from abc import ABC, abstractmethod
import json
import numpy as np

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


class WhisperEngine(TranscriptionEngine):
    """
    Motor de transcripción que utiliza un modelo Whisper desde Hugging Face,
    corrigiendo la configuración de generación para modelos fine-tuned.
    """

    def __init__(self, model_name: str, sample_rate: float, language: str):
        super().__init__()
        print(
            f"Inicializando motor: Whisper (HF) con modelo '{model_name}' e idioma '{language}'"
        )

        from transformers import (
            WhisperForConditionalGeneration,
            WhisperProcessor,
            GenerationConfig,
        )

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

            self.model.to("cuda" if torch.cuda.is_available() else "cpu")

        except Exception as e:
            raise RuntimeError(
                f"No se pudo cargar el modelo '{model_name}' desde Hugging Face: {e}"
            )

        self.sample_rate = sample_rate
        self.language = language  # Guardamos el idioma para usarlo en generate()
        self.audio_buffer = bytearray()
        print(f"Motor Whisper (Hugging Face) listo con configuración corregida.")

    def accept_waveform(self, audio_chunk: bytes):
        self.audio_buffer.extend(audio_chunk)
        return False

    def get_partial_result(self) -> str:
        if len(self.audio_buffer) < self.sample_rate * 0.5:
            return ""

        audio_np = (
            np.frombuffer(self.audio_buffer, dtype=np.int16).astype(np.float32)
            / 32768.0
        )

        input_features = self.processor(
            audio_np, sampling_rate=self.sample_rate, return_tensors="pt"
        ).input_features
        input_features = input_features.to(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        predicted_ids = self.model.generate(
            input_features, language=self.language, task="transcribe"
        )
        transcription = self.processor.batch_decode(
            predicted_ids, skip_special_tokens=True
        )

        return transcription[0].strip() if transcription else ""

    def get_final_result(self) -> str:
        return self.get_partial_result()

    def reset(self):
        self.audio_buffer.clear()
