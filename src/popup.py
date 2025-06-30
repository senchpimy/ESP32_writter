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
    
    /* Sombra para dar profundidad */
}
#popup-label {
    font-weight: bold;
}
"""

DEFAULT_COLORS = {
    "@background": "#1e1e2e",
    "@foreground": "#cdd6f4",
    "@color4": "#89b4fa",
}


def load_pywal_css(template: str, wal_cache_file="~/.cache/wal/colors.css") -> str:
    """Carga los colores de Pywal y los inyecta en la plantilla CSS."""
    wal_file_path = os.path.expanduser(wal_cache_file)
    colors = DEFAULT_COLORS.copy()  # Empezar con los por defecto

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
        self.add(
            Box(
                name="popup-box",
                children=[self.transcription_label],
                valign="center",
                halign="center",
            )
        )
        self.connect("show", self.apply_theme)
        self.hide()

    def apply_theme(self, *args):
        """Carga y aplica el tema de Pywal a la aplicación."""
        print("Aplicando/Recargando tema de Pywal...")
        app = self.get_application()
        if app:
            final_css = load_pywal_css(CSS_STYLES_TEMPLATE)
            app.set_stylesheet_from_string(final_css)

    def update_text(self, text: str):
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


def text_simulator(popup_window: TranscriptionPopup):
    test_phrases = [
        "Hola.",
        "Esta es una prueba de transcripción.",
        "Ahora vamos a probar una frase mucho más larga para ver cómo el texto se ajusta automáticamente.",
        "Este es un ejemplo de texto que debería ocupar varias líneas. Funciona gracias al corte manual de palabras.",
        "Lorem ipsum dolor sit amet, officia excepteur ex fugiat reprehenderit enim labore culpa sint ad nisi Lorem pariatur mollit ex esse exercitation amet. Nisi anim cupidatat excepteur officia. Reprehenderit nostrud nostrud ipsum Lorem est aliquip amet voluptate voluptate dolor minim nulla est proident.",
        "Y ahora una frase corta de nuevo.",
        "Adiós.",
    ]
    GLib.idle_add(popup_window.show_all)
    GLib.idle_add(popup_window.set_position_from_cursor)
    for phrase in test_phrases:
        GLib.idle_add(popup_window.update_text, phrase)
        time.sleep(4)
    GLib.idle_add(popup_window.get_application().quit)


if __name__ == "__main__":
    popup = TranscriptionPopup()
    app = Application("popup-test", popup, standalone=True)

    final_css = load_pywal_css(CSS_STYLES_TEMPLATE)

    app.set_stylesheet_from_string(final_css)

    simulator_thread = threading.Thread(
        target=text_simulator, args=(popup,), daemon=True
    )
    simulator_thread.start()
    app.run()
