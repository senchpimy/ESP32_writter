#include <Arduino.h>
#include <Wire.h>          // Para la comunicación I2C
#include <cmath>           // Para las funciones matemáticas sqrt() y pow()
#include <acelerometer.hpp>

#include <Adafruit_Sensor.h>
#include <Adafruit_ADXL345_U.h>

#define I2C_SDA_PIN 25
#define I2C_SCL_PIN 21

float g_buffer[WINDOW_SIZE];
int buffer_index = 0;
bool buffer_filled = false;

Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);

float calculate_mean(float arr[], int size) {
  float sum = 0.0;
  for (int i = 0; i < size; i++) {
    sum += arr[i];
  }
  return sum / size;
}

auto ultima_medicion = millis();

float calculate_stdev(float arr[], int size, float mean) {
  float sq_diff_sum = 0.0;
  for (int i = 0; i < size; i++) {
    sq_diff_sum += pow(arr[i] - mean, 2);
  }
  float variance = sq_diff_sum / size;
  return sqrt(variance);
}

void init_accelerometer() {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

  if (!accel.begin()) {
    Serial.println("¡Error! No se pudo encontrar un sensor ADXL345. Revisa las conexiones.");
    while (1) { delay(10); }
  }

  accel.setRange(ADXL345_RANGE_4_G);
  Serial.println("Sensor listo. Esperando picos de aceleración...");
  Serial.println("-------------------------------------------------");
}

bool read_accelerometer_data() {
  if (millis() - ultima_medicion < 50) {
    return false; // Espera al menos 50 ms entre lecturas
  }
  ultima_medicion = millis();
  sensors_event_t event;
  accel.getEvent(&event);

  float x = event.acceleration.x;
  float y = event.acceleration.y;
  float z = event.acceleration.z;

  float total_accel_ms2 = sqrt(pow(x, 2) + pow(y, 2) + pow(z, 2));
  float total_accel_g = total_accel_ms2 / SENSORS_GRAVITY_STANDARD;

  g_buffer[buffer_index] = total_accel_g;
  buffer_index++;

  if (!buffer_filled && buffer_index >= WINDOW_SIZE) {
    buffer_filled = true;
  }
  
  if (buffer_index >= WINDOW_SIZE) {
    buffer_index = 0;
  }

  if (buffer_filled) {
    float mean = calculate_mean(g_buffer, WINDOW_SIZE);
    float stdev = calculate_stdev(g_buffer, WINDOW_SIZE, mean);

    if (stdev > 0.01) {
      float z_score = abs(total_accel_g - mean) / stdev;

      if ((z_score - Z_SCORE_THRESHOLD)>1.0) {
        Serial.print("--- ¡PICO DETECTADO! Valor: ");
        Serial.print(total_accel_g, 2);
        Serial.print(" G (Z-Score: ");
        Serial.print(z_score, 2);
        Serial.println(") ---");
        //Serial.print("Valores Z");
        //Serial.print("z_score: ");
        //Serial.print(z_score, 2);
        //Serial.print(" | Media: ");
        //Serial.print(mean, 2);
        //Serial.print(" | Desviación estándar: ");
        //Serial.println(stdev, 2);
        //Serial.print("Diferencia: ");
        //Serial.print(z_score - Z_SCORE_THRESHOLD, 2);
        //Serial.println(" G");
        return  true;
      }
    }
  }
  return false;

}
