import sys
import socket
import time
import threading

import numpy as np
import escritor as esc
import popup
from gi.repository import GLib
from fabric import Application

HOST = "0.0.0.0"
PORT = 8888
SAMPLE_RATE = 16000.0
VOLUME_MULTIPLIER = 10.0

# ENGINE_CHOICE = "whisper"
ENGINE_CHOICE = "vosk"

VOSK_MODEL_PATH = "./models/vosk-model-es-0.42"
# "tiny", "base", "small", "medium", "large"
# WHISPER_MODEL_NAME = "base"
WHISPER_MODEL_NAME = "Drazcat/whisper-small-es"
# FASTER_WHISPER_MODEL_NAME = "base"
FASTER_WHISPER_MODEL_NAME = "tiny"
# WHISPER_MODEL_NAME = "tiny"
WHISPER_LANGUAGE = "spanish"
FASTER_WHISPER_LANGUAGE = "es"

TIMEOUT_PAUSA = 2.0
TIMEOUT_ESPERA = 60.0

CSS_STYLES = popup.CSS_STYLES_TEMPLATE


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


def get_final_result(engine, popup_window, addr, popup_is_visible):
    text = engine.get_final_result()
    if text:
        print(f"[{addr}] Final: {text}")
        GLib.idle_add(popup_window.update_text, text.capitalize())
        time.sleep(2.0)

    print("Transmision terminada")
    if popup_is_visible:
        GLib.idle_add(popup_window.hide)

    print(f"[{addr}] Transcipcion finalizada.")


def handle_client_connection(conn, addr, popup_window, engine: esc.TranscriptionEngine):
    """
    Maneja una conexión de cliente persistente. La señal '[END]' o un timeout
    desencadenan la transcripción inmediata y preparan al servidor para la
    siguiente elocución, sin cerrar la conexión.
    """
    print(f"Cliente conectado: {addr}. Usando motor: {engine.__class__.__name__}")

    popup_is_visible = False
    conn.settimeout(TIMEOUT_ESPERA)
    engine.reset()

    reception_buffer = bytearray()

    last_partial_time = time.time()
    PARTIAL_UPDATE_INTERVAL = 0.5  # Segundos entre cada actualización de parcial

    while True:
        try:

            def process_transcription():
                nonlocal popup_is_visible
                text = engine.get_final_result()
                if text:
                    print(f"[{addr}] Final: {text}")
                    GLib.idle_add(popup_window.update_text, text.capitalize())
                    time.sleep(1.5)

                print("Transmision terminada")
                if popup_is_visible:
                    GLib.idle_add(popup_window.hide)
                    popup_is_visible = False

                engine.reset()
                conn.settimeout(TIMEOUT_ESPERA)

            data_chunk = conn.recv(1024)
            if not data_chunk:
                print(f"[{addr}] Cliente desconectado (flujo finalizado).")
                break

            reception_buffer.extend(data_chunk)

            end_signal_pos = reception_buffer.find(b"[END]")

            if end_signal_pos != -1:
                print(f"[{addr}] Señal de fin instantánea recibida.")

                audio_to_process = reception_buffer[:end_signal_pos]
                engine.accept_waveform(
                    increase_volume_pcm16(audio_to_process, VOLUME_MULTIPLIER)
                )

                process_transcription()

                reception_buffer.clear()
                continue

            audio_to_process = bytes(reception_buffer)

            if not popup_is_visible and audio_to_process:
                print(f"[{addr}] Nueva elocución detectada. Mostrando popup.")
                GLib.idle_add(popup_window.set_position_from_cursor)
                GLib.idle_add(popup_window.update_text, "Escuchando...")
                GLib.idle_add(popup_window.show_all)
                popup_is_visible = True
                conn.settimeout(TIMEOUT_PAUSA)

            if engine.accept_waveform(
                increase_volume_pcm16(audio_to_process, VOLUME_MULTIPLIER)
            ):
                pass
            else:
                is_whisper = isinstance(engine, esc.WhisperEngine)
                if is_whisper:
                    current_time = time.time()
                    if (current_time - last_partial_time) > PARTIAL_UPDATE_INTERVAL:
                        partial_text = engine.get_partial_result()
                        last_partial_time = current_time
                else:
                    partial_text = engine.get_partial_result()
                if partial_text:
                    GLib.idle_add(popup_window.update_text, f"{partial_text}...")

            reception_buffer.clear()

        except socket.timeout:
            print(f"[{addr}] Final por pausa (timeout).")
            process_transcription()
            reception_buffer.clear()
            continue

        except (ConnectionResetError, BrokenPipeError):
            print(f"\n[{addr}] Conexión cerrada por el cliente.")
            break
        except Exception as e:
            print(f"\n[{addr}] Error inesperado durante la conexión: {e}")
            break

    print(f"[{addr}] Finalizando sesión de conexión.")
    if popup_is_visible:
        GLib.idle_add(popup_window.hide)
    conn.close()


def start_server_logic(popup_window, app):
    try:
        if ENGINE_CHOICE == "vosk":
            engine = esc.VoskEngine(VOSK_MODEL_PATH, SAMPLE_RATE)
        elif ENGINE_CHOICE == "whisper":
            engine = esc.WhisperEngine(
                WHISPER_MODEL_NAME, SAMPLE_RATE, WHISPER_LANGUAGE
            )
        elif ENGINE_CHOICE == "faster-whisper":
            engine = esc.FasterWhisperEngine(
                FASTER_WHISPER_MODEL_NAME, SAMPLE_RATE, FASTER_WHISPER_LANGUAGE
            )
        else:
            raise ValueError(
                f"Motor '{ENGINE_CHOICE}' no reconocido. Opciones: 'vosk', 'whisper' or 'faster-whisper'."
            )
    except Exception as e:
        print(f"Error fatal al inicializar el motor de transcripción: {e}")
        GLib.idle_add(app.quit)
        return

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
                handle_client_connection(conn, addr, popup_window, engine)
            except Exception as e:
                print(f"Error en el bucle principal del servidor: {e}")
                time.sleep(1)


def main():
    popup_window = popup.TranscriptionPopup()
    app = Application("modular-transcriber", popup_window, standalone=True)
    final_css = popup.load_pywal_css(CSS_STYLES)
    app.set_stylesheet_from_string(final_css)

    server_thread = threading.Thread(
        target=start_server_logic, args=(popup_window, app), daemon=True
    )
    server_thread.start()

    return app.run()


if __name__ == "__main__":
    sys.exit(main())
