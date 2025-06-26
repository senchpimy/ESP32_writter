#include "network_handler.hpp"
#include <Arduino.h>
#include "WiFi.h"

// Variable global para evitar que se solapen los intentos de conexión.
// Asegúrate de que esta variable esté declarada en tu archivo .cpp principal o en un lugar accesible.
extern bool trying_to_connect;

// Función sin cambios
bool manageClientConnection(WiFiClient& client,
                            const char* server_ip,
                            uint16_t server_port,
                            bool& trasmissione_attiva,
                            volatile bool& g_isRecording) {
    if (!client.connected()) {
        Serial.printf("Intentando conectar al servidor %s:%d\n", server_ip, server_port);
        if (client.connect(server_ip, server_port)) {
            Serial.println("Conectado al servidor!");
            if (trasmissione_attiva) {
                Serial.println("Cliente reconectado, deteniendo transmisión previa si estaba activa.");
                trasmissione_attiva = false;
                g_isRecording = false;
            }
        } else {
            Serial.printf("Conexión fallida al servidor. Reintentando en 2 segundos... (Error: %d)\n", client.getWriteError());
            if (trasmissione_attiva) {
                Serial.println("Conexión perdida durante transmisión. Deteniendo.");
                trasmissione_attiva = false;
                g_isRecording = false;
            }
            return false;
        }
    }
    return true;
}

const char* getWifiStatusString(wl_status_t status) {
  switch (status) {
    case WL_NO_SSID_AVAIL:
      return "SSID no encontrado";
    case WL_CONNECT_FAILED:
      return "Fallo de autenticacion (contrasena incorrecta?)";
    case WL_CONNECTION_LOST:
      return "Conexion perdida";
    case WL_DISCONNECTED:
      return "Desconectado";
    case WL_IDLE_STATUS:
      return "Estado inactivo";
    default:
      return "Error desconocido";
  }
}


bool try_connect_wifi(char* ssid, char* password) {
  if (trying_to_connect) {
    Serial.println("Ya se esta intentando una conexion. Omitiendo.");
    return false;
  }

  trying_to_connect = true;
  
  Serial.printf("Conectando a la red WiFi: %s\n", ssid);
  Serial.printf("Con la contraseña %s",password);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  // Esperar un máximo de 15 segundos para la conexión
  int retries = 30; // 30 reintentos de 500ms = 15 segundos
  for (int i = 0; i < retries; i++) {
    if (WiFi.status() == WL_CONNECTED) {
      // ¡Conexión exitosa!
      Serial.println("\nWiFi conectado!");
      Serial.print("Direccion IP: ");
      Serial.println(WiFi.localIP());
      trying_to_connect = false;
      return true;
    }
    Serial.print(".");
    delay(500);
  }

  // Si el bucle termina, la conexión falló. Ahora diagnosticamos el porqué.
  Serial.println("\nFallo al conectar a WiFi.");
  
  wl_status_t status = WiFi.status();
  Serial.printf("Estado final: %s (Codigo: %d)\n", getWifiStatusString(status), status);
  
  // Desconectar para limpiar el estado y permitir futuros intentos
  WiFi.disconnect(true);
  
  trying_to_connect = false;
  return false;
}
