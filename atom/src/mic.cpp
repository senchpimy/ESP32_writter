#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>
#include "driver/i2s.h"

#define I2S_MIC_BCK_PIN  19
#define I2S_MIC_LRCK_PIN 33
#define I2S_MIC_DATA_IN_PIN 23

#define I2S_MIC_PORT     I2S_NUM_0

const int sampleRate = 16000;
const int bitsPerSample = 16;
const int bufferSize = 1024;

int16_t i2s_read_buffer[bufferSize / 2];

void setup_i2s_microphone() {
    esp_err_t err;
    i2s_driver_uninstall(I2S_MIC_PORT);

    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM),
        .sample_rate = sampleRate,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 64,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };

    err = i2s_driver_install(I2S_MIC_PORT, &i2s_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("Error instalando driver I2S: %d (%s)\n", err, esp_err_to_name(err));
        while (1);
    }
    Serial.println("Driver I2S instalado.");

    i2s_pin_config_t mic_pin_config = {
        .bck_io_num = I2S_MIC_BCK_PIN,
        .ws_io_num = I2S_MIC_LRCK_PIN,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_MIC_DATA_IN_PIN
    };

    err = i2s_set_pin(I2S_MIC_PORT, &mic_pin_config);
    if (err != ESP_OK) {
        Serial.printf("Error configurando pines I2S: %d (%s)\n", err, esp_err_to_name(err));
        while (1);
    }
    Serial.println("Pines I2S para micrófono configurados.");

    err = i2s_set_clk(I2S_MIC_PORT, sampleRate, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);
    if (err != ESP_OK) {
        Serial.printf("Error configurando reloj I2S (i2s_set_clk): %d (%s)\n", err, esp_err_to_name(err));
    } else {
        Serial.println("Reloj I2S (i2s_set_clk) configurado.");
    }

    i2s_zero_dma_buffer(I2S_MIC_PORT);
    Serial.println("I2S driver para micrófono completamente configurado.");
}

