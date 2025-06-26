import socket
import json
from vosk import Model, KaldiRecognizer
import time
import struct
import numpy as np

HOST = "0.0.0.0"
PORT = 8888

MODEL_PATH = "./models/vosk-model-es-0.42"
SAMPLE_RATE = 16000.0

VOLUME_MULTIPLIER = 10.0

try:
    print(f"Cargando modelo Vosk desde: {MODEL_PATH}")
    VOSK_MODEL = Model(MODEL_PATH)
    print("Modelo Vosk cargado globalmente.")
except Exception as e:
    print(f"Error crítico al cargar el modelo Vosk: {e}")
    print("El servidor no puede iniciar sin el modelo. Saliendo.")
    exit(1)


def increase_volume_pcm16(audio_bytes, multiplier):
    if not audio_bytes or len(audio_bytes) % 2 != 0:
        return audio_bytes

    num_samples = len(audio_bytes) // 2
    try:
        samples = np.frombuffer(audio_bytes, dtype=np.int16)
        if samples.size != num_samples:
            samples = np.array(
                struct.unpack(f"<{num_samples}h", audio_bytes), dtype=np.int16
            )
    except (struct.error, ValueError) as e:
        print(f"Error desempaquetando audio_bytes: {e}. Bytes: {len(audio_bytes)}")
        return audio_bytes

    samples_float = samples.astype(np.float64) * multiplier
    samples_clipped = np.clip(samples_float, -32768, 32767)
    samples_processed_np = samples_clipped.astype(np.int16)

    try:
        return samples_processed_np.tobytes()
    except Exception as e:
        print(f"Error convirtiendo samples_processed_np a bytes: {e}")
        try:
            return struct.pack(f"<{num_samples}h", *samples_processed_np)
        except struct.error as se:
            print(f"Error empaquetando samples_processed_np con struct: {se}")
            return audio_bytes


def handle_client_connection(conn, addr, vosk_model_instance):
    """Maneja una conexión individual de un cliente ESP32."""
    print(f"Conectado por {addr}")

    recognizer = KaldiRecognizer(vosk_model_instance, SAMPLE_RATE)
    recognizer.SetWords(True)
    print(f"Reconocedor Vosk listo para la conexión desde {addr}")

    conn.settimeout(60.0)

    last_data_time = time.time()
    first_data_received = False
    packet_count = 0

    print(f"[{addr}] Esperando que el ESP32 comience a transmitir audio...")

    try:
        while True:
            try:
                data_original = conn.recv(1024)
                if not data_original:
                    print(
                        f"[{addr}] Cliente desconectado (no hay más datos). Fin de flujo."
                    )
                    break

                packet_count += 1

                if not first_data_received:
                    print(
                        f"[{addr}] Primer fragmento de audio recibido (paquete {packet_count}, {len(data_original)} bytes)."
                    )
                    first_data_received = True
                    conn.settimeout(2.0)

                data_processed = increase_volume_pcm16(data_original, VOLUME_MULTIPLIER)

                if recognizer.AcceptWaveform(data_processed):
                    result_json = recognizer.Result()
                    result_dict = json.loads(result_json)
                    if "text" in result_dict and result_dict["text"]:
                        print(
                            f"[{addr}] Transcripción (completa): {result_dict['text']}"
                        )
                else:
                    partial_json = recognizer.PartialResult()
                    partial_dict = json.loads(partial_json)
                    if "partial" in partial_dict and partial_dict["partial"]:
                        print(f"[{addr}] Parcial: {partial_dict['partial']}", end="\r")

                last_data_time = time.time()

            except socket.timeout:
                if first_data_received:
                    final_result_json = recognizer.FinalResult()  # Obtener lo que haya
                    final_result_dict = json.loads(final_result_json)
                    if "text" in final_result_dict and final_result_dict["text"]:
                        print(
                            f"\n[{addr}] Transcripción (por pausa/fin de botón): {final_result_dict['text']}"
                        )

                    print(
                        f"\n[{addr}] Timeout esperando más datos. Listo para nueva elocución si el ESP32 envía."
                    )
                    first_data_received = False
                    conn.settimeout(60.0)
                    last_data_time = time.time()

                else:
                    print(
                        f"\n[{addr}] Timeout inicial esperando el primer fragmento de audio. El ESP32 no envió nada."
                    )
                    break
                continue

            except ConnectionResetError:
                print(
                    f"[{addr}] Conexión reseteada por el cliente (después de {packet_count} paquetes)."
                )
                break
            except Exception as e:
                print(
                    f"[{addr}] Error durante la comunicación (después de {packet_count} paquetes): {e}"
                )
                break

    finally:
        if first_data_received:
            final_cleanup_json = recognizer.FinalResult()
            final_cleanup_dict = json.loads(final_cleanup_json)
            if "text" in final_cleanup_dict and final_cleanup_dict["text"]:
                print(
                    f"\n[{addr}] Transcripción final (limpieza de conexión): {final_cleanup_dict['text']}"
                )

        print(
            f"[{addr}] Conexión cerrada. Paquetes totales recibidos en esta sesión: {packet_count}"
        )
        conn.close()


def start_persistent_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"Servidor persistente escuchando en {HOST}:{PORT}...")
        print("Presiona Ctrl+C para detener el servidor.")

        while True:
            try:
                conn, addr = s.accept()
                handle_client_connection(conn, addr, VOSK_MODEL)

            except KeyboardInterrupt:
                print("\nServidor detenido por el usuario (Ctrl+C).")
                break
            except Exception as e:
                print(
                    f"Error en el bucle principal del servidor al aceptar conexión: {e}"
                )
                time.sleep(1)

    print("Servidor finalizado.")


if __name__ == "__main__":
    start_persistent_server()
