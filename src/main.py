import sys
import socket
import time
import threading

import escritor as esc
import popup
from utils import increase_volume_pcm16, get_final_result
from gi.repository import GLib
from fabric import Application

HOST = "0.0.0.0"
PORT = 8888
SAMPLE_RATE = 16000.0
VOLUME_MULTIPLIER = 5.0
ENGINE_CHOICE = "whisper"
VOSK_MODEL_PATH = "./models/vosk-model-es-0.42"
WHISPER_MODEL_NAME = "Drazcat/whisper-small-es"
FASTER_WHISPER_MODEL_NAME = "tiny"
WHISPER_LANGUAGE = "spanish"
FASTER_WHISPER_LANGUAGE = "es"
TIMEOUT_PAUSA = 2.0
TIMEOUT_ESPERA = 60.0
CSS_STYLES = popup.CSS_STYLES_TEMPLATE


def handle_client_connection(conn, addr, popup_window, engine: esc.TranscriptionEngine):
    print(f"Cliente conectado: {addr}. Usando motor: {engine.__class__.__name__}")

    close_event = threading.Event()
    is_final_result_shown = False

    conn.settimeout(TIMEOUT_ESPERA)
    engine.reset()
    reception_buffer = bytearray()
    last_partial_time = time.time()
    PARTIAL_UPDATE_INTERVAL = 0.5

    def process_transcription():
        nonlocal is_final_result_shown
        text = engine.get_final_result()
        if text:
            print(f"[{addr}] Final: {text}")
            GLib.idle_add(
                popup_window.show_final_result, text.capitalize(), close_event
            )
            is_final_result_shown = True
        else:
            if popup_window.is_visible():
                GLib.idle_add(popup_window.hide)

        print("Transmisión terminada. Esperando cierre manual.")
        engine.reset()
        conn.settimeout(TIMEOUT_ESPERA)

    while True:
        try:
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

            if not popup_window.is_visible() and audio_to_process:
                print(f"[{addr}] Nueva elocución detectada. Mostrando popup.")
                GLib.idle_add(popup_window.set_position_from_cursor)
                GLib.idle_add(popup_window.update_text, "Escuchando...")
                GLib.idle_add(popup_window.show_all)
                conn.settimeout(TIMEOUT_PAUSA)

            if not engine.accept_waveform(
                increase_volume_pcm16(audio_to_process, VOLUME_MULTIPLIER)
            ):
                partial_text = ""
                is_whisper = isinstance(
                    engine, (esc.WhisperEngine, esc.FasterWhisperEngine)
                )
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

    if is_final_result_shown:
        print("El hilo del servidor está en espera a que el popup se cierre...")
        closed_in_time = close_event.wait(timeout=300.0)  # 5 minutos de timeout
        if not closed_in_time:
            print("Timeout de espera. Ocultando popup automáticamente.")
            GLib.idle_add(popup_window.hide)

    print(f"[{addr}] Finalizando sesión de conexión.")
    if popup_window.is_visible():
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
            raise ValueError(f"Motor '{ENGINE_CHOICE}' no reconocido.")
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
