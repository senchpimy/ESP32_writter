#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <U8g2_for_Adafruit_GFX.h>
#include <oled.hpp>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1

#define MATRIX_CHAR_WIDTH 6
#define MATRIX_CHAR_HEIGHT 8
#define MATRIX_COLS_MAX (SCREEN_WIDTH / MATRIX_CHAR_WIDTH)   // Aprox. 21 columnas
#define MATRIX_ROWS_MAX (SCREEN_HEIGHT / MATRIX_CHAR_HEIGHT) // Aprox. 4 filas
#define MATRIX_FRAME_DURATION 10 

typedef struct {
    uint8_t x;    
    int8_t y;     
    uint8_t len;  
    uint8_t speed;
    uint8_t ticks;
    bool active;  
} MatrixDrop;

static MatrixDrop drops[MATRIX_COLS_MAX];
static unsigned long matrix_timer = 0;

//const char matrixChars[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
//const int numMatrixChars = sizeof(matrixChars) - 1; // -1 para no contar el caracter nulo '\0'


void reset_matrix_drop(MatrixDrop* drop) {
    drop->active = true;
    drop->y = -(random(10));          // Empieza en una posición Y negativa aleatoria
    drop->len = 2 + random(3);        // Longitud de 2 a 4 caracteres (la pantalla es corta)
    drop->speed = 1 + random(4);      // Velocidad aleatoria
    drop->ticks = 0;
}

void init_matrix_rain() {
    for (uint8_t i = 0; i < MATRIX_COLS_MAX; i++) {
        drops[i].active = false;
        drops[i].x = i; // Asigna una columna fija a cada gota
        if (random(10) < 3) {
            reset_matrix_drop(&drops[i]);
        }
    }
    matrix_timer = millis();
}


void init_animation() {
  //randomSeed(analogRead(32)); 
  randomSeed(23); 
  
  display.clearDisplay();
  
  display.setTextSize(1);
  display.cp437(true);

  init_matrix_rain(); 
}

bool firs_run = true;

void render_matrix_rain(void) {
  if (firs_run) {
    firs_run = false;
    init_animation();
  }
    
    if (millis() - matrix_timer < MATRIX_FRAME_DURATION) {
        return;
    }
    matrix_timer = millis();

    for (uint8_t i = 0; i < MATRIX_COLS_MAX; i++) {
        MatrixDrop* drop = &drops[i];

        if (!drop->active) {
            if (random(100) < 2) { // Probabilidad del 2% por fotograma
                reset_matrix_drop(drop);
            }
            continue; // Pasa a la siguiente gota
        }

        drop->ticks++;
        if (drop->ticks < drop->speed) {
            continue; // Esta gota específica aún no se mueve en este fotograma
        }
        drop->ticks = 0;

        uint16_t x_pos = drop->x * MATRIX_CHAR_WIDTH;

        // 1. Borra el último carácter de la cola (simula el desvanecimiento)
        int8_t tail_y_row = drop->y - drop->len;
        if (tail_y_row >= 0 && tail_y_row < MATRIX_ROWS_MAX) {
            display.fillRect(x_pos, tail_y_row * MATRIX_CHAR_HEIGHT, MATRIX_CHAR_WIDTH, MATRIX_CHAR_HEIGHT, SSD1306_BLACK);
        }

        // 2. Dibuja la "cabeza" de la gota (blanca y brillante)
        int8_t head_y_row = drop->y;
        if (head_y_row >= 0 && head_y_row < MATRIX_ROWS_MAX) {
            //display.setTextColor(SSD1306_WHITE);
            //display.setCursor(x_pos, head_y_row * MATRIX_CHAR_HEIGHT);
            //display.print(matrixChars[random(numMatrixChars)]);
            drawNaviChar(x_pos, head_y_row * MATRIX_CHAR_HEIGHT,(unsigned char) random(127));
        
        }

        // 3. Convierte la antigua cabeza en un carácter normal de la cola
        int8_t prev_head_y_row = drop->y - 1;
        if (prev_head_y_row >= 0 && prev_head_y_row < MATRIX_ROWS_MAX) {
            //display.setTextColor(SSD1306_WHITE); // En monocromo, el "gris" sigue siendo blanco
            //display.setCursor(x_pos, prev_head_y_row * MATRIX_CHAR_HEIGHT);
            //display.print(matrixChars[random(numMatrixChars)]);
            drawNaviChar(x_pos, prev_head_y_row * MATRIX_CHAR_HEIGHT,(unsigned char) random(127));
        }

        // 4. Mueve la gota hacia abajo
        drop->y++;

        // 5. Si la gota ha salido completamente de la pantalla, la desactiva
        if (tail_y_row >= MATRIX_ROWS_MAX) {
            drop->active = false;
        }
    }
}
