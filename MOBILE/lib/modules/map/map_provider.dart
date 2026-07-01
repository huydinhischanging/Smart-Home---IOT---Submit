import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/api_headers.dart';
import '../../core/api_context_provider.dart';
import '../../core/http_client_provider.dart';

class MapState {
  final List<Map<String, dynamic>> devices;
  final List<Map<String, dynamic>> rooms;
  final List<Map<String, dynamic>> layoutRooms;
  final Map<String, dynamic> layoutMapCache;
  final List<Map<String, dynamic>> floors;
  final int floorIndex;
  final bool loading;
  final String? currentRoomId;
  final String? currentRoomName;

  const MapState({
    this.devices = const [],
    this.rooms = const [],
    this.layoutRooms = const [],
    this.layoutMapCache = const {},
    this.floors = const [],
    this.floorIndex = 0,
    this.loading = false,
    this.currentRoomId,
    this.currentRoomName,
  });

  MapState copyWith({
    List<Map<String, dynamic>>? devices,
    List<Map<String, dynamic>>? rooms,
    List<Map<String, dynamic>>? layoutRooms,
    Map<String, dynamic>? layoutMapCache,
    List<Map<String, dynamic>>? floors,
    int? floorIndex,
    bool? loading,
    String? currentRoomId,
    String? currentRoomName,
  }) =>
      MapState(
        devices: devices ?? this.devices,
        rooms: rooms ?? this.rooms,
        layoutRooms: layoutRooms ?? this.layoutRooms,
        layoutMapCache: layoutMapCache ?? this.layoutMapCache,
        floors: floors ?? this.floors,
        floorIndex: floorIndex ?? this.floorIndex,
        loading: loading ?? this.loading,
        currentRoomId: currentRoomId ?? this.currentRoomId,
        currentRoomName: currentRoomName ?? this.currentRoomName,
      );

  bool get hasBlueprint {
    if (floors.isEmpty || floorIndex >= floors.length) return false;
    return floors[floorIndex]['has_blueprint'] == true;
  }

  String get currentFloorId {
    if (floors.isEmpty) return '1';
    return floors[floorIndex]['id']?.toString() ?? '1';
  }

  List<Map<String, dynamic>> get floorDevices {
    if (layoutMapCache.isNotEmpty) {
      final byName = <String, Map<String, dynamic>>{};
      for (final device in devices) {
        final name = (device['name'] ?? device['device_name'] ?? '').toString();
        final code = (device['code'] ?? device['device_code'] ?? '').toString();
        if (name.isNotEmpty) byName[name] = device;
        if (code.isNotEmpty && !byName.containsKey(code)) byName[code] = device;
      }

      final out = <Map<String, dynamic>>[];
      layoutMapCache.forEach((name, pos) {
        final key = name.toString();
        final matchedDevice = byName[key];
        final matchedFloorId =
            (matchedDevice?['floor_id'] ?? matchedDevice?['floor'] ?? '')
                .toString()
                .trim();
        if (matchedFloorId.isNotEmpty && matchedFloorId != currentFloorId) {
          return;
        }

        final rawPos = pos is Map
            ? pos.cast<String, dynamic>()
            : const <String, dynamic>{};
        final device = matchedDevice ??
            {
              'name': key,
              'code': key,
              'is_on': rawPos['isOn'] == true,
            };
        final x = ((rawPos['x'] ?? device['map_x'] ?? 0) as num).toDouble();
        final y = ((rawPos['y'] ?? device['map_y'] ?? 0) as num).toDouble();
        out.add({
          ...device,
          'name': (device['name'] ?? key),
          'map_x': x,
          'map_y': y
        });
      });
      return out;
    }

    if (floors.isEmpty) return const [];

    // layoutMapCache is empty for this floor — only show devices that are
    // explicitly assigned to this floor via floor_id.  No fallback for
    // devices without floor_id to prevent cross-floor leakage.
    return devices.where((device) {
      final fid = device['floor_id']?.toString() ?? device['floor']?.toString();
      if (fid == null || fid.isEmpty) return false;
      return fid == currentFloorId;
    }).toList();
  }
}

class MapNotifier extends StateNotifier<MapState> {
  final Ref _ref;
  int _refreshCount = 0;

  MapNotifier(this._ref) : super(const MapState());

  String get _base => _ref.read(apiBaseUrlProvider);
  http.Client get _client => _ref.read(httpClientProvider);
  Map<String, String> get _headers =>
      apiJsonHeaders(_ref.read(authHeadersProvider));

