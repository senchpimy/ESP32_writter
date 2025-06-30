import sounddevice
import numpy
import socket
import sounddevice as sd
import numpy as np
import sys
import threading

SERVER_IP = "0.0.0.0"
SERVER_PORT = 8888

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
BLOCK_SIZE = 1024


is_recording = False
recording_lock = threading.Lock()


def check_recording_status():
    """Función para verificar de forma segura el estado de grabación."""
    with recording_lock:
        return is_recording


def set_recording_status(status):
    """Función para cambiar de forma segura el estado de grabación."""
    global is_recording
    with recording_lock:
        is_recording = status


def audio_callback(indata, frames, time, status):
    """
    Esta función es llamada por sounddevice cada vez que hay un nuevo bloque de audio.
    """
    if status:
        print(status, file=sys.stderr)

    if check_recording_status():
        try:
            client_socket.sendall(indata.tobytes())
        except (BrokenPipeError, ConnectionResetError):
            print("Error: La conexión con el servidor se ha perdido.", file=sys.stderr)
            set_recording_status(False)
        except Exception as e:
            print(f"Error enviando datos: {e}", file=sys.stderr)
            set_recording_status(False)


def main():
    """
    Función principal que se conecta al servidor y gestiona la grabación.
    """
    global client_socket

    try:
        print(f"Intentando conectar al servidor en {SERVER_IP}:{SERVER_PORT}...")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((SERVER_IP, SERVER_PORT))
        print("¡Conectado al servidor!")

    except Exception as e:
        print(f"No se pudo conectar al servidor: {e}", file=sys.stderr)
        return

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            device=None,  # Micrófono por defecto
            channels=CHANNELS,
            dtype=DTYPE,
            callback=audio_callback,
        ):
            print("\n--- Micrófono listo ---")
            print("Presiona [Enter] para empezar a grabar y enviar audio.")
            print("Presiona [Enter] de nuevo para detener la grabación.")
            print("Presiona Ctrl+C para salir del programa.\n")

            while True:
                input()

                if not check_recording_status():
                    print("▶️  Grabando... (presiona Enter para detener)")
                    set_recording_status(True)
                else:
                    set_recording_status(False)
                    print("⏹️  Detenido. Enviando marcador de fin...")

                    try:
                        client_socket.sendall(b"[END]")
                        print(
                            "Marcador enviado. Presiona Enter para grabar de nuevo.\n"
                        )
                    except Exception as e:
                        print(
                            f"No se pudo enviar el marcador [END]: {e}", file=sys.stderr
                        )
                        break

    except KeyboardInterrupt:
        print("\nSaliendo del programa...")
    except Exception as e:
        print(f"Ocurrió un error: {e}", file=sys.stderr)
    finally:
        if "client_socket" in globals():
            client_socket.close()
            print("Conexión cerrada.")


if __name__ == "__main__":
    main()
