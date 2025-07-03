import gi

gi.require_version("Gtk", "3.0")

from gi.repository import GLib, Gtk, Gdk
from fabric import Application
from fabric.widgets.wayland import WaylandWindow as Window
from fabric.widgets.svg import Svg

import sounddevice as sd
import numpy as np
import socket
import threading
import os
import re
import sys
import signal
import time

SERVER_IP = "127.0.0.1"
SERVER_PORT = 8888
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
BLOCK_SIZE = 1024
PID_FILE = "/tmp/transcription_popup.pid"
VOICE_THRESHOLD = 1500
GAIN_FACTOR = 1.8
SMOOTHING_FACTOR = 0.2

CSS_STYLES_TEMPLATE = """
#transcription-popup {{
    background-color: transparent;
}}
#inner-circle {{
    background-color: {color8}; 
    border-width: {border_thickness}px;
    border-style: solid;
    border-color: alpha(#00FFFF, {glow_level});
    border-radius: 9999px;
    padding: 10px;
}}
#mic-icon {{
    color: {color_fg};
}}
"""

DEFAULT_COLORS = {"color_fg": "#D8DEE9", "color8": "#434C5E"}


def get_pywal_colors(wal_cache_file="~/.cache/wal/colors.css") -> dict:
    wal_file_path = os.path.expanduser(wal_cache_file)
    colors = DEFAULT_COLORS.copy()
    if os.path.exists(wal_file_path):
        try:
            with open(wal_file_path, "r") as f:
                wal_css = f.read()
            pywal_colors = {}
            color_map = {"foreground": "color_fg", "color8": "color8"}
            for match in re.finditer(
                r"--(color\d+|foreground):\s*(#[0-9a-fA-F]{6});", wal_css
            ):
                key = match.group(1)
                if key in color_map:
                    pywal_key = color_map[key]
                    pywal_colors[pywal_key] = match.group(2)
            if pywal_colors:
                colors.update(pywal_colors)
        except Exception as e:
            print(f"Error al cargar Pywal: {e}. Usando colores por defecto.")
    return colors


ICON_SIZE = 64
MAX_BORDER_WIDTH = 4

audio_stream = None


class TranscriptionPopup(Window):
    def __init__(self, **kwargs):
        super().__init__(
            layer="overlay", anchor="top right", exclusivity="ignore", **kwargs
        )
        self.set_name("transcription-popup")
        self.set_margin("20px 20px 0 0")
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)
        self.set_app_paintable(True)
        self.glow_level = 0.0

        mic_icon = Svg(svg_file="mic.svg", name="mic-icon")
        mic_icon.set_size_request(ICON_SIZE, ICON_SIZE)
        inner_circle_frame = Gtk.Frame()
        inner_circle_frame.set_name("inner-circle")
        inner_circle_frame.set_shadow_type(Gtk.ShadowType.NONE)
        inner_circle_frame.add(mic_icon)
        self.add(inner_circle_frame)
        self.connect("show", self.apply_theme)
        self.hide()

    def apply_theme(self, *args):
        colors = get_pywal_colors()
        colors["glow_level"] = self.glow_level
        colors["border_thickness"] = self.glow_level * MAX_BORDER_WIDTH
        final_css = CSS_STYLES_TEMPLATE.format(**colors)
        provider = Gtk.CssProvider()
        provider.load_from_data(final_css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def set_glow_level(self, level: float):
        new_level = max(0.0, min(1.0, level))
        if abs(new_level - self.glow_level) > 0.01:
            self.glow_level = new_level
            self.apply_theme()


def audio_stream_thread(popup: TranscriptionPopup, client_socket: socket.socket):
    global audio_stream
    smooth_volume = 0.0

    def audio_callback(indata, frames, time, status):
        nonlocal smooth_volume
        try:
            client_socket.sendall(indata.tobytes())
            rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
            volume_normalized = np.clip((rms / VOICE_THRESHOLD) * GAIN_FACTOR, 0.0, 1.0)
            smooth_volume = (smooth_volume * (1 - SMOOTHING_FACTOR)) + (
                volume_normalized * SMOOTHING_FACTOR
            )
            GLib.idle_add(popup.set_glow_level, smooth_volume)
        except Exception:
            if audio_stream and audio_stream.active:
                audio_stream.stop()

    try:
        audio_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=audio_callback,
        )
        audio_stream.start()
    except Exception as e:
        print(f"Error al iniciar el stream de audio: {e}")


def handle_singleton():
    """Verifica si ya hay una instancia en ejecución y la termina."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            print(
                f"Encontrada instancia anterior con PID {old_pid}. Enviando señal de terminación..."
            )
            os.kill(old_pid, signal.SIGTERM)
            time.sleep(0.5)
            sys.exit(0)
        except Exception as e:
            pass

    my_pid = os.getpid()
    with open(PID_FILE, "w") as f:
        f.write(str(my_pid))
    print(f"Instancia actual corriendo con PID {my_pid}.")


def on_shutdown(application, sock: socket.socket):
    """
    Función de limpieza centralizada. Se ejecuta cuando la app se cierra.
    """
    global audio_stream
    print("Iniciando secuencia de cierre...")

    if audio_stream and audio_stream.active:
        print("Deteniendo stream de audio...")
        audio_stream.stop()
        audio_stream.close()

    try:
        if sock:
            print("Enviando [END] al servidor...")
            sock.sendall(b"[END]")
            sock.close()
    except Exception as e:
        print(f"Error al enviar [END] o cerrar el socket: {e}")

    try:
        if os.path.exists(PID_FILE) and os.access(PID_FILE, os.W_OK):
            with open(PID_FILE, "r") as f:
                if int(f.read().strip()) == os.getpid():
                    os.remove(PID_FILE)
                    print("Archivo PID eliminado.")
    except Exception as e:
        print(f"Error al eliminar el archivo PID: {e}")


if __name__ == "__main__":
    handle_singleton()

    client_socket = None
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((SERVER_IP, SERVER_PORT))
        print("¡Conectado al servidor!")
    except Exception as e:
        print(f"No se pudo conectar al servidor: {e}")
        if os.path.exists(PID_FILE) and int(open(PID_FILE).read()) == os.getpid():
            os.remove(PID_FILE)
        exit(1)

    popup = TranscriptionPopup()
    app = Application("popup-test", popup, standalone=True)

    app.connect("shutdown", on_shutdown, client_socket)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: app.quit())

    audio_thread = threading.Thread(
        target=audio_stream_thread, args=(popup, client_socket), daemon=True
    )
    audio_thread.start()

    popup.show_all()

    app.run()