  Future<void> loadAll({bool silent = false}) async {
    if (!silent) state = state.copyWith(loading: true);
    try {
      // Fetch independently so one failure doesn't block the others
      final results = await Future.wait([
        _fetchDevices().catchError((_) => <Map<String, dynamic>>[]),
        _fetchRooms().catchError((_) => <Map<String, dynamic>>[]),
        _fetchFloors().catchError((_) => <Map<String, dynamic>>[]),
      ]);

      final devices = results[0];
      final rooms = results[1];
      var floors = results[2];

      if (floors.isEmpty) {
        floors = state.floors.isNotEmpty
            ? state.floors
            : [
                {'id': '1', 'name': 'FLOOR 1', 'has_blueprint': false}
              ];
      }
      state = state.copyWith(
        devices: devices,
        rooms: rooms,
        floors: floors,
        floorIndex: floors.length > state.floorIndex ? state.floorIndex : 0,
      );
      await loadFloorLayout();
    } catch (e) {
      debugPrint('[MapNotifier] loadAll error: $e');
    } finally {
      state = state.copyWith(loading: false);
    }
  }

  Future<void> loadFloorLayout() async {
    if (state.floors.isEmpty) return;
    final floorId = state.currentFloorId;
    state = state.copyWith(layoutRooms: const [], layoutMapCache: const {});
    try {
      final response = await _client
          .get(Uri.parse('$_base/api/map/layout/$floorId'), headers: _headers)
          .timeout(const Duration(seconds: 6));
      if (response.statusCode != 200) {
        state = state.copyWith(layoutRooms: const [], layoutMapCache: const {});
        return;
      }

      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      final data =
          (decoded['data'] as Map?)?.cast<String, dynamic>() ?? const {};
      final rooms = (data['rooms'] as List?) ?? const [];
      final cache =
          (data['map_cache'] as Map?)?.cast<String, dynamic>() ?? const {};

      final sqlRoomsByName = <String, dynamic>{};
      final sqlRoomsById = <String, dynamic>{};
      for (final room in state.rooms) {
        final name = (room['name'] ?? '').toString();
        final id = room['id']?.toString() ?? '';
        if (name.isNotEmpty) sqlRoomsByName[name] = room;
        if (id.isNotEmpty) sqlRoomsById[id] = room;
      }

      final mergedRooms = <Map<String, dynamic>>[];
      for (final rawRoom in rooms) {
        if (rawRoom is! Map) continue;
        final room = rawRoom.cast<String, dynamic>();
        final roomId = room['id']?.toString() ?? '';
        final roomName = (room['name'] ?? '').toString();
        final fallback = sqlRoomsById[roomId] ?? sqlRoomsByName[roomName];
        final hasLayoutPoints = (room['points'] as List?)?.isNotEmpty == true;
        final hasFallbackPoints =
            (fallback?['points'] as List?)?.isNotEmpty == true;

        // Skip layout-only rooms that have no SQL entry — they are stale
        // orphans left after a room was deleted from the backend database.
        if (fallback == null) continue;

        // Prefer floor-layout room polygons (web map source of truth).
        // If missing there, fall back to SQL room points when available.
        mergedRooms.add({
          ...room,
          'points': hasLayoutPoints
              ? room['points']
              : (hasFallbackPoints ? fallback['points'] : const []),
          'color': room['color'] ?? fallback?['color'],
          'name': roomName.isNotEmpty
              ? roomName
              : (fallback?['name']?.toString() ?? ''),
          'id': roomId.isNotEmpty
              ? roomId
              : (fallback?['id']?.toString() ?? ''),
        });
      }

      state = state.copyWith(
        layoutRooms: mergedRooms,
        layoutMapCache: Map<String, dynamic>.from(cache),
      );
    } catch (e) {
      debugPrint('[MapNotifier] loadFloorLayout error: $e');
      state = state.copyWith(layoutRooms: const [], layoutMapCache: const {});
    }
  }

  Future<void> refreshDevices() async {
    _refreshCount++;

    final devices = await _tryFetchDevices();
    if (devices != null) {
      state = state.copyWith(devices: devices);
    }

    // Sync full floor layout every 2 refreshes (~4s) so room polygons/colors
    // also stay in sync with web, not only device positions.
    if (_refreshCount % 2 == 0) {
      await loadFloorLayout();
    }
  }

  Future<Map<String, dynamic>?> _tryFetchLayout(String floorId) async {
    try {
      final response = await _client
          .get(Uri.parse('$_base/api/map/layout/$floorId'), headers: _headers)
          .timeout(const Duration(seconds: 6));
      if (response.statusCode != 200) return null;
      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      final data = (decoded['data'] as Map?)?.cast<String, dynamic>() ?? {};
      return (data['map_cache'] as Map?)?.cast<String, dynamic>();
    } catch (_) {
      return null;
    }
  }

  Future<List<Map<String, dynamic>>?> _tryFetchDevices() async {
    try {
      return await _fetchDevices();
    } catch (_) {
      return null;
    }
  }

  Future<void> selectFloor(int index) async {
    state = state.copyWith(
      floorIndex: index,
      layoutRooms: const [],
      layoutMapCache: const {},
    );
    final expectedIndex = index;
    await loadFloorLayout();
    // Discard result if another floor was selected while we were fetching
    if (state.floorIndex != expectedIndex) {
      state = state.copyWith(layoutRooms: const [], layoutMapCache: const {});
    }
  }

