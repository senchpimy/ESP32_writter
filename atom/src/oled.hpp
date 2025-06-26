#ifndef OLED_HPP
#define OLED_HPP

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>

// Configuración de pantalla
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C
#define I2C_SDA 25
#define I2C_SCL 21

// Duraciones de animaciones
#define NAVI_DURATION 5500
#define TERMINAL_DURATION 7000
#define LILY_DURATION 1000

// Instancia global de pantalla
extern Adafruit_SSD1306 display;
extern volatile bool g_mainSetupComplete;
extern volatile bool g_isRecording;
extern unsigned long ultimo;
extern bool bluetooth_config_in_progress;

// Funciones
int fastrand_display(void);
int interpo_pourcent(int min, int max, int v);
void drawNaviChar(int16_t x, int16_t y, unsigned char c);
void printNaviText(int16_t x, int16_t y, const char *str);
void drawQmkBitmap(int16_t x, int16_t y, const uint8_t *bitmap, int16_t w, int16_t h);
void move_block(int16_t x, int16_t y, int16_t w, int16_t h, int8_t shift);
void render_logo_clean(int16_t x, int16_t y);
void render_logo_glitch(int16_t x, int16_t y, int glitch_probability);
void draw_random_char_glitch(int16_t x, int16_t y, char final_char, int value);
void draw_startup_navi(unsigned long elapsedTime);
void draw_startup_terminal(unsigned long elapsedTime);
void draw_lily(unsigned long elapsedTime);
void displayTask(void *pvParameters);

#endif // OLED_HPP
