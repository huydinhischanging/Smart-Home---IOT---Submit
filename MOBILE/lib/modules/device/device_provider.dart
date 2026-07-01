// lib/modules/device/device_provider.dart
// Riverpod provider for device list + control commands.
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/api_headers.dart';
import '../../core/auth_provider.dart';
import '../../core/cfg_provider.dart';

// ── State ─────────────────────────────────────────────────────
class DeviceState {
  final List<Map<String, dynamic>> devices;
  final bool loading;
  final String? error;

  const DeviceState({
    this.devices = const [],
    this.loading = false,
    this.error,
  });

  DeviceState copyWith({
    List<Map<String, dynamic>>? devices,
    bool? loading,
    String? error,
  }) =>
      DeviceState(
        devices: devices ?? this.devices,
        loading: loading ?? this.loading,
        error: error,
      );

  int get activeCount => devices.where((d) => d['is_on'] == true).length;
  int get totalCount => devices.length;
}

// ── Notifier ──────────────────────────────────────────────────
class DeviceNotifier extends StateNotifier<DeviceState> {
  final Ref _ref;

  DeviceNotifier(this._ref) : super(const DeviceState()) {
    Future.microtask(load);
  }

  String get _base => _ref.read(cfgProvider);
  Map<String, String> get _headers =>
      apiJsonHeaders(_ref.read(authProvider).bearerHeader);

  /// Fetch all devices for the current user.
  Future<void> load() async {
    if (state.devices.isEmpty) state = state.copyWith(loading: true);
    try {
      final r = await http
          .get(Uri.parse('$_base/api/devices'), headers: _headers)
          .timeout(const Duration(seconds: 10));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body);
        final raw =
            (d is List ? d : (d['data'] ?? d['devices'] ?? [])) as List;
        state = state.copyWith(
          devices: raw.cast<Map<String, dynamic>>(),
          loading: false,
        );
      } else if (r.statusCode == 401) {
        state = state.copyWith(loading: false, error: 'Session expired.');
      } else {
        state = state.copyWith(loading: false, error: 'HTTP ${r.statusCode}');
      }
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  /// Send a control command (e.g. action: 'ON' / 'OFF' / '75') to a device.
  Future<bool> control(String deviceName, String action) async {
    try {
      final r = await http
          .post(
            Uri.parse('$_base/api/devices/control'),
            headers: _headers,
            body: jsonEncode({'device_name': deviceName, 'action': action}),
          )
          .timeout(const Duration(seconds: 8));
      final ok = r.statusCode == 200;
      if (ok) {
        // Optimistic local update
        final isOn = action.toUpperCase() == 'ON';
        final isOff = action.toUpperCase() == 'OFF';
        state = state.copyWith(
          devices: state.devices.map((d) {
            if (d['name'] == deviceName || d['code'] == deviceName) {
              return {
                ...d,
                if (isOn || isOff) 'is_on': isOn,
                if (!isOn && !isOff) 'value': action,
              };
            }
            return d;
          }).toList(),
        );

        // Keep state consistent with backend-confirmed values.
        Future.microtask(load);
      }
      return ok;
    } catch (_) {
      return false;
    }
  }

  /// Delete a device by name or code.
  Future<bool> delete(String nameOrCode) async {
    try {
      final r = await http
          .delete(
            Uri.parse('$_base/api/devices/${Uri.encodeComponent(nameOrCode)}'),
            headers: _headers,
          )
          .timeout(const Duration(seconds: 8));
      if (r.statusCode == 200 || r.statusCode == 204) {
        state = state.copyWith(
          devices: state.devices
              .where((d) =>
                  d['name'] != nameOrCode && d['code'] != nameOrCode)
              .toList(),
        );
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  /// Apply a real-time Socket.IO device_update event to local state.
  void applySocketUpdate(Map<String, dynamic> data) {
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
final deviceProvider =
    StateNotifierProvider<DeviceNotifier, DeviceState>(
  (ref) => DeviceNotifier(ref),
);
