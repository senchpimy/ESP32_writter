from abc import ABC, abstractmethod
import json
import numpy as np
from faster_whisper import WhisperModel
import torch
import time

try:
    from vosk import Model, KaldiRecognizer
except ImportError:
    print(
        "Advertencia: No se encontró la librería 'vosk'. El motor Vosk no estará disponible."
    )
try:
    import torch
    import whisper
except ImportError:
    print(
        "Advertencia: No se encontró 'torch' o 'whisper'. El motor Whisper no estará disponible."
    )


class TranscriptionEngine(ABC):
    """Clase base abstracta para todos los motores de transcripción."""

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def accept_waveform(self, audio_chunk: bytes):
        """Procesa un fragmento de audio."""
        pass

    @abstractmethod
    def get_partial_result(self) -> str:
        """Devuelve el resultado parcial de la transcripción."""
        pass

    @abstractmethod
    def get_final_result(self) -> str:
        """Devuelve el resultado final y limpia el estado interno."""
        pass

    @abstractmethod
    def reset(self):
        """Resetea el estado del motor para una nueva elocución."""
        pass


class VoskEngine(TranscriptionEngine):
    """Motor de transcripción que utiliza Vosk."""

    def __init__(self, model_path: str, sample_rate: float):
        super().__init__()
        print("Inicializando motor: Vosk")
        try:
            model = Model(model_path)
            self.recognizer = KaldiRecognizer(model, sample_rate)
            self.recognizer.SetWords(True)
            print("Motor Vosk listo.")
        except Exception as e:
            raise RuntimeError(
                f"No se pudo cargar el modelo de Vosk desde '{model_path}': {e}"
            )

    def accept_waveform(self, audio_chunk: bytes):
        return self.recognizer.AcceptWaveform(audio_chunk)

    def get_partial_result(self) -> str:
        partial = json.loads(self.recognizer.PartialResult())
        return partial.get("partial", "")

    def get_final_result(self) -> str:
        final = json.loads(self.recognizer.FinalResult())
        return final.get("text", "")

    def reset(self):
        self.recognizer.Reset()


from pydub import AudioSegment


class WhisperEngine(TranscriptionEngine):
    """
    Motor de transcripción que utiliza un modelo Whisper desde Hugging Face,
    corrigiendo la configuración de generación para modelos fine-tuned.
    """

    def __init__(
        self, model_name: str, sample_rate: float, language: str, channels: int = 1
    ):
        super().__init__()
        print(
            f"Inicializando motor: Whisper (HF) con modelo '{model_name}' e idioma '{language}'"
        )

        from transformers import (
            WhisperForConditionalGeneration,
            WhisperProcessor,
            GenerationConfig,
        )

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if not torch.cuda.is_available():
            print(
                "Advertencia: CUDA no está disponible. Whisper se ejecutará en CPU (más lento)."
            )

        try:
            self.processor = WhisperProcessor.from_pretrained(model_name)
            self.model = WhisperForConditionalGeneration.from_pretrained(model_name)

            # Cargamos una configuración moderna desde el modelo base oficial de OpenAI.
            # (Drazcat/whisper-small-es está basado en openai/whisper-small)
            generation_config = GenerationConfig.from_pretrained("openai/whisper-small")

            self.model.generation_config = generation_config

            self.model.to(device)

        except Exception as e:
            raise RuntimeError(
                f"No se pudo cargar el modelo '{model_name}' desde Hugging Face: {e}"
            )
        self.bytes_per_sample = 2
        self.bytes_per_second = sample_rate * self.bytes_per_sample
        self.channels = channels
        self.device = device
        self.language = language
        self.sample_rate = int(sample_rate)
        self.bytes_per_second = self.sample_rate * self.bytes_per_sample * self.channels

        self.CHUNK_SECONDS = 30
        self.bytes_per_chunk = self.bytes_per_second * self.CHUNK_SECONDS

        self.audio_buffer = bytearray()
        self.transcribed_text = ""
        self.last_partial_result = ""
        self.last_partial_time = 0
        self.seconds_between_partial = 0.5
        print(f"Motor Whisper (Hugging Face) listo con configuración corregida.")

    def accept_waveform(self, audio_chunk: bytes):
        self.audio_buffer.extend(audio_chunk)
        return False

    def _transcribe_chunk(self, audio_bytes: bytes) -> str:
        """Función auxiliar para transcribir un trozo de audio."""
        if not audio_bytes:
            return ""

        audio_np = (
            np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        )

        try:
            input_features = self.processor(
                audio_np, sampling_rate=self.sample_rate, return_tensors="pt"
            ).input_features.to(self.device)

            predicted_ids = self.model.generate(
                input_features, language=self.language, task="transcribe"
            )

            transcription = self.processor.batch_decode(
                predicted_ids, skip_special_tokens=True
            )
            return transcription[0].strip() if transcription else ""
        except Exception as e:
            print(f"Error durante la transcripción del chunk: {e}")
            return ""

    def get_partial_result(self, skip: bool = False) -> str:
        if len(self.audio_buffer) < self.sample_rate * 0.5:
            return ""

        """
        Procesa el buffer de audio, segmentándolo si es necesario, y devuelve
        la transcripción parcial acumulada más la del fragmento actual.
        """
        if time.time() - self.last_partial_time < self.seconds_between_partial:
            return self.last_partial_result

        while len(self.audio_buffer) >= self.bytes_per_chunk:
            chunk_to_process = self.audio_buffer[: self.bytes_per_chunk]

            print(
                f"[Segmentación] Procesando un chunk de {self.CHUNK_SECONDS} segundos..."
            )
            transcribed_chunk_text = self._transcribe_chunk(chunk_to_process)

            if transcribed_chunk_text:
                self.transcribed_text += transcribed_chunk_text + " "

            self.audio_buffer = self.audio_buffer[self.bytes_per_chunk :]
            print(f"[Segmentación] Texto acumulado: '{self.transcribed_text[:50]}...'")

        partial_transcription = self._transcribe_chunk(self.audio_buffer)

        full_result = self.transcribed_text + partial_transcription

        self.last_partial_result = full_result
        self.last_partial_time = time.time()

        return full_result

    def get_final_result(self) -> str:
        """
        Procesa cualquier audio restante en el buffer, lo añade a la transcripción
        y devuelve el texto completo y final.
        """
        final_text = self._transcribe_chunk(self.audio_buffer)

        self.transcribed_text += final_text

        final_result_to_return = self.transcribed_text.strip()
        self.reset()

        return final_result_to_return

    def reset(self):
        self.audio_buffer.clear()
        self.transcribed_text = ""
        self.last_partial_result = ""
        print("Motor reseteado.")