  void selectRoom(String roomId, String roomName) {
    state = state.copyWith(
      currentRoomId: roomId,
      currentRoomName: roomName,
    );
  }

  void applyDeviceUpdate(Map<String, dynamic> data) {
    final code = data['device_code'] as String?;
    if (code == null) return;
    state = state.copyWith(
      devices: state.devices.map((device) {
        if (device['code'] == code || device['device_code'] == code) {
          return {
            ...Map<String, dynamic>.from(device),
            if (data.containsKey('is_on')) 'is_on': data['is_on'],
            if (data.containsKey('value')) 'value': data['value'],
          };
        }
        return device;
      }).toList(),
    );
  }

  Future<void> toggleDevice(Map<String, dynamic> device) async {
    final name = (device['name'] as String?) ?? '';
    final code = (device['code'] as String?) ?? (device['device_code'] as String?);
    final deviceId = device['id'];
    final wasOn = device['is_on'] == true;
    final previousDevices = state.devices;
    state = state.copyWith(
      devices: state.devices.map((item) {
        final sameCode = code != null &&
            (item['code'] == code || item['device_code'] == code);
        final sameId = deviceId != null && item['id'] == deviceId;
        final sameName = item['name'] == name;
        if (sameCode || sameId || sameName) {
          return {...item, 'is_on': !wasOn};
        }
        return item;
      }).toList(),
    );
    try {
      final response = await _client
          .post(
            Uri.parse('$_base/api/devices/control'),
            headers: _headers,
            body: jsonEncode({
              if (code != null && code.isNotEmpty) 'device_code': code,
              if (name.isNotEmpty) 'name': name,
              'action': wasOn ? 'OFF' : 'ON',
            }),
          )
          .timeout(const Duration(seconds: 5));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        state = state.copyWith(devices: previousDevices);
      }
    } catch (_) {
      state = state.copyWith(devices: previousDevices);
    }
  }

  Future<List<Map<String, dynamic>>> _fetchDevices() async {
    const endpoints = ['/api/devices', '/api/devices/status'];
    for (final endpoint in endpoints) {
      final response = await _client
          .get(Uri.parse('$_base$endpoint'), headers: _headers)
          .timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final raw = decoded is List
            ? decoded
            : (decoded['data'] ?? decoded['devices'] ?? []);
        return (raw as List).cast<Map<String, dynamic>>();
      }
    }
    return const [];
  }

  Future<List<Map<String, dynamic>>> _fetchRooms() async {
    try {
      final response = await _client
          .get(Uri.parse('$_base/api/rooms'), headers: _headers)
          .timeout(const Duration(seconds: 6));
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final raw = decoded is List
            ? decoded
            : (decoded['data'] ?? decoded['rooms'] ?? []);
        return (raw as List).cast<Map<String, dynamic>>();
      }
    } catch (_) {}
    return const [];
  }

  Future<List<Map<String, dynamic>>> _fetchFloors() async {
    try {
      final response = await _client
          .get(Uri.parse('$_base/api/map/floors'), headers: _headers)
          .timeout(const Duration(seconds: 8));
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final list = decoded['data'] ?? decoded;
        if (list is List && list.isNotEmpty) {
          final parsed = list
              .map<Map<String, dynamic>>((floor) => {
                    'id': floor['id']?.toString() ?? '1',
                    'name': floor['name'] ?? 'FLOOR 1',
                    'has_blueprint': floor['has_blueprint'] == true,
                    'device_count': floor['device_count'] ?? 0,
                  })
              .toList();
          return _dedupeFloors(parsed);
        }
      }
    } catch (_) {}
    return const [];
  }

  List<Map<String, dynamic>> _dedupeFloors(List<Map<String, dynamic>> floors) {
    final byId = <String, Map<String, dynamic>>{};
    for (final floor in floors) {
      final id = (floor['id'] ?? '').toString().trim();
      if (id.isEmpty) continue;
      final existing = byId[id];
      if (existing == null) {
        byId[id] = floor;
        continue;
      }

      // Keep the richer row when duplicate IDs are returned by backend.
      final existingScore = ((existing['has_blueprint'] == true) ? 100 : 0) +
          ((existing['device_count'] as num?)?.toInt() ?? 0);
      final nextScore = ((floor['has_blueprint'] == true) ? 100 : 0) +
          ((floor['device_count'] as num?)?.toInt() ?? 0);
      if (nextScore > existingScore) byId[id] = floor;
    }

    final out = byId.values.toList();
    out.sort((a, b) {
      final ai = int.tryParse(a['id']?.toString() ?? '') ?? 0;
      final bi = int.tryParse(b['id']?.toString() ?? '') ?? 0;
      return ai.compareTo(bi);
    });
    return out;
  }
}

final mapProvider = StateNotifierProvider<MapNotifier, MapState>(
  (ref) => MapNotifier(ref),
);
