class Device {
  final String id, name, type, roomId;
  final bool isOnline, state;
  final Map<String, dynamic>? metadata;

  Device({
    required this.id,
    required this.name,
    required this.type,
    required this.roomId,
    required this.isOnline,
    required this.state,
    this.metadata,
  });

  factory Device.fromJson(Map<String, dynamic> json) => Device(
        id: json['id'] ?? '',
        name: json['name'] ?? '',
        type: json['type'] ?? '',
        roomId: json['room_id'] ?? '',
        isOnline: json['is_online'] ?? false,
        state: json['state'] == 1 || json['state'] == true,
        metadata: json['metadata'],
      );

  Device copyWith({bool? state, bool? isOnline}) => Device(
        id: id, name: name, type: type, roomId: roomId,
        isOnline: isOnline ?? this.isOnline,
        state: state ?? this.state,
      );
}

class SensorReading {
  final String deviceId, sensorType, unit;
  final double value;
  final DateTime timestamp;

  SensorReading({
    required this.deviceId,
    required this.sensorType,
    required this.value,
    required this.unit,
    required this.timestamp,
  });

  factory SensorReading.fromJson(Map<String, dynamic> json) => SensorReading(
        deviceId: json['device_id'] ?? '',
        sensorType: json['sensor_type'] ?? '',
        value: (json['value'] ?? 0).toDouble(),
        unit: json['unit'] ?? '',
        timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
      );
}

class Room {
  final String id, name, icon;
  final List<Device> devices;

  Room({
    required this.id,
    required this.name,
    required this.icon,
    this.devices = const [],
  });

  factory Room.fromJson(Map<String, dynamic> json) => Room(
        id: json['id'] ?? '',
        name: json['name'] ?? '',
        icon: json['icon'] ?? 'home',
        devices: (json['devices'] as List<dynamic>? ?? [])
            .map((d) => Device.fromJson(d))
            .toList(),
      );
}

class Alert {
  final String id, type, message, severity;
  final bool isRead;
  final DateTime createdAt;

  Alert({
    required this.id,
    required this.type,
    required this.message,
    required this.severity,
    required this.isRead,
    required this.createdAt,
  });

  factory Alert.fromJson(Map<String, dynamic> json) => Alert(
        id: json['id'] ?? '',
        type: json['type'] ?? '',
        message: json['message'] ?? '',
        severity: json['severity'] ?? 'info',
        isRead: json['is_read'] ?? false,
        createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
      );
}
