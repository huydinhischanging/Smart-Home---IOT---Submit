import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_home_mobile/core/socket_service.dart';

class _FakeSocketClient implements SocketClient {
  final Map<String, void Function(dynamic data)> _eventHandlers = {};
  void Function(dynamic data)? _onConnect;
  final List<Map<String, dynamic>> emitted = [];
  bool connectedValue = false;
  bool connectCalled = false;
  bool disconnectCalled = false;
  bool disposeCalled = false;

  @override
  bool get connected => connectedValue;

  @override
  void connect() {
    connectCalled = true;
    connectedValue = true;
  }

  @override
  void disconnect() {
    disconnectCalled = true;
    connectedValue = false;
  }

  @override
  void dispose() {
    disposeCalled = true;
  }

  @override
  void emit(String event, dynamic data) {
    emitted.add({'event': event, 'data': data});
  }

  @override
  void on(String event, void Function(dynamic data) handler) {
    _eventHandlers[event] = handler;
  }

  @override
  void onConnect(void Function(dynamic data) handler) {
    _onConnect = handler;
  }

  void triggerConnect([dynamic data]) {
    _onConnect?.call(data);
  }

  void triggerEvent(String event, dynamic data) {
    _eventHandlers[event]?.call(data);
  }
}

Future<void> _expectClosedStream<T>(Stream<T> stream) async {
  final done = Completer<void>();
  final sub = stream.listen((_) {}, onDone: done.complete);
  await done.future;
  await sub.cancel();
}

void main() {
  test('socket service connects, joins room, and forwards map events', () async {
    late _FakeSocketClient socket;
    final service = SocketService(
      socketFactory: (_) {
        socket = _FakeSocketClient();
        return socket;
      },
    );
    addTearDown(service.dispose);

    final deviceEvents = <Map<String, dynamic>>[];
    final alertEvents = <Map<String, dynamic>>[];
    final deviceSub = service.onDeviceUpdate.listen(deviceEvents.add);
    final alertSub = service.onNewAlert.listen(alertEvents.add);
    addTearDown(deviceSub.cancel);
    addTearDown(alertSub.cancel);

    service.connect('http://example.test', 'token-123');

    expect(service.isConnected, true);
    expect(socket.connectCalled, true);

    socket.triggerConnect();
    socket.triggerEvent('device_status', {'device_code': 'lamp', 'is_on': true});
    socket.triggerEvent('alert', {'message': 'Warning', 'level': 'warning'});
    socket.triggerEvent('device_status', 'ignored');
    socket.triggerEvent('alert', 42);
    await Future<void>.delayed(Duration.zero);

    expect(socket.emitted, [
      {
        'event': 'join_room',
        'data': {'token': 'token-123'},
      },
    ]);
    expect(deviceEvents, [
      {'device_code': 'lamp', 'is_on': true},
    ]);
    expect(alertEvents, [
      {'message': 'Warning', 'level': 'warning'},
    ]);
  });

  test('socket service disconnects previous socket before reconnecting', () {
    final sockets = <_FakeSocketClient>[];
    final service = SocketService(
      socketFactory: (_) {
        final socket = _FakeSocketClient();
        sockets.add(socket);
        return socket;
      },
    );
    addTearDown(service.dispose);

    service.connect('http://example.test', 'first');
    service.connect('http://example.test', 'second');

    expect(sockets, hasLength(2));
    expect(sockets.first.disconnectCalled, true);
    expect(sockets.first.disposeCalled, true);
    expect(sockets.last.connectCalled, true);
  });

  test('socket service disconnect and dispose are idempotent enough for callers', () async {
    late _FakeSocketClient socket;
    final service = SocketService(
      socketFactory: (_) {
        socket = _FakeSocketClient();
        return socket;
      },
    );

    service.connect('http://example.test', 'token');
    service.disconnect();

    expect(socket.disconnectCalled, true);
    expect(socket.disposeCalled, true);
    expect(service.isConnected, false);

    final deviceDone = service.onDeviceUpdate.isBroadcast;
    final alertDone = service.onNewAlert.isBroadcast;
    expect(deviceDone, true);
    expect(alertDone, true);

    service.dispose();
    await _expectClosedStream(service.onDeviceUpdate);
    await _expectClosedStream(service.onNewAlert);
  });

  test('socket service provider disposes the service with the container', () {
    final container = ProviderContainer();
    final service = container.read(socketServiceProvider);

    expect(service, isA<SocketService>());

    container.dispose();

    expectLater(service.onDeviceUpdate.isEmpty, completes);
    expectLater(service.onNewAlert.isEmpty, completes);
  });
}