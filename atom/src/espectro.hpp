#pragma once

#include <Arduino.h>

// Número de muestras para FFT y frecuencia de muestreo
#define SAMPLES 512
#define SAMPLING_FREQUENCY 16000

// Configuración del área del espectro
#define TEXT_AREA_WIDTH 32
#define VISUALIZER_START_X TEXT_AREA_WIDTH
#define VISUALIZER_WIDTH (SCREEN_WIDTH - TEXT_AREA_WIDTH)
#define SCROLL_SPEED 2

// Configuración del espectro de bandas
#define NUM_BANDS 16
#define NOISE_FLOOR 900
#define MAX_MAGNITUDE 35000
#define WAVEFORM_SENSITIVITY 8000

// Declaración de funciones
void prepareDisplay();       // Inicializa pantalla, texto y marco
void dibujarEspectroUI();    // Dibuja el espectro y forma de onda
void selectNextRandomPhrase(); // Selecciona nueva frase japonesa aleatoria
