// lib/core/socket_service.dart
// Real-time Socket.IO client for Batman OS Mobile.
// Joins the user room with the bearer token after connecting,
// then emits device_status and alert events to listeners.
import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:socket_io_client/socket_io_client.dart' as io;

abstract class SocketClient {
  bool get connected;
  void onConnect(void Function(dynamic data) handler);
  void on(String event, void Function(dynamic data) handler);
  void emit(String event, dynamic data);
  void connect();
  void disconnect();
  void dispose();
}

// coverage:ignore-start
class IoSocketClient implements SocketClient {
  IoSocketClient(this._socket);

  final io.Socket _socket;

  @override
  bool get connected => _socket.connected;

  @override
  void onConnect(void Function(dynamic data) handler) => _socket.onConnect(handler);

  @override
  void on(String event, void Function(dynamic data) handler) => _socket.on(event, handler);

  @override
  void emit(String event, dynamic data) => _socket.emit(event, data);

  @override
  void connect() => _socket.connect();

  @override
  void disconnect() => _socket.disconnect();

  @override
  void dispose() => _socket.dispose();
}

typedef SocketClientFactory = SocketClient Function(String baseUrl);

SocketClient defaultSocketClientFactory(String baseUrl) {
  return IoSocketClient(
    io.io(
      baseUrl,
      io.OptionBuilder()
          .setTransports(['websocket'])
          .disableAutoConnect()
          .setReconnectionAttempts(10)
          .setReconnectionDelay(3000)
          .build(),
    ),
  );
}
// coverage:ignore-end

class SocketService {
  SocketService({SocketClientFactory socketFactory = defaultSocketClientFactory})
      : _socketFactory = socketFactory;

  final SocketClientFactory _socketFactory;
  SocketClient? _socket;

  final _deviceCtrl     = StreamController<Map<String, dynamic>>.broadcast();
  final _alertCtrl      = StreamController<Map<String, dynamic>>.broadcast();
  final _mapLayoutCtrl  = StreamController<Map<String, dynamic>>.broadcast();
  final _hrAlertCtrl    = StreamController<Map<String, dynamic>>.broadcast();

  Stream<Map<String, dynamic>> get onDeviceUpdate    => _deviceCtrl.stream;
  Stream<Map<String, dynamic>> get onNewAlert        => _alertCtrl.stream;
  Stream<Map<String, dynamic>> get onMapLayoutUpdate => _mapLayoutCtrl.stream;
  Stream<Map<String, dynamic>> get onHrAlert         => _hrAlertCtrl.stream;

  bool get isConnected => _socket?.connected ?? false;

  /// Connect (or reconnect) to [baseUrl] and authenticate with [token].
  void connect(String baseUrl, String token) {
    // Avoid duplicate connections
    if (_socket != null) {
      _socket!.disconnect();
      _socket!.dispose();
      _socket = null;
    }

    _socket = _socketFactory(baseUrl);

    _socket!.onConnect((_) {
      // Authenticate with the server by joining the user room
      _socket!.emit('join_room', {'token': token});
    });

    _socket!.on('device_status', (data) {
      if (data is Map && !_deviceCtrl.isClosed) {
        _deviceCtrl.add(Map<String, dynamic>.from(data));
      }
    });

    _socket!.on('alert', (data) {
      if (data is Map && !_alertCtrl.isClosed) {
        _alertCtrl.add(Map<String, dynamic>.from(data));
      }
    });

    _socket!.on('map_layout_updated', (data) {
      if (data is Map && !_mapLayoutCtrl.isClosed) {
        _mapLayoutCtrl.add(Map<String, dynamic>.from(data));
      }
    });

    _socket!.on('hr_alert', (data) {
      if (data is Map && !_hrAlertCtrl.isClosed) {
        _hrAlertCtrl.add(Map<String, dynamic>.from(data));
      }
    });

    _socket!.connect();
  }

  void disconnect() {
    _socket?.disconnect();
    _socket?.dispose();
    _socket = null;
  }

  void dispose() {
    disconnect();
    _deviceCtrl.close();
    _alertCtrl.close();
    _mapLayoutCtrl.close();
    _hrAlertCtrl.close();
  }
}

final socketServiceProvider = Provider<SocketService>((ref) {
  final service = SocketService();
  ref.onDispose(service.dispose);
  return service;
});
