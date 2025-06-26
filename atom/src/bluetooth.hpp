#ifndef BLE_CONFIG_HPP
#define BLE_CONFIG_HPP

#include <Arduino.h> // Necesario para tipos como Serial, delay, etc.
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <Preferences.h>
#include <ArduinoJson.h>

#define SERVICE_UUID "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define SCHEMA_CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define DATA_CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a9"

extern char ssid[64] ;
extern char password[64] ;
extern bool new_credential;

extern Preferences preferences;

class DataCharacteristicCallbacks : public BLECharacteristicCallbacks {
public:
    void onWrite(BLECharacteristic *pCharacteristic) override;
};

class MyServerCallbacks : public BLEServerCallbacks {
public:
    void onConnect(BLEServer* pServer) override;
    void onDisconnect(BLEServer* pServer) override;
};

void setupBLE();

void draw_bluetooth_screen();

#endif // BLE_CONFIG_HPP
