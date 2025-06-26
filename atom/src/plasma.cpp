#include "network_handler.hpp"
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <U8g2_for_Adafruit_GFX.h>
#include <oled.hpp>
#include <plasma.hpp>
#include <WiFi.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32


// 1. Tabla para la distancia (evita sqrt y pow en el bucle principal)
float dist_lut[SCREEN_WIDTH][SCREEN_HEIGHT];

// 2. Tabla para el seno (evita la costosa función sin() en el bucle)
const int SINE_TABLE_SIZE = 256;
int8_t sine_table[SINE_TABLE_SIZE];

float plasma_time = 0.0;

// Función de inicialización para pre-calcular todo
void init_plasma() {
  Serial.println("Pre-calculando tablas para el efecto plasma...");

  const float center_x = SCREEN_WIDTH / 2.0f;
  const float center_y = SCREEN_HEIGHT / 2.0f;
  for (int x = 0; x < SCREEN_WIDTH; x++) {
    for (int y = 0; y < SCREEN_HEIGHT; y++) {
      float dx = x - center_x;
      float dy = y - center_y;
      dist_lut[x][y] = sqrt(dx * dx + dy * dy);
    }
  }

  for (int i = 0; i < SINE_TABLE_SIZE; i++) {
    float angle = (float)i / SINE_TABLE_SIZE * 2.0 * PI;
    sine_table[i] = (int8_t)(sin(angle) * 127.0f);
  }
  //Serial.println("Pre-cálculo completado.");
}

void prepare() {
  display.clearDisplay();
  init_plasma();
}

const int WINDOW_WIDTH_CHARS = 5;      // Ancho de la ventana en caracteres
const int CHAR_PIXEL_WIDTH = 6;        // Ancho de un carácter en píxeles (fuente tamaño 1)
const int SCROLL_SPEED_MS = 250;       // Velocidad del scroll (ms por carácter)
const int PAUSE_DURATION_MS = 2000;    // Duración de la pausa al final (2 segundos)
const int ENTER_SPEED_MS = 150;        // Velocidad de entrada (ms por carácter)

// --- Estados de la animación ---
enum AnimState { SCROLLING, PAUSING, ENTERING };

struct StateIcon {
    const unsigned char* bitmap;
    int width;
    int height;
};

//14x14
const unsigned char bitmap_wifi_connected [] = {
	0x33, 0x33, 0x33, 0x33, 0x73, 0xe3, 0xc7, 0x8e, 0x1c, 0x38, 0x70, 0xe0, 0xc0, 0x80, 0x33, 0x33, 
	0x07, 0x0e, 0x3c, 0x38, 0x01, 0x03, 0x3f, 0x3e, 0x00, 0x00, 0x3f, 0x3f
};

// 'antena', 12x15px
const unsigned char bitmap_antena [] = {
	0x83, 0xe3, 0xf4, 0xe8, 0xd4, 0xa2, 0x42, 0x81, 0x01, 0x81, 0x62, 0x1c, 0x43, 0x65, 0x6b, 0x6b, 
	0x6b, 0x65, 0x75, 0x3a, 0x5d, 0x6e, 0x6f, 0x60
};

// 'no_wifi', 15x15px
const unsigned char bitmap_no_wifi [] = {
	0x00, 0x33, 0x33, 0x33, 0x33, 0x73, 0xe3, 0xc7, 0xee, 0xfc, 0x78, 0x7c, 0xee, 0xc7, 0x83, 0x60, 
	0x73, 0x3b, 0x1f, 0x0e, 0x3f, 0x3b, 0x03, 0x03, 0x3f, 0x3e, 0x00, 0x00, 0x3f, 0x3f
};

// 'cadena', 20x15
const unsigned char server_desconectado [] PROGMEM = {
	0x0c, 0x0c, 0x0c, 0x0c, 0x1c, 0x3c, 0xf8, 0xf0, 0x00, 0x00, 0x00, 0x00, 0xf0, 0xf8, 0x3c, 0x1c, 
	0x0c, 0x0c, 0x0c, 0x0c, 0x18, 0x18, 0x18, 0x18, 0x1c, 0x1e, 0x0f, 0x07, 0x00, 0x00, 0x00, 0x00, 
	0x07, 0x0f, 0x1e, 0x1c, 0x18, 0x18, 0x18, 0x18
};

// 'conectado', 15x14px
const unsigned char server_conectado [] PROGMEM = {
	0xff, 0x56, 0xae, 0x56, 0xfe, 0xff, 0x00, 0xff, 0xe4, 0xe5, 0xe5, 0xe5, 0xe5, 0xe4, 0xff, 0x3f, 
	0x3f, 0x3f, 0x3f, 0x3f, 0x3f, 0x00, 0x3f, 0x3f, 0x3f, 0x3f, 0x3f, 0x3f, 0x2f, 0x3f
};

