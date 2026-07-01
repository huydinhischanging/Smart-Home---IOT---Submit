import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smart_home_mobile/core/api_context_provider.dart';
import 'package:smart_home_mobile/core/http_client_provider.dart';
import 'package:smart_home_mobile/modules/dashboard/dashboard_provider.dart';

void main() {
  test('dashboard state computed helpers and grouping work', () {
    const state = DashboardState(
      devices: [
        {'name': 'Lamp', 'room': 'Living', 'is_on': true},
        {'name': 'Fan', 'is_on': false},
      ],
      rooms: [
        {'id': 1, 'name': 'Living'},
        {'id': 2, 'name': 'Bedroom'},
      ],
    );

    expect(state.activeDevices, 1);
    expect(state.totalDevices, 2);
    expect(state.totalRooms, 2);
    expect(state.devicesByRoom['Living'], hasLength(1));
    expect(state.devicesByRoom['General Area'], hasLength(1));
    expect(state.copyWith().devices, hasLength(2));
  });

  test('dashboard provider loads devices and rooms', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices') {
        return http.Response('{"data":[{"name":"Lamp","room":"Living","is_on":true}]}', 200);
      }
      if (request.url.path == '/api/rooms') {
        return http.Response('{"data":[{"id":1,"name":"Living"}]}', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    await container.read(dashboardProvider.notifier).load();
    final state = container.read(dashboardProvider);

    expect(state.devices, hasLength(1));
    expect(state.rooms, hasLength(1));
    expect(state.activeDevices, 1);
    expect(state.devicesByRoom['Living'], hasLength(1));
  });

  test('dashboard provider surfaces session expiry and preserves prior rooms', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices') {
        return http.Response('Denied', 401);
      }
      if (request.url.path == '/api/rooms') {
        return http.Response('[{"id":1,"name":"Living"}]', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    await container.read(dashboardProvider.notifier).load();
    final state = container.read(dashboardProvider);

    expect(state.loading, false);
    expect(state.error, contains('Session expired'));
    expect(state.rooms, hasLength(1));
    expect(state.devices, isEmpty);
  });

  test('dashboard provider surfaces generic device HTTP failures', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices') {
        return http.Response('Boom', 500);
      }
      if (request.url.path == '/api/rooms') {
        return http.Response('{"data":[]}', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    await container.read(dashboardProvider.notifier).load();
    final state = container.read(dashboardProvider);

    expect(state.loading, false);
    expect(state.error, 'Devices: HTTP 500');
  });

  test('dashboard provider handles load exceptions', () async {
    final client = MockClient((_) async => throw http.ClientException('offline'));

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    await container.read(dashboardProvider.notifier).load();
    final state = container.read(dashboardProvider);

    expect(state.loading, false);
    expect(state.error, contains('offline'));
  });

  test('dashboard provider refreshDevices updates devices and ignores refresh errors', () async {
    var shouldThrow = false;
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices') {
        if (shouldThrow) throw http.ClientException('offline');
        return http.Response('[{"name":"Lamp","is_on":true}]', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    final notifier = container.read(dashboardProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Fan', 'is_on': false}
    ]);

    await notifier.refreshDevices();
    expect(container.read(dashboardProvider).devices.single['name'], 'Lamp');

    shouldThrow = true;
    await notifier.refreshDevices();
    expect(container.read(dashboardProvider).devices.single['name'], 'Lamp');
  });

  test('dashboard provider setDevicePower returns true on success', () async {
    http.Request? sentRequest;
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices/control') {
        sentRequest = request;
        return http.Response('{"success":true}', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    final notifier = container.read(dashboardProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Lamp', 'is_on': false}
    ]);

    final ok = await notifier.setDevicePower({'name': 'Lamp'}, true);

    expect(ok, true);
    expect(container.read(dashboardProvider).devices.single['is_on'], true);
    expect(sentRequest?.body, contains('"action":"ON"'));
  });

  test('dashboard provider reverts setDevicePower on failure', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices/control') {
        throw http.ClientException('offline');
      }
      return http.Response('{"data":[]}', 200);
    });

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    final notifier = container.read(dashboardProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Lamp', 'is_on': false}
    ]);

    final ok = await notifier.setDevicePower({'name': 'Lamp'}, true);

    expect(ok, false);
    expect(container.read(dashboardProvider).devices.single['is_on'], false);
  });

  test('dashboard provider reverts setDevicePower on non-200 response', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices/control') {
        return http.Response('Denied', 500);
      }
      return http.Response('Not found', 404);
    });

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    final notifier = container.read(dashboardProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Lamp', 'is_on': false}
    ]);

    final ok = await notifier.setDevicePower({'name': 'Lamp'}, true);

    expect(ok, false);
    expect(container.read(dashboardProvider).devices.single['is_on'], false);
  });

  test('dashboard provider applies socket device updates by device_code or code', () {
    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(MockClient((_) async => http.Response('{}', 200))),
    ]);
    addTearDown(container.dispose);

    final notifier = container.read(dashboardProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Lamp', 'device_code': 'dev-1', 'is_on': false},
      {'name': 'Fan', 'code': 'dev-2', 'is_on': false, 'value': 1},
    ]);

    notifier.applyDeviceUpdate({'device_code': 'dev-1', 'is_on': true});
    notifier.applyDeviceUpdate({'code': 'dev-2', 'value': 42});
    notifier.applyDeviceUpdate(const {'value': 99});

    final devices = container.read(dashboardProvider).devices;
    expect(devices[0]['is_on'], true);
    expect(devices[1]['value'], 42);
  });
}