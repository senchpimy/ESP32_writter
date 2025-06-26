// accelerometer.hpp

#ifndef ACCELEROMETER_HPP
#define ACCELEROMETER_HPP

#include <Adafruit_ADXL345_U.h>

const int WINDOW_SIZE = 30;
const float Z_SCORE_THRESHOLD = 2.0;
extern unsigned long ultimo;


extern Adafruit_ADXL345_Unified accel;
extern float g_buffer[WINDOW_SIZE];


void init_accelerometer();

bool read_accelerometer_data();

#endif
