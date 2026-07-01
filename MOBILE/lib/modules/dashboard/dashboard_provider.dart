// lib/modules/dashboard/dashboard_provider.dart
// Aggregated Riverpod provider combining devices + rooms in a single load.
// Screens can use this instead of making two separate HTTP calls.
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/api_headers.dart';
import '../../core/api_context_provider.dart';
import '../../core/http_client_provider.dart';

// ── State ─────────────────────────────────────────────────────
class DashboardState {
  final List<Map<String, dynamic>> devices;
  final List<Map<String, dynamic>> rooms;
  final bool loading;
  final String? error;

  const DashboardState({
    this.devices = const [],
    this.rooms = const [],
    this.loading = false,
    this.error,
  });

  DashboardState copyWith({
    List<Map<String, dynamic>>? devices,
    List<Map<String, dynamic>>? rooms,
    bool? loading,
    String? error,
  }) =>
      DashboardState(
        devices: devices ?? this.devices,
        rooms: rooms ?? this.rooms,
        loading: loading ?? this.loading,
        error: error,
      );

  // ── Computed properties ──────────────────────────────────────
  int get activeDevices =>
      devices.where((d) => d['is_on'] == true).length;
  int get totalDevices => devices.length;
  int get totalRooms => rooms.length;

  /// Devices grouped by room name.
  Map<String, List<Map<String, dynamic>>> get devicesByRoom {
    final map = <String, List<Map<String, dynamic>>>{};
    for (final d in devices) {
      final room = (d['room'] as String?) ?? 'General Area';
      map.putIfAbsent(room, () => []).add(d);
    }
    return map;
  }
}

// ── Notifier ──────────────────────────────────────────────────
class DashboardNotifier extends StateNotifier<DashboardState> {
  final Ref _ref;

  DashboardNotifier(this._ref) : super(const DashboardState());

    String get _base => _ref.read(apiBaseUrlProvider);
    http.Client get _client => _ref.read(httpClientProvider);
  Map<String, String> get _headers =>
      apiJsonHeaders(_ref.read(authHeadersProvider));

  /// Fetch devices and rooms in parallel.
  Future<void> load() async {
    if (state.devices.isEmpty) state = state.copyWith(loading: true);
    try {
      final results = await Future.wait([
        _client
            .get(Uri.parse('$_base/api/devices'), headers: _headers)
            .timeout(const Duration(seconds: 10)),
        _client
            .get(Uri.parse('$_base/api/rooms'), headers: _headers)
            .timeout(const Duration(seconds: 10)),
      ]);

      final dr = results[0];
      final rr = results[1];

      var devices = state.devices;
      var rooms = state.rooms;
      String? err;

      if (dr.statusCode == 200) {
        final d = jsonDecode(dr.body);
        final raw =
            (d is List ? d : (d['data'] ?? d['devices'] ?? [])) as List;
        devices = raw.cast<Map<String, dynamic>>();
      } else if (dr.statusCode == 401) {
        err = 'Session expired — please log in again.';
      } else {
        err = 'Devices: HTTP ${dr.statusCode}';
      }

      if (rr.statusCode == 200) {
        final d = jsonDecode(rr.body);
        final raw =
            (d is List ? d : (d['data'] ?? d['rooms'] ?? [])) as List;
        rooms = raw.cast<Map<String, dynamic>>();
      }

      state = state.copyWith(
        devices: devices,
        rooms: rooms,
        loading: false,
        error: err,
      );
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  Future<void> refreshDevices() async {
    try {
        final r = await _client
          .get(Uri.parse('$_base/api/devices'), headers: _headers)
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body);
        final raw =
            (d is List ? d : (d['data'] ?? d['devices'] ?? [])) as List;
        state = state.copyWith(devices: raw.cast<Map<String, dynamic>>());
      }
    } catch (_) {}
  }

  Future<bool> setDevicePower(Map<String, dynamic> device, bool isOn) async {
    final deviceCode =
        (device['code'] as String?) ?? (device['device_code'] as String?);
    final deviceId = device['id'];
    final deviceName = (device['name'] as String?) ?? '';

    final previousDevices = state.devices;
    state = state.copyWith(
      devices: state.devices.map((d) {
        final sameCode = deviceCode != null &&
            (d['code'] == deviceCode || d['device_code'] == deviceCode);
        final sameId = deviceId != null && d['id'] == deviceId;
        final sameName = d['name'] == deviceName;
        if (sameCode || sameId || sameName) {
          return {...d, 'is_on': isOn};
        }
        return d;
      }).toList(),
    );

    try {
      final r = await _client
          .post(
            Uri.parse('$_base/api/devices/control'),
            headers: _headers,
            body: jsonEncode({
              if (deviceCode != null && deviceCode.isNotEmpty)
                'device_code': deviceCode,
              if (deviceName.isNotEmpty) 'device_name': deviceName,
              if (deviceName.isNotEmpty) 'name': deviceName,
              'action': isOn ? 'ON' : 'OFF',
            }),
          )
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        return true;
      }
    } catch (_) {}

    state = state.copyWith(devices: previousDevices);
    return false;
  }

  /// Apply a real-time Socket.IO device_update event.
  void applyDeviceUpdate(Map<String, dynamic> data) {
    final code =
        data['device_code'] as String? ?? data['code'] as String?;
    if (code == null) return;
    state = state.copyWith(
      devices: state.devices.map((d) {
        if (d['code'] == code || d['device_code'] == code) {
          return {
            ...Map<String, dynamic>.from(d),
            if (data.containsKey('is_on')) 'is_on': data['is_on'],
            if (data.containsKey('value')) 'value': data['value'],
          };
        }
        return d;
      }).toList(),
    );
  }
}

// ── Provider ──────────────────────────────────────────────────
final dashboardProvider =
    StateNotifierProvider<DashboardNotifier, DashboardState>(
  (ref) => DashboardNotifier(ref),
);
