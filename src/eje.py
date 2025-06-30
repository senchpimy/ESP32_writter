import numpy as np
import torch
import sounddevice as sd
import time
import sys
import threading

from transformers import (
    pipeline,
    AutoTokenizer,
    WhisperForConditionalGeneration,
    WhisperFeatureExtractor,
)
import collections

BLOCK_SIZE = 4096
MODEL_NAME = "distil-whisper/distil-large-v3"
LANGUAGE = "es"
SAMPLE_RATE = 16000
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
TORCH_DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32

MIN_CHUNK_SECONDS = 5
MAX_CHUNK_SECONDS = 25
SILENCE_THRESHOLD = 0.02
SILENCE_SECONDS = 0.7

print(f"Usando dispositivo: {DEVICE}")

shared_audio_buffer = collections.deque()
buffer_lock = threading.Lock()
is_recording = False


def audio_callback(indata, frames, time, status):
    global is_recording
    if status:
        print(status, file=sys.stderr)
    if is_recording:
        with buffer_lock:
            shared_audio_buffer.append(indata.copy())


def wait_for_enter(stop_event):
    input()
    stop_event.set()


class TranscriptionThread(threading.Thread):
    def __init__(self, asr_pipeline, forced_decoder_ids, stop_session_event):
        super().__init__()
        self.asr_pipeline = asr_pipeline
        self.forced_decoder_ids = forced_decoder_ids
        self.stop_session_event = stop_session_event

    def get_full_buffer(self):
        with buffer_lock:
            if not shared_audio_buffer:
                return np.array([], dtype=np.float32)
            return np.concatenate(list(shared_audio_buffer), axis=0).flatten()

    def find_split_point(self, audio_data):
        samples_per_second = SAMPLE_RATE
        silence_samples = int(SILENCE_SECONDS * samples_per_second)
        chunk_size = int(0.1 * samples_per_second)
        num_chunks = len(audio_data) // chunk_size
        if num_chunks < 10:
            return None
        for i in range(num_chunks - 1, 0, -1):
            start_index = i * chunk_size
            end_index = start_index + silence_samples
            if end_index > len(audio_data):
                continue
            segment = audio_data[start_index:end_index]
            rms = np.sqrt(np.mean(segment**2))
            if rms < SILENCE_THRESHOLD:
                return end_index
        return None

    def process_and_clear_buffer(self, audio_to_process, samples_to_process):
        generate_kwargs = {"forced_decoder_ids": self.forced_decoder_ids}
        result = self.asr_pipeline(
            audio_to_process.copy(), generate_kwargs=generate_kwargs
        )
        transcribed_text = result["text"].strip()
        if transcribed_text:
            print(f"\n>>> {transcribed_text}", end="", flush=True)

        with buffer_lock:
            num_blocks_to_remove = samples_to_process // BLOCK_SIZE
            for _ in range(num_blocks_to_remove):
                if shared_audio_buffer:
                    shared_audio_buffer.popleft()
            remaining_samples = samples_to_process % BLOCK_SIZE
            if remaining_samples > 0 and shared_audio_buffer:
                first_block = shared_audio_buffer[0]
                shared_audio_buffer[0] = first_block[remaining_samples:]

    def run(self):
        global is_recording
        while not self.stop_session_event.is_set():
            if not is_recording:
                time.sleep(0.2)
                continue
            audio_data = self.get_full_buffer()
            buffer_duration = len(audio_data) / SAMPLE_RATE
            if buffer_duration < MIN_CHUNK_SECONDS:
                time.sleep(0.5)
                continue
            split_point = self.find_split_point(audio_data)
            if split_point:
                self.process_and_clear_buffer(audio_data[:split_point], split_point)
            elif buffer_duration > MAX_CHUNK_SECONDS:
                print("\n[Buffer largo, forzando transcripción...]")
                self.process_and_clear_buffer(audio_data, len(audio_data))
            else:
                time.sleep(0.5)
        final_audio = self.get_full_buffer()
        if len(final_audio) > SAMPLE_RATE:
            self.process_and_clear_buffer(final_audio, len(final_audio))
        with buffer_lock:
            shared_audio_buffer.clear()


def main():
    try:
        model = WhisperForConditionalGeneration.from_pretrained(MODEL_NAME)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        feature_extractor = WhisperFeatureExtractor.from_pretrained(MODEL_NAME)

        forced_decoder_ids = tokenizer.get_decoder_prompt_ids(
            language=LANGUAGE, task="transcribe"
        )

        asr_pipeline = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,  # <--- Pasar el extractor aquí
            torch_dtype=TORCH_DTYPE,
            device=DEVICE,
            chunk_length_s=30,
        )
    except Exception as e:
        print(f"Error: {e}")
        return

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            device=None,
            channels=1,
            dtype="float32",
            callback=audio_callback,
        ):
            while True:
                global is_recording
                stop_session_event = threading.Event()

                transcription_thread = TranscriptionThread(
                    asr_pipeline, forced_decoder_ids, stop_session_event
                )
                transcription_thread.start()

                stop_input_thread = threading.Thread(
                    target=wait_for_enter, args=(stop_session_event,)
                )
                is_recording = True
                stop_input_thread.start()
                stop_session_event.wait()
                is_recording = False
                transcription_thread.join()
                stop_input_thread.join()
    except KeyboardInterrupt:
        print("\nSaliendo del programa.")
    except Exception as e:
        print(f"Error fatal: {e}")


if __name__ == "__main__":
    main()
