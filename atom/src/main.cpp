#include "acelerometer.hpp"
#include "bluetooth.hpp"
#include "driver/i2s.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "mic.hpp"
#include "network_handler.hpp"
#include "oled.hpp"
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <Wire.h>

Preferences preferences;

unsigned long ultimo = millis();
volatile bool g_isRecording = false;
volatile bool g_mainSetupComplete = false;

const int bufferSizeSamples = 1024;
const int bufferSizeBytes = bufferSizeSamples * sizeof(int16_t);
int16_t audio_buffer_1[bufferSizeSamples];
int16_t audio_buffer_2[bufferSizeSamples];
volatile int16_t *display_buffer = nullptr;

SemaphoreHandle_t bufferMutex;
TaskHandle_t displayTaskHandle = NULL;

char ssid[64] = "";
char password[64] = "";
// const char* server_ip [64] = "192.168.1.79";
char server_ip[64] = "";
// const uint16_t server_port = 8888;
uint16_t server_port = -1;

#define BUTTON_PIN 39
#define CONFIG_PIN G23 // Botón BOOT para forzar modo config
#define DEBUG

WiFiClient client;
bool trasmissione_attiva = false;

bool trying_to_connect = false;

bool loadCredentials() {
  preferences.begin("net-creds", true);
  String savedSsid = preferences.getString("ssid", "");
  String savedPass = preferences.getString("pass", "");
  String savedIp = preferences.getString("ip", "");
  int savedPort = preferences.getInt("port", -1);
  preferences.end();
  if (savedSsid.length() > 0) {
    strcpy(ssid, savedSsid.c_str());
    strcpy(password, savedPass.c_str());
    strcpy(server_ip, savedIp.c_str());
    server_port = savedPort;
    Serial.println("Credenciales WiFi cargadas en memoria.");
    return true;
  }
  Serial.println("No hay credenciales WiFi guardadas.");
  return false;
  preferences.clear();
}

bool bluetooth_config_in_progress = false;

void setup() {
  Serial.begin(115200);
  delay(100);

  bluetooth_config_in_progress = !loadCredentials();

#ifdef DEBUG
#else
  xTaskCreatePinnedToCore(displayTask, "DisplayTask", 10000, NULL, 1,
                          &displayTaskHandle, 0);
#endif

  if (bluetooth_config_in_progress) {
    Serial.println("Modo configuración BLE activado. Presione el botón BOOT "
                   "para reiniciar en modo configuración.");
    setupBLE();
    bluetooth_config_in_progress = true;
    while (true) {
      delay(1000);
    }
  }

  Serial.println("Iniciando ESP32 Atom Echo Vosk Client (Core 1)...");

  bufferMutex = xSemaphoreCreateMutex();
  if (bufferMutex == NULL) {
    Serial.println("Error fatal creando el mutex!");
  }

  display_buffer = audio_buffer_1;

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(CONFIG_PIN, INPUT_PULLUP);

  setup_i2s_microphone();

  Serial.println("Setup principal (Core 1) completado.");
  g_mainSetupComplete = true;
#ifdef DEBUG
#else
  init_accelerometer();
#endif
}

bool try_connection = true;
bool new_credential = false;
unsigned long presionado_boton_configuracion = millis();
int prev_state_btn = 0;

void loop() {
#ifdef DEBUG
#else
  int medida = digitalRead(CONFIG_PIN);
  if (prev_state_btn == 0 && medida == 1) {
    presionado_boton_configuracion = millis();
  }

  if (medida == 0) {
    presionado_boton_configuracion = millis();
  }

  if (medida == 1 && (millis() - presionado_boton_configuracion) > 3000) {
    Serial.println("Botón de configuración presionado durante más de 5 "
                   "segundos. Reiniciando en modo configuración BLE...");
    // preferences.begin("net-creds", false);
    // preferences.clear();
    // preferences.end();
    delay(100);
    setupBLE();
    bluetooth_config_in_progress = true;
    while (!new_credential) {
      delay(1000);
    }
    try_connection = true;  // Forzar reconexión al servidor
    new_credential = false; // Reiniciar el estado de nueva credencial
  }
  prev_state_btn = medida;
#endif

  if (try_connection) {
    Serial.println("Intentando conectar al servidor...");
    try_connect_wifi((char *)ssid, (char *)password);

    if (WiFi.isConnected()) {
      Serial.println("Conectado al WiFi, intentando conectar al servidor...");
      manageClientConnection(client, server_ip, server_port,
                             trasmissione_attiva, g_isRecording);
    } else {
      Serial.println(
          "No se pudo conectar al WiFi, no se intentará conectar al servidor.");
    }
    try_connection = false;
  }

  bool bottone_premuto = (digitalRead(BUTTON_PIN) == LOW);

  if (bottone_premuto && client.connected()) {
    if (!trasmissione_attiva) {
      trasmissione_attiva = true;
      g_isRecording = true;
    }

    int16_t *capture_buffer =
        (display_buffer == audio_buffer_1) ? audio_buffer_2 : audio_buffer_1;

    size_t bytes_read = 0;
    esp_err_t result =
        i2s_read(I2S_MIC_PORT, (char *)capture_buffer, bufferSizeBytes,
                 &bytes_read, pdMS_TO_TICKS(100));

    if (result == ESP_OK && bytes_read > 0) {
#ifdef DEBUG
#else
      if (xSemaphoreTake(bufferMutex, portMAX_DELAY) == pdTRUE) {
        display_buffer = capture_buffer;
        xSemaphoreGive(bufferMutex);
      }
#endif

      if (client.connected()) {
        size_t bytes_sent =
            client.write((const uint8_t *)capture_buffer, bytes_read);
        if (bytes_sent != bytes_read) {
          Serial.printf(
              "Error enviando datos: %d de %d bytes enviados. Desconectando.\n",
              bytes_sent, bytes_read);
          client.stop();
          trasmissione_attiva = false;
          g_isRecording = false;
        }
      } else {
        Serial.println("Cliente no conectado, no se envían datos. Deteniendo "
                       "transmisión.");
        trasmissione_attiva = false;
        g_isRecording = false;
      }
    } else if (result != ESP_OK) {
      Serial.printf("Error leyendo de I2S: %d (%s), bytes leídos: %d\n", result,
                    esp_err_to_name(result), bytes_read);
    }
  } else {
    if (trasmissione_attiva) {
      Serial.println("Botón soltado o cliente desconectado, deteniendo "
                     "transmisión de audio.");
      trasmissione_attiva = false;
      g_isRecording = false;
    }
    delay(50);
  }
#ifdef DEBUG

#else
  bool result = read_accelerometer_data();
  unsigned long tiempo_desde_pico = millis() - ultimo;
  if (result) {
    ultimo = millis();
    Serial.println("Pico detectado en el acelerómetro.");
  }
#endif
}
