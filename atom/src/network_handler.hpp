#ifndef NETWORK_HANDLER_HPP
#define NETWORK_HANDLER_HPP

#include <WiFi.h> // Necesario para el tipo WiFiClient

// Declaración de la función
// - client: Se pasa por referencia para poder modificarlo (conectar/desconectar).
// - server_ip, server_port: Se pasan como valores constantes.
// - trasmissione_attiva, g_isRecording: Se pasan por referencia para que la función
//   pueda cambiar su estado directamente.
// - Retorna 'true' si la conexión está bien, y 'false' si hubo un fallo y el loop debe detenerse.
bool manageClientConnection(WiFiClient& client,
                            const char* server_ip,
                            uint16_t server_port,
                            bool& trasmissione_attiva,
                            volatile bool& g_isRecording);

extern bool trying_to_connect;

bool try_connect_wifi(char* ssid, char* password);

#endif // NETWORK_HANDLER_HPP
