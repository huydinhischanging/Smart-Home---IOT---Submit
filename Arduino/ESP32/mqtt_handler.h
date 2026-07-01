/**
 * ✅ MODULAR: MQTT Connection & Publishing Handler
 * Manages MQTT client lifecycle, connection, and message publishing
 */

#ifndef MQTT_HANDLER_H
#define MQTT_HANDLER_H

#include <PubSubClient.h>
#include <WiFiClientSecure.h>
#include <string>

class MqttHandler {
private:
  WiFiClientSecure espClient;
  PubSubClient client;
  const char* mqttServer;
  int mqttPort;
  const char* mqttUser;
  const char* mqttPassword;
  const char* mqttRootCA;
  bool useTLS;
  bool allowInsecureTLS;

  unsigned long lastReconnectAttempt = 0;
  const unsigned long RECONNECT_INTERVAL = 5000;
  int reconnectionAttempts = 0;
  const int MAX_RECONNECT_ATTEMPTS = 10;

public:
  MqttHandler(const char* _server, int _port, const char* _user, const char* _password,
              const char* _rootCA, bool _useTLS, bool _allowInsecure)
    : mqttServer(_server), mqttPort(_port), mqttUser(_user), mqttPassword(_password),
      mqttRootCA(_rootCA), useTLS(_useTLS), allowInsecureTLS(_allowInsecure),
      client(espClient) {
    client.setServer(mqttServer, mqttPort);
  }

  /**
   * Setup MQTT connection with TLS configuration
   * @return true if setup successful (doesn't guarantee connection)
   */
  bool setup() {
    Serial.println("[MQTT] Setting up TLS configuration...");

    if (useTLS && mqttRootCA && strlen(mqttRootCA) > 0) {
      espClient.setCACert(mqttRootCA);
      Serial.println("[MQTT] ✅ Using CA certificate pinning (secure)");
      return true;
    } else if (allowInsecureTLS) {
      #warning "⚠️  MQTT_ALLOW_INSECURE_TLS is enabled! This disables certificate verification."
      #warning "🔓 SECURITY RISK: Device is vulnerable to Man-in-the-Middle (MITM) attacks!"
      #warning "👉 FOR DEVELOPMENT ONLY! Never deploy to production with this setting!"
      espClient.setInsecure();
      Serial.println("[MQTT] ⚠️  TLS verification DISABLED (insecure!)");
      Serial.println("[MQTT] ⚠️  This configuration is for development only!");
      return true;
    } else {
      Serial.println("[MQTT] ❌ TLS not configured!");
      Serial.println("[MQTT] 👉 Either:");
      Serial.println("[MQTT]    1. Set MQTT_USE_CA_CERT=1 and provide MQTT_ROOT_CA");
      Serial.println("[MQTT]    2. OR set MQTT_ALLOW_INSECURE_TLS=1 (development only)");
      return false;
    }
  }

  /**
   * Connect to MQTT broker
   * @param clientId Unique client identifier
   * @return true if connected successfully
   */
  bool connect(const char* clientId) {
    if (client.connected()) {
      return true;
    }

    unsigned long now = millis();
    if (now - lastReconnectAttempt < RECONNECT_INTERVAL) {
      return false;
    }

    lastReconnectAttempt = now;
    reconnectionAttempts++;

    Serial.printf("[MQTT] Connecting to %s:%d (attempt %d/%d)...\n",
                  mqttServer, mqttPort, reconnectionAttempts, MAX_RECONNECT_ATTEMPTS);

    if (client.connect(clientId, mqttUser, mqttPassword)) {
      Serial.println("[MQTT] ✅ Connected!");
      reconnectionAttempts = 0;
      return true;
    } else {
      int returnCode = client.state();
      Serial.printf("[MQTT] ❌ Connection failed (rc=%d: %s)\n", returnCode, getMqttStateString(returnCode));

      if (reconnectionAttempts >= MAX_RECONNECT_ATTEMPTS) {
        Serial.println("[MQTT] ⚠️  Max reconnection attempts reached");
        reconnectionAttempts = 0;
      }
      return false;
    }
  }

  /**
   * Publish message to MQTT topic
   * @param topic MQTT topic name
   * @param payload Message payload
   * @return true if published successfully
   */
  bool publish(const char* topic, const char* payload) {
    if (!isConnected()) {
      Serial.printf("[MQTT] Not connected. Cannot publish to %s\n", topic);
      return false;
    }

    if (client.publish(topic, payload)) {
      Serial.printf("[MQTT] 📤 Published: %s -> %s\n", topic, payload);
      return true;
    } else {
      Serial.printf("[MQTT] ❌ Publish failed: %s -> %s\n", topic, payload);
      return false;
    }
  }

  /**
   * Subscribe to MQTT topic
   */
  bool subscribe(const char* topic) {
    if (!isConnected()) {
      Serial.printf("[MQTT] Not connected. Cannot subscribe to %s\n", topic);
      return false;
    }

    if (client.subscribe(topic)) {
      Serial.printf("[MQTT] ✅ Subscribed: %s\n", topic);
      return true;
    } else {
      Serial.printf("[MQTT] ❌ Subscribe failed: %s\n", topic);
      return false;
    }
  }

  /**
   * Process MQTT client loop (call regularly in main loop)
   */
  void loop() {
    if (client.connected()) {
      client.loop();
    } else {
      // Not connected, will attempt reconnection in next call to connect()
    }
  }

  /**
   * Check if MQTT is connected
   */
  bool isConnected() const {
    return client.connected();
  }

  /**
   * Set message callback for received messages
   */
  void setCallback(MQTT_CALLBACK_SIGNATURE) {
    client.setCallback(callback);
  }

private:
  /**
   * Get human-readable MQTT state string
   */
  const char* getMqttStateString(int state) {
    switch (state) {
      case -4: return "Connection timeout";
      case -3: return "Connection lost";
      case -2: return "Connect failed";
      case -1: return "Disconnected";
      case 0: return "Connected";
      case 1: return "Bad protocol version";
      case 2: return "Bad client id";
      case 3: return "Unavailable";
      case 4: return "Bad credentials";
      case 5: return "Not authorized";
      default: return "Unknown state";
    }
  }
};

#endif // MQTT_HANDLER_H