StateIcon connected_icon = { bitmap_wifi_connected, 14, 14 };
StateIcon no_wifi_icon = { bitmap_no_wifi, 15, 15 };
StateIcon antenna_icon = { bitmap_antena, 12, 15 };

StateIcon server_desconectado_icon = { server_desconectado, 20, 15 };
StateIcon server_conectado_icon = { server_conectado, 15, 14 };

String getAnimatedText(
    const String& full_text,
    AnimState& anim_state,
    int& scroll_index,
    unsigned long& last_update_time,
    String& last_text_cache,
    unsigned long current_time,
    const int window_width_chars) 
{
    if (full_text != last_text_cache) {
        last_text_cache = full_text;
        anim_state = ENTERING;
        scroll_index = 0;
        last_update_time = current_time;
    }

    String text_to_display = "";

    switch (anim_state) {
        case ENTERING: {
            if (current_time - last_update_time > ENTER_SPEED_MS) {
                scroll_index++;
                last_update_time = current_time;
            }
            text_to_display = last_text_cache.substring(0, scroll_index);
            
            if (scroll_index >= window_width_chars || scroll_index >= last_text_cache.length()) {
                if (last_text_cache.length() > window_width_chars) {
                    anim_state = SCROLLING; // Si el texto es largo, empieza a desplazar
                } else {
                    anim_state = PAUSING; // Si es corto, solo pausa
                }
                scroll_index = 0;
            }
            break;
        }

        case SCROLLING: {
            if (current_time - last_update_time > SCROLL_SPEED_MS) {
                scroll_index++;
                last_update_time = current_time;
            }
            text_to_display = last_text_cache.substring(scroll_index, scroll_index + window_width_chars);

            if (scroll_index + window_width_chars >= last_text_cache.length()) {
                anim_state = PAUSING;
                last_update_time = current_time; 
            }
            break;
        }

        case PAUSING: {
            if (last_text_cache.length() > window_width_chars) {
                text_to_display = last_text_cache.substring(last_text_cache.length() - window_width_chars);
            } else {
                text_to_display = last_text_cache;
            }
            
            if (current_time - last_update_time > PAUSE_DURATION_MS) {
                anim_state = ENTERING;
                scroll_index = 0; 
            }
            break;
        }
    }
    return text_to_display;
}

//int retry=10000;
//bool retry_example=true;

