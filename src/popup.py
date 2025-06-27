from gi.repository import GLib
from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.wayland import WaylandWindow as Window
import subprocess


WIDGET_WIDTH = 420
WIDGET_HEIGHT = 150


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
        self.hide()

    def update_text(self, text: str):
        self.transcription_label.set_label(text)

    def set_position_from_cursor(self):
        try:
            result = subprocess.run(
                ["hyprctl", "cursorpos"], capture_output=True, text=True, check=True
            )
            x_str, y_str = result.stdout.strip().split(",")
            # pos_x = int(x_str) - (WIDGET_WIDTH // 2)
            # pos_y = int(y_str.strip()) - (WIDGET_HEIGHT // 2)

            pos_x = int(x_str)
            pos_y = int(y_str.strip())
            self.set_margin(f"{pos_y}px 0 0 {pos_x}px")
        except Exception as e:
            print(f"Advertencia: No se pudo obtener la posición del cursor: {e}")
            self.set_margin("0px 0 0 0px")
