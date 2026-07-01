// lib/modules/alert/alert_provider.dart
// Riverpod state notifier for alert history and unread count.
import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/api_headers.dart';
import '../../core/api_context_provider.dart';
import '../../core/http_client_provider.dart';
import '../../core/socket_service.dart';

// ── Model ─────────────────────────────────────────────────────
class AlertItem {
  final int id;
  final String deviceCode;
  final String message;
  final String level;
  final bool isRead;
  final String createdAt;

  const AlertItem({
    required this.id,
    required this.deviceCode,
    required this.message,
    required this.level,
    required this.isRead,
    required this.createdAt,
  });

  factory AlertItem.fromJson(Map<String, dynamic> j) => AlertItem(
        id: (j['id'] as num?)?.toInt() ?? 0,
        deviceCode: j['device_code']?.toString() ?? '',
        message: j['message']?.toString() ?? '',
        level: j['level']?.toString() ?? 'info',
        isRead: j['is_read'] == true,
        createdAt: j['created_at']?.toString() ?? '',
      );

  AlertItem asRead() => AlertItem(
        id: id,
        deviceCode: deviceCode,
        message: message,
        level: level,
        isRead: true,
        createdAt: createdAt,
      );
}

// ── State ─────────────────────────────────────────────────────
class AlertState {
  final List<AlertItem> alerts;
  final int unread;
  final bool loading;
  final String? error;

  const AlertState({
    this.alerts = const [],
    this.unread = 0,
    this.loading = false,
    this.error,
  });

  AlertState copyWith({
    List<AlertItem>? alerts,
    int? unread,
    bool? loading,
    String? error,
  }) =>
      AlertState(
        alerts: alerts ?? this.alerts,
        unread: unread ?? this.unread,
        loading: loading ?? this.loading,
        error: error,
      );

  AlertState clearError() => AlertState(
        alerts: alerts,
        unread: unread,
        loading: loading,
      );
}

// ── Notifier ──────────────────────────────────────────────────
class AlertNotifier extends StateNotifier<AlertState> {
  final Ref _ref;
  StreamSubscription<Map<String, dynamic>>? _alertSub;

  AlertNotifier(this._ref) : super(const AlertState()) {
    final socketService = _ref.read(socketServiceProvider);
    _alertSub = socketService.onNewAlert.listen(addFromSocket);
  }

  @override
  void dispose() {
    _alertSub?.cancel();
    super.dispose();
  }

    String get _base => _ref.read(apiBaseUrlProvider);
    http.Client get _client => _ref.read(httpClientProvider);
  Map<String, String> get _headers =>
      apiJsonHeaders(_ref.read(authHeadersProvider));

  /// Fetch alert history from backend.
  Future<void> load({int limit = 50}) async {
    state = state.copyWith(loading: true);
    try {
        final r = await _client
          .get(Uri.parse('$_base/api/alerts?limit=$limit'), headers: _headers)
          .timeout(const Duration(seconds: 10));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body) as Map<String, dynamic>;
        final raw =
            (d['data'] as List?)?.cast<Map<String, dynamic>>() ?? [];
        state = state.copyWith(
          alerts: raw.map(AlertItem.fromJson).toList(),
          unread: (d['unread'] as int?) ?? 0,
          loading: false,
        );
      } else {
        state =
            state.copyWith(loading: false, error: 'HTTP ${r.statusCode}');
      }
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  /// Mark a single alert as read (optimistic update + API call).
  Future<void> markRead(int alertId) async {
    // Optimistic update
    state = state.copyWith(
      alerts: state.alerts
          .map((a) => a.id == alertId ? a.asRead() : a)
          .toList(),
      unread: (state.unread - 1).clamp(0, state.unread),
    );
    try {
      await _client
          .patch(
            Uri.parse('$_base/api/alerts/$alertId/read'),
            headers: _headers,
          )
          .timeout(const Duration(seconds: 8));
    } catch (_) {
      // Revert on failure
      await load();
    }
  }

  /// Mark all loaded alerts as read.
  Future<void> markAllRead() async {
    final unreadIds =
        state.alerts.where((a) => !a.isRead).map((a) => a.id).toList();
    for (final id in unreadIds) {
      await markRead(id);
    }
  }

  /// Delete a single alert permanently.
  Future<void> deleteAlert(int alertId) async {
    state = state.copyWith(
      alerts: state.alerts.where((a) => a.id != alertId).toList(),
    );
    try {
      await _client
          .delete(
            Uri.parse('$_base/api/alerts/$alertId'),
            headers: _headers,
          )
          .timeout(const Duration(seconds: 8));
    } catch (_) {
      await load();
    }
  }

  /// Delete all read alerts (bulk clear history).
  Future<void> clearReadAlerts() async {
    state = state.copyWith(
      alerts: state.alerts.where((a) => !a.isRead).toList(),
    );
    try {
      await _client
          .delete(
            Uri.parse('$_base/api/alerts/read'),
            headers: _headers,
          )
          .timeout(const Duration(seconds: 10));
    } catch (_) {
      await load();
    }
  }

  /// Prepend a real-time alert received via Socket.IO.
  void addFromSocket(Map<String, dynamic> data) {
    try {
      final item = AlertItem(
        id: (data['id'] as num?)?.toInt() ?? 0,
        deviceCode: data['device_code']?.toString() ?? '',
        message: data['message']?.toString() ?? '',
        level: data['level']?.toString() ?? 'info',
        isRead: false,
        createdAt:
            data['created_at']?.toString() ?? DateTime.now().toIso8601String(),
      );
      state = state.copyWith(
        alerts: [item, ...state.alerts],
        unread: state.unread + 1,
      );
    } catch (_) {}
  }
}

// ── Provider ──────────────────────────────────────────────────
final alertProvider =
    StateNotifierProvider<AlertNotifier, AlertState>(
  (ref) => AlertNotifier(ref),
);