void mostrarEstadoWifiAnimado() {
    static AnimState wifi_anim_state = ENTERING;
    static int wifi_scroll_index = 0;
    static unsigned long wifi_last_update_time = 0;
    static String wifi_last_text_cache = "";

    static AnimState server_anim_state = ENTERING;
    static int server_scroll_index = 0;
    static unsigned long server_last_update_time = 0;
    static String server_last_text_cache = "";
    
    unsigned long current_time = millis();

    const int16_t TEXT_HEIGHT = 8;
    const int16_t Y_SSID = SCREEN_HEIGHT - TEXT_HEIGHT;
    const int16_t X_SSID = 0;

    String full_wifi_text = WiFi.isConnected() ? WiFi.SSID() : "Sin Conexion WiFi";
    
    String wifi_text_to_display = getAnimatedText(
        full_wifi_text, 
        wifi_anim_state, 
        wifi_scroll_index, 
        wifi_last_update_time, 
        wifi_last_text_cache, 
        current_time, 
        WINDOW_WIDTH_CHARS
    );
    
    const int16_t RECT_WIDTH_WIFI = WINDOW_WIDTH_CHARS * CHAR_PIXEL_WIDTH;
    display.fillRect(X_SSID, Y_SSID, RECT_WIDTH_WIFI, TEXT_HEIGHT, BLACK);
    display.setTextSize(1);
    printNaviText(X_SSID, Y_SSID, wifi_text_to_display.c_str());

  //if (retry_example){

  //if (retry > 0) {
  //  retry--;}
  //else{
  //  //const char* ssid = "INFINITUM8BAF";
  //  //const char* password = "HfWnWge44q";
  //  //  Serial.println("Reintentando conexión WiFi...");
  //  //  try_connect_wifi((char*)ssid, (char*)password);
  //  //  Reintentar la coneccion de se debe hacer en el loop principal
  //    try_connection = true;
  //    Serial.println("Reintentando conexión WiFi...Desde plasma.cpp");
  //    retry_example = false; // Evitar reintentos infinitos

  //  }
  //}

    StateIcon *wifi_icon = nullptr;
    if (WiFi.isConnected()) {
        wifi_icon = &connected_icon;
    //} else {
    } else if (trying_to_connect){
        wifi_icon = &antenna_icon;
    } else if (WiFi.status() == WL_NO_SSID_AVAIL || WiFi.status() == WL_DISCONNECTED) {
        wifi_icon = &no_wifi_icon;
    }
    int wifi_x = 4;
    int wifi_y = 4;
    display.fillRect(wifi_x - 2, wifi_y - 2, wifi_icon->width + 2, wifi_icon->height + 2, BLACK);
    drawQmkBitmap(wifi_x, wifi_y, wifi_icon->bitmap, wifi_icon->width, wifi_icon->height);

    StateIcon *server_icon = nullptr;
    String full_server_text = "";
    if (client.connected()) {
        server_icon = &server_conectado_icon;
        full_server_text = "Servidor Conectado";
    } else {
        server_icon = &server_desconectado_icon;
        full_server_text = "Servidor Desconectado";
    }

    int server_icon_x = SCREEN_WIDTH - server_icon->width - 7;
    int server_icon_y = 4;
    display.fillRect(server_icon_x - 2, server_icon_y - 2, server_icon->width + 4, server_icon->height + 4, BLACK);
    drawQmkBitmap(server_icon_x, server_icon_y, server_icon->bitmap, server_icon->width, server_icon->height);

    const int SERVER_TEXT_X = 96;
    const int SERVER_TEXT_MAX_WIDTH = 30;
    const int SERVER_WINDOW_WIDTH_CHARS = SERVER_TEXT_MAX_WIDTH / CHAR_PIXEL_WIDTH;
    const int SERVER_TEXT_Y = 24;

    String server_text_to_display = getAnimatedText(
        full_server_text,
        server_anim_state,
        server_scroll_index,
        server_last_update_time,
        server_last_text_cache,
        current_time,
        SERVER_WINDOW_WIDTH_CHARS
    );

    display.fillRect(SERVER_TEXT_X, SERVER_TEXT_Y, SERVER_TEXT_MAX_WIDTH, TEXT_HEIGHT, BLACK);
    printNaviText(SERVER_TEXT_X, SERVER_TEXT_Y, server_text_to_display.c_str());
}

bool first_run = true;


void render_plasma() {
  if (first_run) {
    prepare();
    first_run = false;
  }

  plasma_time += 0.05;

  const float time_div_2 = plasma_time / 2.0f;
  const float time_div_3 = plasma_time / 3.0f;
  const float time_mul_10 = plasma_time * 10.0f;
  
  const uint8_t time_idx_2 = (uint8_t)(fmod(time_div_2, 2.0 * PI) / (2.0 * PI) * SINE_TABLE_SIZE);
  const uint8_t time_idx_3 = (uint8_t)(fmod(time_div_3, 2.0 * PI) / (2.0 * PI) * SINE_TABLE_SIZE);

  const float inv_x_freq = 1.0f / (8.0f + (sine_table[time_idx_2] / 127.0f) * 2.0f);
  const float inv_y_freq = 1.0f / (6.0f + (sine_table[time_idx_3] / 127.0f) * 3.0f);
  
  uint8_t *buffer = display.getBuffer();

  for (int y = 0; y < SCREEN_HEIGHT; y++) {
    for (int x = 0; x < SCREEN_WIDTH; x++) {
      
      const float dist_val = dist_lut[x][y];
      
      uint8_t idx1 = (uint8_t)(fmod(dist_val / 8.0f, 2.0 * PI) / (2.0 * PI) * SINE_TABLE_SIZE);
      uint8_t idx2 = (uint8_t)(fmod(x * inv_x_freq, 2.0 * PI) / (2.0 * PI) * SINE_TABLE_SIZE);
      uint8_t idx3 = (uint8_t)(fmod(y * inv_y_freq, 2.0 * PI) / (2.0 * PI) * SINE_TABLE_SIZE);
      uint8_t idx4 = (uint8_t)(fmod((x + y + time_mul_10) / 6.0f, 2.0 * PI) / (2.0 * PI) * SINE_TABLE_SIZE);
      
      int total_value = sine_table[idx1] + sine_table[idx2] + sine_table[idx3] + sine_table[idx4];

      if (sine_table[(uint8_t)(total_value) & (SINE_TABLE_SIZE - 1)] > 40) { // Umbral: 40 ~ sin(0.3) * 127
        buffer[x + (y / 8) * SCREEN_WIDTH] |= (1 << (y & 7));
      } else {
        buffer[x + (y / 8) * SCREEN_WIDTH] &= ~(1 << (y & 7));
      }
    }
  }
  mostrarEstadoWifiAnimado();
}

