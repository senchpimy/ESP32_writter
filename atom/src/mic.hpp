#pragma once

#include <Arduino.h>
#include "driver/i2s.h"

#define I2S_MIC_BCK_PIN    19
#define I2S_MIC_LRCK_PIN   33
#define I2S_MIC_DATA_IN_PIN 23

#define I2S_MIC_PORT       I2S_NUM_0

const int sampleRate = 16000;
const int bitsPerSample = 16;
const int bufferSize = 1024;

extern int16_t i2s_read_buffer[bufferSize / 2];

void setup_i2s_microphone();
//extern bool read_ready=false;
extern bool read_ready;
