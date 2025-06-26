#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include "bluetooth.hpp"
#include "oled.hpp"

// 'luna', 30x38px
const unsigned char luna [] PROGMEM = {
	0x08, 0x08, 0x1c, 0x7f, 0x1c, 0x08, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
	0x00, 0x20, 0x00, 0x00, 0x00, 0x20, 0x20, 0x70, 0xd8, 0x8e, 0xd8, 0x70, 0x20, 0x20, 0x10, 0x00, 
	0x00, 0x80, 0x40, 0xa0, 0xf0, 0x70, 0xf8, 0xd8, 0xec, 0xec, 0xdc, 0xfc, 0xfc, 0xfc, 0xfc, 0x9c, 
	0x9c, 0x18, 0x38, 0xf0, 0x70, 0x60, 0xc0, 0x83, 0x00, 0x00, 0x10, 0x00, 0x00, 0x04, 0x01, 0x20, 
	0x23, 0x2b, 0x5d, 0xb7, 0xff, 0xf9, 0xf9, 0x8f, 0xe7, 0x73, 0x73, 0x73, 0x87, 0xff, 0xfd, 0xf3, 
	0xff, 0xf3, 0xe3, 0xe7, 0xff, 0xff, 0xff, 0xfc, 0xf0, 0x00, 0x00, 0x20, 0x46, 0x0c, 0x08, 0x20, 
	0x20, 0xf0, 0xff, 0x3f, 0x97, 0x0b, 0x0b, 0x0a, 0x16, 0x2f, 0x9f, 0x9c, 0xfc, 0xf3, 0x73, 0xff, 
	0xe7, 0x67, 0x1f, 0xcf, 0xeb, 0x3f, 0x0f, 0x00, 0x10, 0x00, 0x00, 0x00, 0x02, 0x04, 0x00, 0x00, 
	0x01, 0x00, 0x01, 0x23, 0x02, 0x22, 0x00, 0x00, 0x00, 0x01, 0x09, 0x05, 0x05, 0x01, 0x00, 0x00, 
	0x02, 0x01, 0x00, 0x00, 0x20, 0x00
};

void draw_bluetooth_screen(){
  drawQmkBitmap(0, 0, luna, 30, 38);
  display.display();
  delay(1000);
}


#define SERVICE_UUID "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define SCHEMA_CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define DATA_CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a9"

void DataCharacteristicCallbacks::onWrite(BLECharacteristic *pCharacteristic) {
    std::string value = pCharacteristic->getValue();
    if (!value.empty()) {
        JsonDocument doc;
        if (deserializeJson(doc, value) == DeserializationError::Ok) {
            const char* newSsid = doc["ssid"];
            const char* newPass = doc["pass"];
            const char* newServerIp = doc["server"];
            int newServerPort = doc["port"];
            Serial.println("Datos recibidos:");
            Serial.printf("SSID: %s\n", newSsid);
            Serial.printf("Contraseña: %s\n", newPass);
            Serial.printf("IP del servidor: %s\n", newServerIp);
            Serial.printf("Puerto del servidor: %d\n", newServerPort);
            preferences.begin("net-creds", false);
            preferences.putString("ssid", newSsid);
            preferences.putString("pass", newPass);
            preferences.putString("ip", newServerIp);
            preferences.putInt("port", newServerPort);
            preferences.end();
            Serial.println("Credenciales guardadas. Reiniciando...");
            delay(1000);
            new_credential = true;
        }
    }//Manejar errores
}

void MyServerCallbacks::onConnect(BLEServer* pServer) {
    Serial.println("App conectada");
}

void MyServerCallbacks::onDisconnect(BLEServer* pServer) {
    Serial.println("App desconectada");
    pServer->getAdvertising()->start();
}

void setupBLE() {
    Serial.println("Iniciando modo configuración por BLE...");
    char deviceName[32];
    sprintf(deviceName, "Configurador_VoskClient");
    BLEDevice::init(deviceName);
    BLEServer* pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());
    BLEService *pService = pServer->createService(SERVICE_UUID);
    BLECharacteristic *pSchemaCharacteristic = pService->createCharacteristic(SCHEMA_CHARACTERISTIC_UUID, BLECharacteristic::PROPERTY_READ);
    
    const char* schemaJson = R"json([
        { "key": "ssid", "label": "Nombre de Red (SSID)", "type": "string", "required": true },
        { "key": "pass", "label": "Contraseña WiFi", "type": "password", "required": false },
        { "key": "server", "label": "Server Ip", "type": "string", "required": true },
        { "key": "port", "label": "Server Port", "type": "int", "required": true }
    ])json";
    pSchemaCharacteristic->setValue(schemaJson);

    BLECharacteristic *pDataCharacteristic = pService->createCharacteristic(DATA_CHARACTERISTIC_UUID, BLECharacteristic::PROPERTY_WRITE);
    pDataCharacteristic->setCallbacks(new DataCharacteristicCallbacks());
    pService->start();
    BLEDevice::getAdvertising()->addServiceUUID(SERVICE_UUID);
    BLEDevice::startAdvertising();
    Serial.println("Esperando conexión de la app...");
}
