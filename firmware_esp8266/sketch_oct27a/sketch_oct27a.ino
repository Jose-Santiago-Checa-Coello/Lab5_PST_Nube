#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include "secrets.h"

// ---------------- CONFIGURACION ----------------
const char* WIFI_SSID  = SECRET_WIFI_SSID;
const char* WIFI_PASS  = SECRET_WIFI_PASS;
const char* SERVER_URL = SECRET_SERVER_URL;
const char* API_TOKEN  = SECRET_API_TOKEN;
const char* DEVICE_ID  = "esp8266-nodo01";

#define DHTPIN 4         // GPIO 4 corresponde al pin físico D2 en NodeMCU/Wemos
#define DHTTYPE DHT22    // Sensor DHT22
#define PIN_ACTUADOR 5   // GPIO 5 corresponde al pin físico D1 en NodeMCU/Wemos

DHT dht(DHTPIN, DHTTYPE);

// Cambiar a false para probar el rechazo HTTP 401 desde el servidor en la nube
bool ENVIAR_TOKEN = true;

unsigned long ultimoEnvioLectura = 0;
const unsigned long INTERVALO_LECTURA = 5000;

void conectarWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Conectando a WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.print("\nConectado. IP local: ");
  Serial.println(WiFi.localIP());
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_ACTUADOR, OUTPUT);
  digitalWrite(PIN_ACTUADOR, LOW);
  dht.begin();
  conectarWiFi();
}

void enviarLecturaDHT() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  
  if (isnan(h) || isnan(t)) {
    Serial.println("Error al leer el sensor DHT22");
    return;
  }

  WiFiClientSecure client;
  client.setInsecure(); // Necesario en ESP8266 para omitir la validación del certificado SSL

  HTTPClient http;
  String url = String(SERVER_URL) + "/api/lecturas";
  
  if (http.begin(client, url)) {
    http.addHeader("Content-Type", "application/json");

    if (ENVIAR_TOKEN) {
      http.addHeader("Authorization", String("Bearer ") + API_TOKEN);
    }

    char jsonBody[128];
    snprintf(jsonBody, sizeof(jsonBody),
             "{\"dispositivo\":\"%s\",\"temperatura\":%.1f,\"humedad\":%.1f}",
             DEVICE_ID, t, h);

    int httpCode = http.POST(jsonBody);
    String resp = http.getString();
    Serial.printf("[POST /api/lecturas] %s -> HTTP %d | %s\n", jsonBody, httpCode, resp.c_str());
    http.end();
  } else {
    Serial.println("No se pudo conectar al servidor para POST");
  }
}

void consultarEstadoActuador() {
  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  String url = String(SERVER_URL) + "/api/actuador";
  
  if (http.begin(client, url)) {
    int httpCode = http.GET();
    if (httpCode == HTTP_CODE_OK) {
      String payload = http.getString();
      JsonDocument doc;
      DeserializationError error = deserializeJson(doc, payload);
      
      if (!error) {
        int estado = doc["estado"];
        digitalWrite(PIN_ACTUADOR, estado == 1 ? HIGH : LOW);
        Serial.printf("[GET /api/actuador] Estado recibido: %d\n", estado);
      }
    }
    http.end();
  } else {
    Serial.println("No se pudo conectar al servidor para GET");
  }
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) conectarWiFi();

  unsigned long ahora = millis();
  if (ahora - ultimoEnvioLectura >= INTERVALO_LECTURA) {
    ultimoEnvioLectura = ahora;
    enviarLecturaDHT();
  }

  consultarEstadoActuador();
  delay(1500);
}