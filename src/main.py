import sys
import socket
import json
import time
import threading
import subprocess

import numpy as np
from gi.repository import GLib
from vosk import Model, KaldiRecognizer
from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.wayland import WaylandWindow as Window

HOST = "0.0.0.0"
PORT = 8888
MODEL_PATH = "./models/vosk-model-es-0.42"
SAMPLE_RATE = 16000.0
VOLUME_MULTIPLIER = 10.0
TIMEOUT_PAUSA = 1.0  # Segundos de silencio para considerar una pausa
TIMEOUT_ESPERA = 60.0  # Segundos para esperar una nueva elocución

WIDGET_WIDTH = 420
WIDGET_HEIGHT = 150

CSS_STYLES = """
window { background-color: transparent; }
#popup-box {
    background-color: rgba(30, 30, 46, 0.95);
    color: #cdd6f4;
    border-radius: 18px;
    border: 1px solid #89b4fa;
    padding: 22px;
    font-size: 16px;
}
#popup-label { font-weight: bold; }
"""

try:
    print(f"Cargando modelo Vosk desde: {MODEL_PATH}")
    VOSK_MODEL = Model(MODEL_PATH)
    print("Modelo Vosk cargado exitosamente.")
except Exception as e:
    print(f"Error crítico al cargar el modelo Vosk: {e}")
    sys.exit(1)


class TranscriptionPopup(Window):
    def __init__(self, **kwargs):
        super().__init__(
            layer="overlay", anchor="top left", exclusivity="ignore", **kwargs
        )
        self.set_size_request(WIDGET_WIDTH, WIDGET_HEIGHT)
        self.transcription_label = Label(name="popup-label")
        self.add(
            Box(
                name="popup-box",
                children=[self.transcription_label],
                valign="center",
                halign="center",
            )
        )
        self.hide()

    def update_text(self, text: str):
        self.transcription_label.set_label(text)

    def set_position_from_cursor(self):
        try:
            result = subprocess.run(
                ["hyprctl", "cursorpos"], capture_output=True, text=True, check=True
            )
            x_str, y_str = result.stdout.strip().split(",")
            cursor_x, cursor_y = int(x_str), int(y_str.strip())
            pos_x = cursor_x - (WIDGET_WIDTH // 2)
            pos_y = cursor_y - (WIDGET_HEIGHT // 2)
            self.set_margin(f"{pos_y}px 0 0 {pos_x}px")
        except Exception as e:
            print(f"Advertencia: No se pudo obtener la posición del cursor: {e}")
            self.set_margin("0px 0 0 0px")


def increase_volume_pcm16(audio_bytes, multiplier):
    if not audio_bytes or len(audio_bytes) % 2 != 0:
        return audio_bytes
    try:
        samples = np.frombuffer(audio_bytes, dtype=np.int16)
        samples_float = samples.astype(np.float64) * multiplier
        samples_clipped = np.clip(samples_float, -32768, 32767)
        return samples_clipped.astype(np.int16).tobytes()
    except:
        return audio_bytes


def handle_client_connection(conn, addr, popup_window):
    """
    Maneja la conexión de un cliente. El popup aparece y se reposiciona con cada
    elocución y se oculta durante las pausas.
    """
    print(f"Cliente conectado: {addr}. Esperando audio...")

    recognizer = KaldiRecognizer(VOSK_MODEL, SAMPLE_RATE)
    recognizer.SetWords(True)

    popup_is_visible = False
    conn.settimeout(TIMEOUT_ESPERA)

    try:
        while True:
            try:
                data_original = conn.recv(1024)
                if not data_original:
                    print(f"[{addr}] Cliente desconectado (flujo finalizado).")
                    break

                if not popup_is_visible:
                    print(
                        f"[{addr}] Nueva elocución detectada. Mostrando y reposicionando popup."
                    )
                    GLib.idle_add(popup_window.set_position_from_cursor)
                    GLib.idle_add(popup_window.update_text, "Escuchando...")
                    GLib.idle_add(popup_window.show_all)
                    popup_is_visible = True
                    conn.settimeout(TIMEOUT_PAUSA)  # Timeout corto para detectar pausas

                data_processed = increase_volume_pcm16(data_original, VOLUME_MULTIPLIER)

                if recognizer.AcceptWaveform(data_processed):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        GLib.idle_add(popup_window.update_text, text.capitalize())
                        print(f"\n[{addr}] Resultado: {text}")
                else:
                    partial = json.loads(recognizer.PartialResult())
                    partial_text = partial.get("partial", "")
                    if partial_text:
                        GLib.idle_add(popup_window.update_text, f"{partial_text}...")

            except socket.timeout:
                final_result = json.loads(recognizer.FinalResult())
                text = final_result.get("text", "")
                if text:
                    print(f"\n[{addr}] Final (por pausa): {text}")
                    GLib.idle_add(popup_window.update_text, text.capitalize())
                    time.sleep(1.5)

                print("Transmision terminada")
                GLib.idle_add(popup_window.hide)
                popup_is_visible = False

                recognizer.Reset()
                conn.settimeout(TIMEOUT_ESPERA)
                continue

            except (ConnectionResetError, BrokenPipeError):
                print(f"\n[{addr}] Conexión cerrada por el cliente.")
                break
            except Exception as e:
                print(f"\n[{addr}] Error inesperado: {e}")
                break

    finally:
        print(f"[{addr}] Conexión finalizada.")
        if popup_is_visible:
            GLib.idle_add(popup_window.hide)
        conn.close()


def start_server_logic(popup_window, app):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, PORT))
            s.listen()
            print(f"Servidor escuchando en {HOST}:{PORT}...")
        except OSError as e:
            print(f"Error crítico al iniciar el servidor: {e}")
            GLib.idle_add(app.quit)
            return

        while True:
            try:
                conn, addr = s.accept()
                handle_client_connection(conn, addr, popup_window)
            except Exception as e:
                print(f"Error en el bucle principal del servidor: {e}")
                time.sleep(1)


def main():
    popup_window = TranscriptionPopup()
    app = Application("vosk-fabric-popup", popup_window, standalone=True)
    app.set_stylesheet_from_string(CSS_STYLES)

    server_thread = threading.Thread(
        target=start_server_logic, args=(popup_window, app), daemon=True
    )
    server_thread.start()

    return app.run()


if __name__ == "__main__":
    sys.exit(main())
