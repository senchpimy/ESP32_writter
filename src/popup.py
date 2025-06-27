from gi.repository import GLib
from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.wayland import WaylandWindow as Window
import subprocess
import time
import threading


WIDGET_WIDTH = 200
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
        self.hide()

    def update_text(self, text: str):
        if len(text) > 70:
            # text = [text[i : i + 70] for i in range(0, len(text), 70)]
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


def text_simulator(popup_window: TranscriptionPopup):
    test_phrases = [
        "Hola.",
        "Esta es una prueba de transcripción.",
        "Lorem ipsum dolor sit amet, officia excepteur ex fugiat reprehenderit enim labore culpa sint ad nisi Lorem pariatur mollit ex esse exercitation amet. Nisi anim cupidatat excepteur officia. Reprehenderit nostrud nostrud ipsum Lorem est aliquip amet voluptate voluptate dolor minim nulla est proident. Nostrud officia pariatur ut officia. Sit irure elit esse ea nulla sunt ex occaecat reprehenderit commodo officia dolor Lorem duis laboris cupidatat officia voluptate. Culpa proident adipisicing id nulla nisi laboris ex in Lorem sunt duis officia eiusmod. Aliqua reprehenderit commodo ex non excepteur duis sunt velit enim. Voluptate laboris sint cupidatat ullamco ut ea consectetur et est culpa et culpa duis."
        "Y ahora una frase corta de nuevo.",
        "Adiós.",
    ]

    GLib.idle_add(popup_window.show_all)

    for phrase in test_phrases:
        GLib.idle_add(popup_window.update_text, phrase)
        time.sleep(4)

    GLib.idle_add(popup_window.get_application().quit)


if __name__ == "__main__":
    CSS_FOR_TESTING = """
    window { background-color: transparent; }
    #popup-box {
        background-color: rgba(30, 30, 46, 0.95); color: #cdd6f4;
        border-radius: 18px; border: 1px solid #89b4fa;
        padding: 22px; font-size: 16px;
    }
    #popup-label { font-weight: bold; color: #00FF00; }
    .transparent { background-color: transparent; border: none; }
    """

    popup = TranscriptionPopup()
    app = Application("popup-test", popup, standalone=True)
    app.set_stylesheet_from_string(CSS_FOR_TESTING)

    simulator_thread = threading.Thread(
        target=text_simulator, args=(popup,), daemon=True
    )
    simulator_thread.start()
    app.run()
