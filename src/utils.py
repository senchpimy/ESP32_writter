import time
import numpy as np
from gi.repository import GLib


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
