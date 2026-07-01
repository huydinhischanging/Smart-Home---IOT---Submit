// lib/modules/sensor/sensor_provider.dart
// Riverpod provider for heart-rate records and patient summary.
import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/api_headers.dart';
import '../../core/api_context_provider.dart';
import '../../core/http_client_provider.dart';
import '../../core/socket_service.dart';

// ── Model ─────────────────────────────────────────────────────
class HrRecord {
  final int bpm;
  final String severity;
  final String? mood;
  final String? risk;
  final String recordedAt;

  const HrRecord({
    required this.bpm,
    required this.severity,
    this.mood,
    this.risk,
    required this.recordedAt,
  });

  factory HrRecord.fromJson(Map<String, dynamic> j) => HrRecord(
        bpm: (j['bpm'] as num?)?.toInt() ?? 0,
        severity: j['severity']?.toString() ?? 'normal',
        mood: j['mood']?.toString(),
        risk: j['risk']?.toString(),
        recordedAt: j['recorded_at']?.toString() ?? '',
      );

  bool get isAbnormal =>
      severity == 'warning' || severity == 'critical' || severity == 'caution';
}

// ── State ─────────────────────────────────────────────────────
class SensorState {
  final List<HrRecord> hrRecords;
  final Map<String, dynamic>? summary;
  final Map<String, dynamic>? hrvSummary;
  final bool loading;
  final String? error;

  const SensorState({
    this.hrRecords = const [],
    this.summary,
    this.hrvSummary,
    this.loading = false,
    this.error,
  });

  SensorState copyWith({
    List<HrRecord>? hrRecords,
    Map<String, dynamic>? summary,
    Map<String, dynamic>? hrvSummary,
    bool? loading,
    String? error,
  }) =>
      SensorState(
        hrRecords: hrRecords ?? this.hrRecords,
        summary: summary ?? this.summary,
        hrvSummary: hrvSummary ?? this.hrvSummary,
        loading: loading ?? this.loading,
        error: error,
      );

  // Convenience getters derived from summary
  int? get avgBpm =>
      summary != null ? (summary!['avg_bpm'] as num?)?.toInt() : null;
  int? get maxBpm =>
      summary != null ? (summary!['max_bpm'] as num?)?.toInt() : null;
  int? get minBpm =>
      summary != null ? (summary!['min_bpm'] as num?)?.toInt() : null;
  double? get normalRatePercent =>
      summary != null ? (summary!['normal_rate_percent'] as num?)?.toDouble() : null;
}

// ── Notifier ──────────────────────────────────────────────────
class SensorNotifier extends StateNotifier<SensorState> {
  final Ref _ref;
  StreamSubscription<Map<String, dynamic>>? _socketSub;
  StreamSubscription<Map<String, dynamic>>? _hrAlertSub;

  SensorNotifier(this._ref) : super(const SensorState()) {
    _subscribeSocket();
  }

  void _subscribeSocket() {
    final socketService = _ref.read(socketServiceProvider);
    // Live BPM updates from MQTT (all readings)
    _socketSub = socketService.onDeviceUpdate.listen((data) {
      final code = data['code']?.toString() ?? data['device_name']?.toString() ?? '';
      if (code == 'heart_rate') {
        final bpm = (data['heart_rate'] ?? data['value']);
        if (bpm == null) return;
        final bpmInt = (bpm as num).toInt();
        appendLiveReading(bpm: bpmInt);
      }
    });
    // hr_alert events (abnormal readings with severity/mood/risk info)
    _hrAlertSub = socketService.onHrAlert.listen((data) {
      final bpm = data['bpm'];
      if (bpm == null) return;
      appendLiveReading(
        bpm: (bpm as num).toInt(),
        severity: data['severity']?.toString() ?? 'normal',
        mood: data['mood']?.toString(),
        risk: data['risk']?.toString(),
      );
    });
  }

  @override
  void dispose() {
    _socketSub?.cancel();
    _hrAlertSub?.cancel();
    super.dispose();
  }

    String get _base => _ref.read(apiBaseUrlProvider);
  http.Client get _client => _ref.read(httpClientProvider);
  Map<String, String> get _headers =>
      apiJsonHeaders(_ref.read(authHeadersProvider));

  /// Load HRV summary metrics from the patient report API.
  Future<void> loadHrvSummary({int limit = 500}) async {
    try {
      final r = await _client
          .get(
            Uri.parse('$_base/api/patient/hrv/summary?limit=$limit'),
            headers: _headers,
          )
          .timeout(const Duration(seconds: 12));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body) as Map<String, dynamic>;
        final hrv = d['hrv'] as Map<String, dynamic>? ?? d;
        state = state.copyWith(hrvSummary: hrv);
      }
    } catch (_) {
      // Non-critical: HRV data is optional
    }
  }

  /// Load heart-rate records from the patient report API.
  Future<void> loadHrRecords({int limit = 100}) async {
    state = state.copyWith(loading: true);
    try {
      final r = await _client
          .get(
            Uri.parse('$_base/api/patient/hr-records?limit=$limit'),
            headers: _headers,
          )
          .timeout(const Duration(seconds: 12));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body) as Map<String, dynamic>;
        final raw =
            (d['records'] as List?)?.cast<Map<String, dynamic>>() ?? [];
        state = state.copyWith(
          hrRecords: raw.map(HrRecord.fromJson).toList(),
          summary: d['summary'] as Map<String, dynamic>?,
          loading: false,
        );
      } else if (r.statusCode == 401) {
        state = state.copyWith(loading: false, error: 'Session expired.');
      } else {
        state = state.copyWith(
            loading: false, error: 'HTTP ${r.statusCode}');
      }
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  /// Append a newly received BPM reading (e.g. from MQTT/socket) to local state.
  void appendLiveReading({
    required int bpm,
    String severity = 'normal',
    String? mood,
    String? risk,
  }) {
    final record = HrRecord(
      bpm: bpm,
      severity: severity,
      mood: mood,
      risk: risk,
      recordedAt: DateTime.now().toIso8601String(),
    );
    state = state.copyWith(hrRecords: [...state.hrRecords, record]);
  }
}

// ── Provider ──────────────────────────────────────────────────
final sensorProvider =
    StateNotifierProvider<SensorNotifier, SensorState>(
  (ref) => SensorNotifier(ref),
);
