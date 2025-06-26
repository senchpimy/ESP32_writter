#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <navi_font_data.h>
#include <espectro.hpp>
#include <oled.hpp>
#include <matrix.hpp>
#include <plasma.hpp>
#include "bluetooth.hpp"

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C
#define I2C_SDA 25
#define I2C_SCL 21


//volatile bool g_mainSetupComplete = false;
//volatile bool g_isRecording = false;
static unsigned long g_seed_display = 0;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

int fastrand_display(void) {
  g_seed_display = (214013 * g_seed_display + 2531011);
  return (g_seed_display >> 16) & 0x7FFF; 
}

int interpo_pourcent(int min, int max, int v) {
  if (v <= min) return 0; if (v >= max) return 100;
  float x0 = min, x1 = max, y0 = 0, y1 = 100, xp = v;
  float yp = y0 + ((y1 - y0) / (x1 - x0)) * (xp - x0);
  return (int)yp;
}

void drawNaviChar(int16_t x, int16_t y, unsigned char c) { if (c > 127) return; const uint8_t* glyph = navi_font_map + c * 6; for (int8_t i = 0; i < 5; i++) { uint8_t line = pgm_read_byte(glyph + i); for (int8_t j = 0; j < 8; j++, line >>= 1) { if (line & 1) display.drawPixel(x + i, y + j, SSD1306_WHITE); } } }
void printNaviText(int16_t x, int16_t y, const char *str) { while (*str) { drawNaviChar(x, y, *str++); x += 6; } }

static const uint8_t PROGMEM raw_logo[] = {
    0, 0, 0, 0, 0, 0, 128, 128, 0, 0, 128, 128, 192, 192, 204, 222, 222, 204, 192, 192, 128,
    0, 0, 0, 128, 128, 0, 0, 0, 0, 0, 0, 192, 240, 248, 28, 14, 7, 3, 249, 252, 255, 15, 7, 
  3, 225, 241, 241, 241, 241, 225, 3, 7, 15, 255, 252, 249, 3, 7, 14, 28, 248, 240, 192, 192,
  227, 231, 206, 28, 56, 112, 99, 15, 31, 60, 120, 240, 225, 227, 3, 3, 227, 225, 240, 120, 
  60, 31, 15, 103, 112, 56, 28, 206, 231, 227, 192, 0, 1, 1, 0, 0, 0, 56, 120, 96, 192, 192,
  192, 96, 127, 63, 0, 0, 63, 127, 96, 192, 192, 192, 96, 120, 56, 0, 0, 0, 1, 1, 0,
};

void drawQmkBitmap(int16_t x, int16_t y, const uint8_t *bitmap, int16_t w, int16_t h) {
  int16_t pages = h / 8;
  if (h % 8 != 0) pages++;
  for (int16_t page = 0; page < pages; page++) {
    for (int16_t col = 0; col < w; col++) {
      uint8_t byte = pgm_read_byte(bitmap + page * w + col);
      for (int16_t bit = 0; bit < 8; bit++) {
        if (byte & (1 << bit)) {
          display.drawPixel(x + col, y + (page * 8) + bit, SSD1306_WHITE);
        }
      }
    }
  }
}

void move_block(int16_t x, int16_t y, int16_t w, int16_t h, int8_t shift) { if (shift == 0) return; uint8_t buffer[w * h]; for(int16_t i=0; i<w; ++i) { for (int16_t j=0; j<h; ++j) { buffer[j * w + i] = display.getPixel(x + i, y + j); } } display.fillRect(x, y, w, h, SSD1306_BLACK); for(int16_t i=0; i<w; ++i) { for (int16_t j=0; j<h; ++j) { if (buffer[j * w + i]) { display.drawPixel(x + i + shift, y + j, SSD1306_WHITE); } } } }

void render_logo_clean(int16_t x, int16_t y) {
    drawQmkBitmap(x, y, raw_logo, 32, 32);
}


void render_logo_glitch(int16_t x, int16_t y, int glitch_probability) {
    render_logo_clean(x, y);
    if ((fastrand_display() % 100) > glitch_probability) return;
    int glitch_index = 4 + (fastrand_display() % 7);
    switch (glitch_index) {
        case 4: move_block(x + 1, y + 11, 24, 3, 2); move_block(x + 2, y + 19, 14, 3, -2); break;
        case 5: move_block(x + 6, y + 25, 20, 7, 1); move_block(x + 0, y + 8, 32, 8, -1); break;
        case 6: move_block(x + 3, y + 7, 27, 4, -3); break;
        case 7: display.fillRect(x, y, 32, 32, SSD1306_INVERSE); break;
        case 8: for(int i=0; i<4; ++i) display.drawFastHLine(x, y + (fastrand_display()%32), 32, SSD1306_INVERSE); break;
        case 9: for (int i = 0; i < 32; i++) if ((fastrand_display() % 100) < 25) display.drawFastHLine(x, y + i, 32, SSD1306_WHITE); break;
        case 10: for (int i = 0; i < 70; i++) display.drawPixel(x + (fastrand_display()%32), y + (fastrand_display()%32), SSD1306_INVERSE); break;
    }
}

#define NAVI_DURATION 5500
#define TERMINAL_DURATION 7000
#define LILY_DURATION 1000

void draw_random_char_glitch(int16_t x, int16_t y, char final_char, int value) { if (value < 100) drawNaviChar(x, y, (fastrand_display() % 15) + 1); else drawNaviChar(x, y, final_char); }