class FasterWhisperEngine(TranscriptionEngine):
    """
    Motor de transcripción que utiliza la implementación optimizada
    de faster-whisper con ctranslate2.
    """

    def __init__(self, model_name: str, sample_rate: float, language: str):
        super().__init__()
        print(f"Inicializando motor: FasterWhisper con modelo '{model_name}'")

        device = "cuda"
        compute_type = "int8"  # faster-whisper no soporta float16 en CPU

        print(f"Usando dispositivo: {device} con tipo de cómputo: {compute_type}")

        try:
            print(f"Cargando modelo de FasterWhisper '{model_name}'...")
            self.model = WhisperModel(
                model_name,
                device=device,
                download_root="./models/faster-whisper",
            )
            print(f"Modelo '{model_name}' cargado correctamente.")

        except Exception as e:
            raise RuntimeError(
                f"No se pudo cargar el modelo de FasterWhisper '{model_name}': {e}"
            )

        self.sample_rate = sample_rate
        self.language = language
        self.audio_buffer = bytearray()
        print("Motor FasterWhisper listo.")

    def accept_waveform(self, audio_chunk: bytes):
        """Acumula el audio en el buffer interno."""
        self.audio_buffer.extend(audio_chunk)
        return False

    def _transcribe_buffer(self) -> str:
        """Función interna para transcribir el buffer actual."""
        if not self.audio_buffer:
            return ""

        audio_np = (
            np.frombuffer(self.audio_buffer, dtype=np.int16).astype(np.float32)
            / 32768.0
        )

        segments, info = self.model.transcribe(
            audio_np, language=self.language, beam_size=5
        )

        full_text = "".join(segment.text for segment in segments)

        return full_text.strip()

    def get_partial_result(self) -> str:
        """
        Realiza una transcripción del buffer actual para simular un resultado parcial.
        No limpia el buffer.
        """
        return self._transcribe_buffer()

    def get_final_result(self) -> str:
        """
        Realiza la transcripción final del buffer.
        El reseteo del buffer se hace llamando a .reset() por separado.
        """
        print(f"Procesando audio final con FasterWhisper...")
        return self._transcribe_buffer()

    def reset(self):
        """Limpia el buffer de audio para la siguiente elocución."""
        self.audio_buffer.clear()
