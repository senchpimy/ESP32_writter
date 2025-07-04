import gi

gi.require_version("Gtk", "3.0")

import os
import re
import time
import threading
import subprocess
from gi.repository import GLib, Gtk
from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from fabric.widgets.wayland import WaylandWindow as Window

CSS_STYLES_TEMPLATE = """
window {
    background-color: transparent;
}
#popup-box {
    background-color: alpha(@background, 0.90);
    color: @foreground;
    border: 2px solid @color4;
    border-radius: 18px;
    padding: 22px;
    font-size: 16px;
}
#popup-label {
    font-weight: bold;
}
#close-button {
    margin-top: 10px;
    background-color: @color4;
    color: @background;
    font-weight: bold;
    border-radius: 12px;
    padding: 5px 15px;
}
#close-button:hover {
    background-color: alpha(@color4, 0.8);
}
"""
DEFAULT_COLORS = {
    "@background": "#1e1e2e",
    "@foreground": "#cdd6f4",
    "@color4": "#89b4fa",
}


def load_pywal_css(template: str, wal_cache_file="~/.cache/wal/colors.css") -> str:
    wal_file_path = os.path.expanduser(wal_cache_file)
    colors = DEFAULT_COLORS.copy()
    if os.path.exists(wal_file_path):
        try:
            with open(wal_file_path, "r") as f:
                wal_css = f.read()
            pywal_colors = {}
            for match in re.finditer(
                r"--(color\d+|background|foreground):\s*(#[0-9a-fA-F]{6});", wal_css
            ):
                key = match.group(1)
                value = match.group(2)
                pywal_colors[f"@{key}"] = value
            if pywal_colors:
                colors.update(pywal_colors)
                print("Estilos de Pywal cargados exitosamente.")
        except Exception as e:
            print(f"Error al cargar Pywal: {e}. Usando colores por defecto.")
    else:
        print(
            f"Advertencia: No se encontró '{wal_file_path}'. Usando colores por defecto."
        )
    themed_css = template
    for key, value in colors.items():
        themed_css = themed_css.replace(key, value)
    return themed_css


WIDGET_WIDTH = 420
WIDGET_HEIGHT = 100


class TranscriptionPopup(Window):
    def __init__(self, **kwargs):
        super().__init__(
            layer="overlay", anchor="top left", exclusivity="ignore", **kwargs
        )
        self.set_size_request(WIDGET_WIDTH, WIDGET_HEIGHT)
        self.transcription_label = Label(name="popup-label")

        self.close_button = Button(label="Cerrar", name="close-button")
        self.copy_button = Button(label="Copiar", name="copiar-button")
        self.close_button.connect("clicked", self.on_close_clicked)
        self.copy_button.connect("clicked", self.on_copy_clicked)

        self.close_event = None

        main_box = Box(
            name="popup-box",
            orientation="vertical",
            spacing=10,
            children=[self.transcription_label, self.close_button, self.copy_button],
            valign="center",
            halign="center",
        )

        self.add(main_box)
        self.connect("show", self.apply_theme)
        self.hide()

    def on_close_clicked(self, widget):
        if self.close_event:
            self.close_event.set()
        self.hide()

    def on_copy_clicked(self, widget):
        # Usar wl-clipboard para copiar el texto al portapapeles
        text: str = self.transcription_label.get_label()
        text = text.replace("\n", " ")
        if text:
            try:
                subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True)
                print("Texto copiado al portapapeles.")
            except Exception as e:
                print(f"Error al copiar al portapapeles: {e}")

    def show_final_result(self, text, event_to_signal):
        """Muestra el texto final, el botón de cierre y guarda el evento a señalar."""
        self.update_text(text)
        self.close_event = event_to_signal
        self.close_button.show()
        self.queue_resize()

    def hide(self):
        self.close_button.hide()
        self.close_event = None
        super().hide()

    def apply_theme(self, *args):
        print("Aplicando/Recargando tema de Pywal...")
        app = self.get_application()
        if app:
            final_css = load_pywal_css(CSS_STYLES_TEMPLATE)
            app.set_stylesheet_from_string(final_css)

    def update_text(self, text: str):
        if "Escuchando..." in text or "..." in text:
            self.close_button.hide()

        if len(text) > 70:
            n_text = []
            while len(text) > 70:
                cut_index = text.rfind(" ", 0, 70)
                if cut_index == -1:
                    cut_index = 70
                n_text.append(text[:cut_index])
                text = text[cut_index:].lstrip()
            n_text.append(text)
            text = "\n".join(n_text)

        self.transcription_label.set_label(text)
        self.queue_resize()

    def set_position_from_cursor(self):
        try:
            result = subprocess.run(
                ["hyprctl", "cursorpos"], capture_output=True, text=True, check=True
            )
            x_str, y_str = result.stdout.strip().split(",")
            current_width, current_height = self.get_size()
            pos_x = int(x_str) - (current_width // 2)
            pos_y = int(y_str.strip()) - (current_height // 2)
            self.set_margin(f"{pos_y}px 0 0 {pos_x}px")
        except Exception as e:
            print(f"Advertencia: No se pudo obtener la posición del cursor: {e}")
            self.set_margin("0px 0 0 0px")
