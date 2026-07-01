import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smart_home_mobile/core/api_context_provider.dart';
import 'package:smart_home_mobile/core/http_client_provider.dart';
import 'package:smart_home_mobile/modules/map/map_provider.dart';

ProviderContainer _makeContainer(http.Client client) {
  return ProviderContainer(overrides: [
    apiBaseUrlProvider.overrideWithValue('http://example.test'),
    authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
    httpClientProvider.overrideWithValue(client),
  ]);
}

void main() {
  test('map state getters handle empty, floor-filtered, and cached device layouts', () {
    const empty = MapState();
    expect(empty.hasBlueprint, false);
    expect(empty.currentFloorId, '1');
    expect(empty.floorDevices, isEmpty);

    final filtered = const MapState(
      devices: [
        {'name': 'Lamp', 'floor_id': '1'},
        {'name': 'Fan', 'floor': '2'},
        {'name': 'NoFloor'},
      ],
      floors: [
        {'id': '2', 'has_blueprint': true}
      ],
    ).copyWith(floorIndex: 0);
    expect(filtered.hasBlueprint, true);
    expect(filtered.currentFloorId, '2');
    expect(filtered.floorDevices.single['name'], 'Fan');

    const cached = MapState(
      devices: [
        {'name': 'Lamp', 'map_x': 1, 'map_y': 2},
      ],
      layoutMapCache: {
        'Lamp': {'x': 25, 'y': 30}
      },
      floors: [
        {'id': '1', 'has_blueprint': true}
      ],
    );
    expect(cached.floorDevices.single['map_x'], 25.0);
    expect(cached.floorDevices.single['map_y'], 30.0);

    const cacheMiss = MapState(
      devices: [
        {'name': 'Lamp', 'map_x': 1, 'map_y': 2},
      ],
      layoutMapCache: {
        'Ghost': {'x': 99, 'y': 100}
      },
      floors: [
        {'id': '1', 'has_blueprint': true}
      ],
    );
    expect(cacheMiss.floorDevices, hasLength(1));
    expect(cacheMiss.floorDevices.single['name'], 'Ghost');
  });

  test('map provider handles no-floor layout calls and fetch fallbacks', () async {
    final client = MockClient((request) async {
      switch (request.url.path) {
        case '/api/devices':
          return http.Response('Denied', 500);
        case '/api/devices/status':
          return http.Response('Denied', 503);
        case '/api/rooms':
          throw http.ClientException('offline');
        case '/api/map/floors':
          return http.Response('{"data":[{"id":"3","name":"Floor 3","has_blueprint":false},{"id":"1","name":"Floor 1","has_blueprint":true}]}', 200);
        case '/api/map/layout/1':
          return http.Response('{"data":{"rooms":[],"map_cache":{}}}', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(mapProvider.notifier);

    await notifier.loadFloorLayout();
    expect(container.read(mapProvider).layoutRooms, isEmpty);

    await notifier.loadAll();
    final state = container.read(mapProvider);
    expect(state.devices, isEmpty);
    expect(state.rooms, isEmpty);
    expect(state.floors, hasLength(2));
    expect(state.floors.first['id'], '1');
    expect(state.floors.last['id'], '3');
  });

  test('map provider loadAll and refreshDevices keep state stable on fetch exceptions', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices') {
        throw http.ClientException('offline');
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(mapProvider.notifier);
    notifier.state = notifier.state.copyWith(
      devices: const [
        {'name': 'Lamp', 'is_on': true}
      ],
    );

    await notifier.loadAll();
    expect(container.read(mapProvider).loading, false);
    expect(container.read(mapProvider).devices, isEmpty);

    await notifier.refreshDevices();
    expect(container.read(mapProvider).devices, isEmpty);
  });

  test('map provider refreshDevices swallows fetch exceptions directly', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices') {
        throw http.ClientException('offline');
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(mapProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Lamp'}
    ]);

    await notifier.refreshDevices();

    expect(container.read(mapProvider).devices.single['name'], 'Lamp');
  });

  test('map provider refreshDevices replaces devices on success', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices') {
        return http.Response('{"data":[{"name":"Fan"}]}', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(mapProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Lamp'}
    ]);

    await notifier.refreshDevices();

    expect(container.read(mapProvider).devices.single['name'], 'Fan');
  });

  test('map provider keeps stronger duplicate floor and sorts output ids', () async {
    final client = MockClient((request) async {
      switch (request.url.path) {
        case '/api/devices':
          return http.Response('{"data":[]}', 200);
        case '/api/rooms':
          return http.Response('{"data":[]}', 200);
        case '/api/map/floors':
          return http.Response('{"data":[{"id":"10","name":"Floor 2","has_blueprint":true,"device_count":9},{"id":"2","name":"Tang 2","has_blueprint":false,"device_count":1},{"id":"1","name":"Floor 1","has_blueprint":false,"device_count":0}]}', 200);
        case '/api/map/layout/1':
          return http.Response('{"data":{"rooms":[],"map_cache":{}}}', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    await container.read(mapProvider.notifier).loadAll();
    final floors = container.read(mapProvider).floors;

    expect(floors, hasLength(3));
    expect(floors.first['id'], '1');
    expect(floors[1]['id'], '2');
    expect(floors.last['id'], '10');
    expect(floors.last['has_blueprint'], true);
    expect(floors.last['device_count'], 9);
  });

  test('map provider loadAll and selectFloor build floor-specific layout state', () async {
    final client = MockClient((request) async {
      switch (request.url.path) {
        case '/api/devices':
          return http.Response('{"data":[{"id":1,"name":"Lamp","code":"L1","floor_id":"1"},{"id":2,"name":"Fan","code":"F2","floor_id":"2"}]}', 200);
        case '/api/rooms':
          return http.Response('{"data":[{"id":"101","name":"Living","points":[{"x":0,"y":0}],"color":"#fff"},{"id":"201","name":"Bedroom","points":[{"x":1,"y":1}],"color":"#eee"}]}', 200);
        case '/api/map/floors':
          return http.Response('{"data":[{"id":"1","name":"Floor 1","has_blueprint":true,"device_count":1},{"id":"2","name":"Floor 2","has_blueprint":false,"device_count":1}]}', 200);
        case '/api/map/layout/1':
          return http.Response('{"data":{"rooms":[{"id":"101","name":"Living","points":[{"x":0,"y":0}]}],"map_cache":{"Lamp":{"x":25,"y":30}}}}', 200);
        case '/api/map/layout/2':
          return http.Response('{"data":{"rooms":[{"id":"201","name":"Bedroom","points":[{"x":1,"y":1}]}],"map_cache":{"Fan":{"x":60,"y":70}}}}', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    await container.read(mapProvider.notifier).loadAll();
    var state = container.read(mapProvider);
    expect(state.floors, hasLength(2));
    expect(state.layoutRooms, hasLength(1));
    expect(state.floorDevices.single['name'], 'Lamp');

    await container.read(mapProvider.notifier).selectFloor(1);
    state = container.read(mapProvider);
    expect(state.currentFloorId, '2');
    expect(state.layoutRooms.single['name'], 'Bedroom');
    expect(state.floorDevices.single['name'], 'Fan');
  });

  test('map provider toggleDevice reverts when control request fails', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices/control') {
        throw http.ClientException('offline');
      }
      return http.Response('{"data":[]}', 200);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    final notifier = container.read(mapProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Lamp', 'is_on': true}
    ]);

    await notifier.toggleDevice({'name': 'Lamp', 'is_on': true});

    expect(container.read(mapProvider).devices.single['is_on'], true);
  });

  test('map provider toggleDevice reverts when control request returns error', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices/control') {
        return http.Response('Denied', 500);
      }
      return http.Response('{"data":[]}', 200);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    final notifier = container.read(mapProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Lamp', 'is_on': true}
    ]);

    await notifier.toggleDevice({'name': 'Lamp', 'is_on': true});

    expect(container.read(mapProvider).devices.single['is_on'], true);
  });

  test('map provider loadAll falls back to status endpoint and default floor', () async {
    final client = MockClient((request) async {
      switch (request.url.path) {
        case '/api/devices':
          return http.Response('Denied', 500);
        case '/api/devices/status':
          return http.Response('{"devices":[{"name":"Lamp","code":"L1","floor":"1"}]}', 200);
        case '/api/rooms':
          return http.Response('[{"id":"101","name":"Living","points":[{"x":0,"y":0}],"color":"#fff"}]', 200);
        case '/api/map/floors':
          return http.Response('{"data":[]}', 200);
        case '/api/map/layout/1':
          return http.Response('Denied', 404);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    await container.read(mapProvider.notifier).loadAll();
    final state = container.read(mapProvider);

    expect(state.devices.single['name'], 'Lamp');
    expect(state.floors.single['id'], '1');
    expect(state.hasBlueprint, false);
    expect(state.layoutRooms, isEmpty);
    expect(state.layoutMapCache, isEmpty);
  });

  test('map provider merges layout rooms with SQL fallback and dedupes floors', () async {
    final client = MockClient((request) async {
      switch (request.url.path) {
        case '/api/devices':
          return http.Response('{"data":[{"name":"Lamp","code":"L1","device_code":"dev-1","floor_id":"1","map_x":5,"map_y":6,"is_on":false}]}', 200);
        case '/api/rooms':
          return http.Response('{"data":[{"id":"101","name":"Living","points":[{"x":1,"y":1}],"color":"#abc"}]}', 200);
        case '/api/map/floors':
          return http.Response('{"data":[{"id":"9","name":"Tang 1","has_blueprint":false,"device_count":1},{"id":"1","name":"Tầng 1","has_blueprint":true,"device_count":2}]}', 200);
        case '/api/map/layout/1':
          return http.Response('{"data":{"rooms":[{"id":"101","name":"Living","points":[]},{"id":"999","name":"Ghost","points":[{"x":9,"y":9}]}],"map_cache":{"Lamp":{"x":20,"y":21}}}}', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    await container.read(mapProvider.notifier).loadAll();
    final state = container.read(mapProvider);

    expect(state.floors, hasLength(1));
    expect(state.floors.single['id'], '1');
    expect(state.layoutRooms, hasLength(1));
    expect(state.layoutRooms.single['points'], isNotEmpty);
    expect(state.layoutRooms.single['color'], '#abc');
    expect(state.floorDevices.single['map_x'], 20.0);
    expect(state.floorDevices.single['map_y'], 21.0);
  });

  test('map provider refresh, selectFloor, and loadFloorLayout tolerate failures', () async {
    var layoutThrows = false;
    var devicesThrow = false;
    final client = MockClient((request) async {
      switch (request.url.path) {
        case '/api/devices':
          if (devicesThrow) throw http.ClientException('offline');
          return http.Response('{"data":[{"name":"Lamp","floor_id":"1"}]}', 200);
        case '/api/rooms':
          return http.Response('{"data":[{"id":"101","name":"Living","points":[{"x":0,"y":0}]}]}', 200);
        case '/api/map/floors':
          return http.Response('{"data":[{"id":"1","name":"Floor 1","has_blueprint":true},{"id":"2","name":"Floor 2","has_blueprint":false}]}', 200);
        case '/api/map/layout/1':
          if (layoutThrows) throw http.ClientException('offline');
          return http.Response('{"data":{"rooms":[{"id":"101","name":"Living","points":[{"x":0,"y":0}]}],"map_cache":{}}}', 200);
        case '/api/map/layout/2':
          return http.Response('Denied', 500);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(mapProvider.notifier);

    await notifier.loadAll();
    expect(container.read(mapProvider).layoutRooms, hasLength(1));

    devicesThrow = true;
    await notifier.refreshDevices();
    expect(container.read(mapProvider).devices.single['name'], 'Lamp');

    await notifier.selectFloor(1);
    expect(container.read(mapProvider).currentFloorId, '2');
    expect(container.read(mapProvider).layoutRooms, isEmpty);

    notifier.state = notifier.state.copyWith(floorIndex: 0);
    layoutThrows = true;
    await notifier.loadFloorLayout();
    expect(container.read(mapProvider).layoutRooms, isEmpty);
    expect(container.read(mapProvider).layoutMapCache, isEmpty);
  });

  test('map provider applies live device updates and keeps optimistic toggle on success', () async {
    http.Request? sentRequest;
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices/control') {
        sentRequest = request;
        return http.Response('{"success":true}', 200);
      }
      return http.Response('{"data":[]}', 200);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(mapProvider.notifier);
    notifier.state = notifier.state.copyWith(devices: const [
      {'name': 'Lamp', 'code': 'dev-1', 'is_on': false, 'value': 1},
      {'name': 'Fan', 'device_code': 'dev-2', 'is_on': false},
    ]);

    notifier.applyDeviceUpdate(const {'value': 5});
    notifier.applyDeviceUpdate(const {'device_code': 'dev-1', 'is_on': true, 'value': 8});
    notifier.applyDeviceUpdate(const {'device_code': 'dev-2', 'is_on': true});

    var state = container.read(mapProvider);
    expect(state.devices.first['is_on'], true);
    expect(state.devices.first['value'], 8);
    expect(state.devices[1]['is_on'], true);

    await notifier.toggleDevice({'name': 'Lamp', 'is_on': true});
    state = container.read(mapProvider);
    expect(state.devices.first['is_on'], false);
    expect(sentRequest?.body, contains('"action":"OFF"'));
  });
}