import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:smart_home_mobile/modules/sensor/sensor_provider.dart';
import 'package:smart_home_mobile/screens/health_screen.dart';
import 'package:smart_home_mobile/widgets/common_widgets.dart';

class _FakeSensorNotifier extends SensorNotifier {
  _FakeSensorNotifier(
    super.ref, {
    required SensorState initialState,
  }) : super() {
    state = initialState;
  }

  int loadCalls = 0;

  @override
  Future<void> loadHrRecords({int limit = 100}) async {
    loadCalls += 1;
  }
}

HrRecord _record({
  required int bpm,
  required String severity,
  String? mood,
  String? risk,
  required String recordedAt,
}) {
  return HrRecord(
    bpm: bpm,
    severity: severity,
    mood: mood,
    risk: risk,
    recordedAt: recordedAt,
  );
}

Future<void> _pumpHealthScreen(
  WidgetTester tester, {
  required SensorState sensorState,
  void Function(_FakeSensorNotifier notifier)? onNotifier,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        sensorProvider.overrideWith((ref) {
          final notifier = _FakeSensorNotifier(ref, initialState: sensorState);
          onNotifier?.call(notifier);
          return notifier;
        }),
      ],
      child: const MaterialApp(home: HealthScreen()),
    ),
  );

  await tester.pump();
}

Future<void> _disposeScreen(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump();
}

void main() {
  testWidgets('health screen shows loader while loading records', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeSensorNotifier notifier;

    await _pumpHealthScreen(
      tester,
      sensorState: const SensorState(loading: true),
      onNotifier: (value) => notifier = value,
    );

    expect(find.byType(BcLoader), findsOneWidget);
    expect(notifier.loadCalls, 1);
  });

  testWidgets('health screen shows error banner and refresh actions call load', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeSensorNotifier notifier;

    await _pumpHealthScreen(
      tester,
      sensorState: const SensorState(error: 'Sensor backend offline'),
      onNotifier: (value) => notifier = value,
    );

    expect(find.text('Sensor backend offline'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.refresh_rounded));
    await tester.pump();
    expect(notifier.loadCalls, 2);

    await tester.widget<RefreshIndicator>(find.byType(RefreshIndicator)).onRefresh();
    expect(notifier.loadCalls, 3);
  });

  testWidgets('health screen shows no data placeholder without records', (tester) async {
    addTearDown(() async => _disposeScreen(tester));

    await _pumpHealthScreen(
      tester,
      sensorState: const SensorState(),
    );

    expect(find.text('NO RECORDS YET'), findsOneWidget);
    expect(find.text('BPM TIMELINE'), findsNothing);
    expect(find.text('RECENT READINGS'), findsOneWidget);
  });

  testWidgets('health screen renders summary chart severity breakdown and readings', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeSensorNotifier notifier;

    await _pumpHealthScreen(
      tester,
      sensorState: SensorState(
        hrRecords: [
          _record(
            bpm: 72,
            severity: 'normal',
            mood: 'calm',
            risk: 'low',
            recordedAt: '2026-04-15T08:00:00Z',
          ),
          _record(
            bpm: 118,
            severity: 'warning',
            mood: '',
            risk: 'null',
            recordedAt: 'not-a-date',
          ),
          _record(
            bpm: 135,
            severity: 'critical',
            recordedAt: '2026-04-15T08:10:00Z',
          ),
        ],
        summary: const {
          'avg_bpm': 108.4,
          'min_bpm': 72,
          'max_bpm': 135,
          'count': 3,
          'normal_rate_percent': 33.3,
          'severity_counts': {
            'normal': 1,
            'caution': 0,
            'warning': 1,
            'critical': 1,
          },
        },
      ),
      onNotifier: (value) => notifier = value,
    );

    expect(find.text('VITALS SUMMARY'), findsOneWidget);
    expect(find.text('3 records'), findsOneWidget);
    expect(find.text('108.3'), findsWidgets);
    expect(find.text('33.3%'), findsOneWidget);
    expect(find.text('BPM TIMELINE'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('SEVERITY DISTRIBUTION'),
      250,
      scrollable: find.byType(Scrollable).first,
    );

    expect(find.text('SEVERITY DISTRIBUTION'), findsOneWidget);
    expect(find.text('NORMAL'), findsWidgets);
    expect(find.text('CAUTION'), findsOneWidget);
    expect(find.text('WARNING'), findsWidgets);
    expect(find.text('CRITICAL'), findsWidgets);

    await tester.scrollUntilVisible(
      find.text('RECENT READINGS'),
      250,
      scrollable: find.byType(Scrollable).first,
    );

    expect(find.text('RECENT READINGS'), findsOneWidget);
    expect(find.text('· calm'), findsOneWidget);
    expect(find.text('risk: low'), findsOneWidget);
    expect(find.text('not-a-date'), findsOneWidget);
    expect(find.text('risk: null'), findsNothing);

    final chart = tester.widget<LineChart>(find.byType(LineChart));
    final lineData = chart.data.lineBarsData;
    final tooltipItems = chart
        .data.lineTouchData.touchTooltipData.getTooltipItems(
      [
        LineBarSpot(lineData.first, 0, lineData.first.spots[1]),
        LineBarSpot(lineData.last, 1, lineData.last.spots.first),
      ],
    );
    expect(tooltipItems[0]?.text, '118 BPM\nwarning');
    expect(tooltipItems[1], isNull);

    await tester.tap(find.byIcon(Icons.refresh_rounded));
    await tester.pump();
    expect(notifier.loadCalls, 2);
  });

  testWidgets('health screen hides summary and chart when data is insufficient', (tester) async {
    addTearDown(() async => _disposeScreen(tester));

    await _pumpHealthScreen(
      tester,
      sensorState: SensorState(
        hrRecords: [
          _record(
            bpm: 88,
            severity: 'caution',
            recordedAt: '2026-04-15T08:00:00Z',
          ),
        ],
      ),
    );

    expect(find.text('VITALS SUMMARY'), findsOneWidget);
    expect(find.text('BPM TIMELINE'), findsNothing);
    expect(find.text('88'), findsWidgets);
    expect(find.text('CAUTION'), findsWidgets);
  });
}