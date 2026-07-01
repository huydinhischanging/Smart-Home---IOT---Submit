import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smart_home_mobile/core/api_context_provider.dart';
import 'package:smart_home_mobile/core/http_client_provider.dart';
import 'package:smart_home_mobile/modules/sensor/sensor_provider.dart';

ProviderContainer _makeContainer(http.Client client) {
  return ProviderContainer(overrides: [
    apiBaseUrlProvider.overrideWithValue('http://example.test'),
    authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
    httpClientProvider.overrideWithValue(client),
  ]);
}

void main() {
  test('hr record model and sensor state getters expose derived values', () {
    final record = HrRecord.fromJson({
      'bpm': 110.6,
      'severity': 'caution',
      'mood': 'anxious',
      'risk': 'medium',
      'recorded_at': '2026-04-15T10:00:00Z',
    });
    const fallbackRecord = HrRecord(
      bpm: 60,
      severity: 'normal',
      recordedAt: '2026-04-15T10:05:00Z',
    );
    const state = SensorState(
      summary: {
        'avg_bpm': 88.5,
        'max_bpm': 120,
        'min_bpm': 60,
        'normal_rate_percent': 75.5,
      },
    );

    expect(record.bpm, 110);
    expect(record.isAbnormal, true);
    expect(fallbackRecord.isAbnormal, false);
    expect(state.avgBpm, 88);
    expect(state.maxBpm, 120);
    expect(state.minBpm, 60);
    expect(state.normalRatePercent, 75.5);
  });

  test('sensor provider loads hr records and summary', () async {
    final client = MockClient(
      (_) async => http.Response(
        '{"records":[{"bpm":72,"severity":"normal","recorded_at":"2026-04-14T10:00:00Z"},{"bpm":128,"severity":"warning","recorded_at":"2026-04-14T10:01:00Z"}],"summary":{"avg_bpm":100.0,"max_bpm":128,"min_bpm":72,"normal_rate_percent":50.0}}',
        200,
      ),
    );

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    await container.read(sensorProvider.notifier).loadHrRecords();
    final state = container.read(sensorProvider);

    expect(state.hrRecords, hasLength(2));
    expect(state.avgBpm, 100);
    expect(state.maxBpm, 128);
    expect(state.hrRecords.last.isAbnormal, true);
  });

  test('sensor provider surfaces auth, HTTP, and exception errors', () async {
    var mode = 0;
    final client = MockClient((_) async {
      mode += 1;
      if (mode == 1) {
        return http.Response('Denied', 401);
      }
      if (mode == 2) {
        return http.Response('Boom', 500);
      }
      throw http.ClientException('offline');
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(sensorProvider.notifier);

    await notifier.loadHrRecords(limit: 5);
    expect(container.read(sensorProvider).error, 'Session expired.');

    await notifier.loadHrRecords(limit: 6);
    expect(container.read(sensorProvider).error, 'HTTP 500');

    await notifier.loadHrRecords(limit: 7);
    expect(container.read(sensorProvider).error, contains('offline'));
    expect(container.read(sensorProvider).loading, false);
  });

  test('sensor provider appends live readings locally', () {
    final container = _makeContainer(MockClient((_) async => http.Response('{}', 200)));
    addTearDown(container.dispose);
    final notifier = container.read(sensorProvider.notifier);

    notifier.appendLiveReading(
      bpm: 130,
      severity: 'critical',
      mood: 'panic',
      risk: 'high',
    );

    final state = container.read(sensorProvider);
    expect(state.hrRecords, hasLength(1));
    expect(state.hrRecords.single.bpm, 130);
    expect(state.hrRecords.single.isAbnormal, true);
    expect(state.hrRecords.single.recordedAt, isNotEmpty);
  });
}