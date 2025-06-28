# Transcriptor Modular con Cliente Hardware ESP32

Este proyecto implementa un sistema de transcripción de voz en tiempo real compuesto por dos partes principales:

1.  **Cliente Hardware (M5Stack Atom Echo)**: Un dispositivo ESP32 que captura audio mediante un micrófono I2S, lo envía por WiFi a un servidor y muestra feedback visual en una pantalla OLED.
2.  **Servidor de Escritorio (Python)**: Una aplicación que recibe el audio, lo transcribe usando motores como **Vosk** o **Whisper**, y muestra el texto resultante en una ventana emergente (popup) en el escritorio.

El sistema funciona en modo "Push-to-Talk": mantienes presionado el botón del dispositivo para hablar, y el texto aparece en tu ordenador.

## Arquitectura

El programa sigue la siguiente arquitectura:

```
┌──────────────────┐      ┌─────────────────────────┐      ┌───────────────┐
│ M5Stack Atom Echo│      │   Servidor Python       │      │               │
│                  ├----->│ (main.py)               ├----->│  Popup GTK    │
│                  │ WiFi │                         │      │  (popup.py)   │
└──────────────────┘      └───────────┬─────────────┘      └───────────────┘
                                      │
                                      │
                         ┌────────────▼────────────┐
                         │ Motores de Transcripción│
                         │ (escritor.py)           │
                         │  - Vosk                 │
                         │  - Whisper (HuggingFace)│
                         └─────────────────────────┘
```

## Características

### Servidor de Escritorio (Python)
- **Motores de Transcripción Modulares**: Fácilmente extensible. Incluye implementaciones para:
  - **Vosk**: Ligero, rápido y funciona offline.
  - **Whisper**: Modelos de OpenAI (vía Hugging Face) para alta precisión, con soporte para GPU (CUDA).
- **Popup de Transcripción**: Una ventana GTK que aparece cerca del cursor del ratón mostrando el texto en tiempo real.
- **Detección de Pausa**: Finaliza automáticamente la transcripción tras un silencio.
- **Señal de Fin Explícita**: El cliente puede enviar `[END]` para finalizar la transcripción al instante.
- **Estilo Dinámico**: El popup se integra con el tema del sistema usando los colores de **Pywal** si están disponibles.

### Cliente Hardware (M5Stack Atom Echo)
- **Conectividad WiFi**: Se conecta a la red local para comunicarse con el servidor.
- **Modo Push-to-Talk**: La transmisión de audio se activa al presionar el botón integrado.
- **Configuración por Bluetooth (BLE)**: La primera vez, las credenciales de WiFi y la IP del servidor se configuran fácilmente desde una aplicación móvil genérica (como *nRF Connect*).
- **Feedback Visual en Pantalla OLED**:
  - **Animación de Inicio**: Secuencia de arranque con estética "retro-hacker".
  - **Estado de Conexión**: Iconos y texto animado para el estado de WiFi y la conexión con el servidor.
  - **Modo Reposo**: Animaciones de "Plasma" o "Matrix Rain" cuando no se está usando.
  - **Modo Grabación**: Un visualizador de espectro de audio en tiempo real.
- **Detección de Movimiento**: Utiliza un acelerómetro ADXL345 para detectar picos de movimiento (potencialmente para activar la pantalla o futuras interacciones).

---

## Ejecución

### 1. Servidor de Escritorio

**Requisitos:**
- Python 3.12+
- `uv` (un instalador y gestor de paquetes de Python ultrarrápido).
- Git
- Opcional: Una GPU NVIDIA con CUDA para un rendimiento óptimo con Whisper.

**Pasos:**

2.  **Crea y activa un entorno virtual con `uv`:**
    ```bash
    source .venv/bin/activate
    ```

3.  **Instala las dependencias:**
    Instálalas usando `uv`:
    ```bash
    uv pip install -r requirements.txt
    ```
4.  **Descarga un modelo para Vosk (si lo vas a usar):**
    - Descarga un modelo en español desde la [página de modelos de Vosk](https://alphacephei.com/vosk/models). Se recomienda el `vosk-model-small-es-0.42`.
    - Descomprímelo y coloca la carpeta en `src/models/`. La ruta final debería ser `src/models/vosk-model-es-0.42`.

5.  **Configura el motor a utilizar:**
    - Abre `src/main.py` y modifica la variable `ENGINE_CHOICE` a `'vosk'` o `'whisper'`.
    - Ajusta las constantes `VOSK_MODEL_PATH` o `WHISPER_MODEL_NAME` según corresponda.

6.  **Ejecuta el servidor:**
    ```bash
    python main.py
    ```
    El servidor empezará a escuchar en el puerto `8888`.

### 2. Cliente Hardware (M5Stack Atom Echo)

**Requisitos:**
- **Hardware**: M5Stack Atom Echo, una pantalla OLED SSD1306 (128x32) y un acelerómetro ADXL345.
- **Software**: Visual Studio Code con la extensión **PlatformIO**.

1.  **Configuración Inicial (vía Bluetooth):**
    - La primera vez que enciendas el dispositivo (o si mantienes presionado el botón `BOOT` durante el arranque), entrará en modo de configuración BLE.
    - Desde tu teléfono, usa una app como **nRF Connect for Mobile** o similar.
    - Busca un dispositivo llamado `Configurador_VoskClient` y conéctate.
    - El servicio te mostrará un esquema con los campos a rellenar (`ssid`, `pass`, `server`, `port`).
    - Escribe los datos de tu red WiFi, la IP del ordenador donde corre el servidor y el puerto (`8888`).
    - Al enviar los datos, el dispositivo los guardará y se reiniciará.


---

## Configuración

- `HOST`, `PORT`: Dirección y puerto de escucha del servidor.
- `SAMPLE_RATE`: Frecuencia de muestreo del audio (debe coincidir con la del cliente).
- `VOLUME_MULTIPLIER`: Amplificador de volumen de software para el audio recibido.
- `ENGINE_CHOICE`: Elige entre `'whisper'` o `'vosk'`.
- `VOSK_MODEL_PATH`: Ruta al modelo de Vosk.
- `WHISPER_MODEL_NAME`: Nombre del modelo de Whisper a descargar de Hugging Face (e.g., `'base'`, `'small'`, `'Drazcat/whisper-small-es'`).
- `WHISPER_LANGUAGE`: Idioma para la transcripción con Whisper.
- `TIMEOUT_PAUSA`: Segundos de silencio para considerar que la elocución ha terminado.

