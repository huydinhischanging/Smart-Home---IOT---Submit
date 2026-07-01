class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'APP_BASE_URL',
    defaultValue: '',
  );
  static const String socketUrl = String.fromEnvironment(
    'APP_SOCKET_URL',
    defaultValue: '',
  );

  static const String mqttBroker = String.fromEnvironment(
    'MQTT_BROKER',
    defaultValue: '',
  );
  static const int mqttPort =
      int.fromEnvironment('MQTT_PORT', defaultValue: 8883);
  static const String mqttUser = String.fromEnvironment(
    'MQTT_USER',
    defaultValue: '',
  );
  static const String mqttPass = String.fromEnvironment(
    'MQTT_PASS',
    defaultValue: '',
  );

  static const String mqttTopicSensor = 'home/sensors/#';
  static const String mqttTopicControl = 'home/control';
  static const String mqttTopicStatus = 'home/status/#';
}