void draw_startup_navi(unsigned long elapsedTime) {
  display.clearDisplay();
  int text_y1 = 2, text_y2 = 12, prompt_y = 24;
  printNaviText(5, text_y1, "HELL0");
  printNaviText(5, text_y2, "NAVI.");
  if ((elapsedTime / 400) % 2 == 0) printNaviText(5, prompt_y, ">"); else printNaviText(5, prompt_y, ">_");

  unsigned long frame = elapsedTime * 55 / NAVI_DURATION;
  uint8_t tres_shell = 15, tres_load  = 35;

  if (frame > tres_shell) {
    int inter_f = interpo_pourcent(tres_shell, tres_load, frame);
    int init_x_start = 5 + (6 * 2);
    draw_random_char_glitch(init_x_start, prompt_y, 'i', 60 + inter_f);
    draw_random_char_glitch(init_x_start + 6, prompt_y, 'n', 20 + inter_f);
    draw_random_char_glitch(init_x_start + 12, prompt_y, 'i', 0  + inter_f);
    draw_random_char_glitch(init_x_start + 18, prompt_y, 't', 20 + inter_f);
  }

  if (frame < tres_load) {
    render_logo_clean(94, 0);
  } else {
    int glitch_prob = interpo_pourcent(tres_load, 55, frame);
    render_logo_glitch(94, 0, glitch_prob);
  }
}

#define TERMINAL_LINE_MAX 4
const char *boot_ref[] = { "LT: OK", "RT: OK", "M: SYNC", "    ", "cnx: 2.4Ghz", "A0: 0.8V", "B0: 1.1V", "    ", "0x40 - chk", "0x60 - chk", "0x85 - chk", "0x0F - chk", "    ", "> run diag", "x: OK", "y: OK", "100%", "    ", "> world_load", "Kernel v1.3.37 boot...", "Matrix init... OK", " ", "LT: OK", "RT: OK", "M: SYNC", " ", "Loading modules...", "  [i2c]... synced", "  [oled]... active", "  [rgb]... loaded", "  [audio]... n/a", " ", "cnx: 2.4Ghz", "A0: 0.8V", "B0: 1.1V", " ", "Verifying checksum...", "  MEM_CHK: C4F1... OK", "0x40 - chk", "0x60 - chk", "0x85 - chk", "0x0F - chk", "0xA2 - chk", "0xB7 - chk", "0xE1 - chk", "0xFF - chk", " ", "> run diag", "  x: OK", "  y: OK", "  z: n/a", "  Result: 100%", " ", "> load_layout: FR_custom", "> set_layer: _QWERTY", " ", "GUI init...", "All systems nominal.", "Ready for input...", "> keymap_load: final" };
const int TERMINAL_LINE_NUMBER = sizeof(boot_ref) / sizeof(boot_ref[0]);
void draw_startup_terminal(unsigned long elapsedTime) {
  display.clearDisplay();
  //unsigned long f = elapsedTime * (TERMINAL_LINE_NUMBER + TERMINAL_LINE_MAX) / TERMINAL_DURATION;
  //uint8_t i_start = 0, i_nb_lines = f;
  //if (f > TERMINAL_LINE_MAX) { i_start = f - TERMINAL_LINE_MAX; i_nb_lines = TERMINAL_LINE_MAX; }
  //for (uint8_t i = 0; i < i_nb_lines; i++) {
  //  int line_index = i + i_start;
  //  if (line_index < TERMINAL_LINE_NUMBER) printNaviText(0, i * 8, boot_ref[line_index]);
  //}
}


void draw_lily(unsigned long elapsedTime) {
    display.clearDisplay();
    //for (int i = 0; i < 400; i++) {
    //    display.drawPixel(fastrand_display() % 128, fastrand_display() % 32, SSD1306_WHITE);
    //}
}

void prepareDisplay(); 

bool clean_screen = false;

void displayTask(void *pvParameters) {
  Serial.println("Display task running on core 0");
  Wire.begin(I2C_SDA, I2C_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("Error al iniciar pantalla OLED desde Tarea"));
    vTaskDelete(NULL);
    return;
  }
  g_seed_display = micros();

  unsigned long startTime;

  startTime = millis();
  while (millis() - startTime < NAVI_DURATION) { draw_startup_navi(millis() - startTime); display.display(); vTaskDelay(pdMS_TO_TICKS(10));}
  startTime = millis();
  while (millis() - startTime < TERMINAL_DURATION) { draw_startup_terminal(millis() - startTime); display.display(); vTaskDelay(pdMS_TO_TICKS(10));}
  startTime = millis();
  while (millis() - startTime < LILY_DURATION) { draw_lily(millis() - startTime); display.display(); vTaskDelay(pdMS_TO_TICKS(10));}

  //while (!g_mainSetupComplete) {
  //  display.clearDisplay();
  //  printNaviText(10, 12, "ESPERANDO SYS...");
  //  display.display();
  //  vTaskDelay(pdMS_TO_TICKS(100));
  //}
  prepareDisplay(); // Inicializa el espectro y las fuentes
  //
  while (true) {
    if (bluetooth_config_in_progress){
      Serial.println("Configuración Bluetooth en progreso, esperando conexión...");
      display.clearDisplay();
      draw_bluetooth_screen();
      continue;
    }
    if (g_isRecording) {
      display.clearDisplay();
      dibujarEspectroUI();
    } else {

      unsigned long tiempo_desde_pico = millis() - ultimo;
      if (tiempo_desde_pico>(100*1000)) {
        //clean display
        //TODO apagar display
        if (clean_screen) {
          clean_screen = false;
          display.clearDisplay();
        }
      }
      else if (tiempo_desde_pico>(40*1000)) {
        //standby display
        if (!clean_screen) {
          clean_screen = true;
          display.clearDisplay();
        }
        render_matrix_rain(); //debe de regresarse al estado original del display al momento de salir
        display.display();

      }else{
        //main display
        clean_screen = false;
        display.clearDisplay();
        render_plasma();
      }
    }
    display.display();
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}
