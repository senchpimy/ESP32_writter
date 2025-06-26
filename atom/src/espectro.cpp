#include "driver/i2s.h"
#include "mic.hpp"
#include "oled.hpp"
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>
#include <U8g2_for_Adafruit_GFX.h>
#include <Wire.h>
#include <arduinoFFT.h>
#include "freertos/semphr.h"

// --- Acceso a variables globales de main.cpp ---
extern volatile int16_t* display_buffer;
extern SemaphoreHandle_t bufferMutex;
// ----------------------------------------------

U8G2_FOR_ADAFRUIT_GFX u8g2_for_adafruit_gfx;

#define TEXT_AREA_WIDTH 32
#define VISUALIZER_START_X TEXT_AREA_WIDTH
#define VISUALIZER_WIDTH (SCREEN_WIDTH - TEXT_AREA_WIDTH)
#define SCROLL_SPEED 2

// Asegúrate de que SAMPLES no sea mayor que bufferSizeSamples en main.cpp
#define SAMPLES 512
#define SAMPLING_FREQUENCY 16000
double vReal[SAMPLES];
double vImag[SAMPLES];
ArduinoFFT<double> FFT =
    ArduinoFFT<double>(vReal, vImag, SAMPLES, SAMPLING_FREQUENCY);

// Búfer local para procesar los datos de forma segura
int16_t local_processing_buffer[SAMPLES];

#define NUM_BANDS 16
#define NOISE_FLOOR 900
#define MAX_MAGNITUDE 35000
#define WAVEFORM_SENSITIVITY 8000

const char *japanesePhrases[] = {
    "オーディオスペクトラム", "音楽は力", "M5Stack Atom", "こんにちは世界", 
    "音の波形", "マイクロフォン入力", "お前はイケてないよ、兄弟", "俺は純粋なパフォーマンスだ", "ケツを食べる"
};
const int numPhrases = sizeof(japanesePhrases) / sizeof(japanesePhrases[0]);
int currentPhraseIndex = -1;
const char *currentScrollText;
int text_width = 0;
int scroll_x_pos = 0;

void selectNextRandomPhrase() {
  int newIndex = random(numPhrases);
  while (newIndex == currentPhraseIndex) {
    newIndex = random(numPhrases);
  }
  currentPhraseIndex = newIndex;
  currentScrollText = japanesePhrases[currentPhraseIndex];
  text_width = u8g2_for_adafruit_gfx.getUTF8Width(currentScrollText);
  text_width -= 10;
  scroll_x_pos = TEXT_AREA_WIDTH;
}

void prepareDisplay() {
  u8g2_for_adafruit_gfx.begin(display);
  u8g2_for_adafruit_gfx.setFont(u8g2_font_wqy12_t_gb2312);
  randomSeed(analogRead(32));
  selectNextRandomPhrase();
  display.clearDisplay();
  display.display();
}

void dibujarEspectroUI() {
  // 1. Bloquear el mutex para acceder de forma segura a `display_buffer`
  if (xSemaphoreTake(bufferMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
      // 2. Copiar rápidamente los datos al búfer local
      memcpy(local_processing_buffer, (const void*)display_buffer, SAMPLES * sizeof(int16_t));
      
      // 3. Liberar el mutex INMEDIATAMENTE después de copiar
      xSemaphoreGive(bufferMutex);
  } else {
      // No se pudo obtener el mutex a tiempo.
      // Es mejor saltarse un frame que bloquear la pantalla o causar inestabilidad.
      return; 
  }

  // 4. AHORA, todo el procesamiento se hace con el búfer local 'local_processing_buffer'
  // Es 100% seguro porque la tarea principal ya no puede modificar estos datos.
  for (int i = 0; i < SAMPLES; i++) {
    vReal[i] = (double)local_processing_buffer[i];
    vImag[i] = 0.0;
  }
  FFT.windowing(FFT_WIN_TYP_HAMMING, FFT_FORWARD);
  FFT.compute(FFT_FORWARD);
  FFT.complexToMagnitude();

  display.clearDisplay();

  u8g2_for_adafruit_gfx.setForegroundColor(SSD1306_WHITE);
  u8g2_for_adafruit_gfx.setCursor(scroll_x_pos, 30);
  u8g2_for_adafruit_gfx.print(currentScrollText);
  display.fillRect(VISUALIZER_START_X, 0, VISUALIZER_WIDTH, SCREEN_HEIGHT, SSD1306_BLACK);

  scroll_x_pos -= SCROLL_SPEED;
  if (scroll_x_pos < -(text_width + 5)) {
    selectNextRandomPhrase();
  }

  display.drawRoundRect(VISUALIZER_START_X, 0, VISUALIZER_WIDTH, SCREEN_HEIGHT, 8, SSD1306_WHITE);
  int bar_width = VISUALIZER_WIDTH / NUM_BANDS;
  for (int i = 1; i < NUM_BANDS; i++) {
    int start_bin = i * (SAMPLES / 2 / NUM_BANDS);
    int end_bin = (i + 1) * (SAMPLES / 2 / NUM_BANDS);
    double band_magnitude = 0;
    for (int j = start_bin; j < end_bin; j++) {
      if (vReal[j] > band_magnitude)
        band_magnitude = vReal[j];
    }
    if (band_magnitude < NOISE_FLOOR)
      band_magnitude = 0;
    int bar_height = map(band_magnitude, NOISE_FLOOR, MAX_MAGNITUDE, 0, SCREEN_HEIGHT - 2);
    bar_height = constrain(bar_height, 0, SCREEN_HEIGHT - 2);
    int start_x = VISUALIZER_START_X + ((i - 1) * bar_width);
    for (int dx = 0; dx < bar_width - 1; dx++) {
      for (int dy = 0; dy < bar_height; dy++) {
        int current_x = start_x + dx;
        int current_y = SCREEN_HEIGHT - 2 - dy;
        if ((current_x + current_y) % 2 == 0) {
          display.drawPixel(current_x, current_y, SSD1306_WHITE);
        }
      }
    }
  }

  int prev_plot_x = 0;
  int prev_y = SCREEN_HEIGHT / 2 - 5;
  for (int plot_x = 25; plot_x < VISUALIZER_WIDTH; plot_x++) {
    int sample_index = map(plot_x, 0, VISUALIZER_WIDTH, 0, SAMPLES);
    // Usar el búfer local para dibujar la forma de onda
    int y = map(local_processing_buffer[sample_index], -WAVEFORM_SENSITIVITY, WAVEFORM_SENSITIVITY, 1, SCREEN_HEIGHT - 2);
    y = constrain(y, 1, SCREEN_HEIGHT - 2);
    display.drawLine(VISUALIZER_START_X + prev_plot_x, prev_y, VISUALIZER_START_X + plot_x, y, SSD1306_WHITE);
    prev_plot_x = plot_x;
    prev_y = y;
  }

  // El delay ya está en la tarea principal de la pantalla, no es necesario aquí.
  // display.display() se llama desde la tarea de la pantalla.
}
