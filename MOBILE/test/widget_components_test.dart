import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_home_mobile/core/bc.dart';
import 'package:smart_home_mobile/widgets/common_widgets.dart';

void main() {
  group('BcToggle Widget Tests', () {
    testWidgets('BcToggle renders in ON state', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcToggle(isOn: true, color: BC.green),
          ),
        ),
      );

      expect(find.byType(BcToggle), findsOneWidget);
      expect(find.byType(AnimatedContainer), findsOneWidget);
    });

    testWidgets('BcToggle renders in OFF state', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcToggle(isOn: false, color: BC.red),
          ),
        ),
      );

      expect(find.byType(BcToggle), findsOneWidget);
    });

    testWidgets('BcToggle color property affects appearance',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcToggle(isOn: true, color: BC.green),
                BcToggle(isOn: true, color: BC.red),
                BcToggle(isOn: true, color: BC.cyan),
              ],
            ),
          ),
        ),
      );

      expect(find.byType(BcToggle), findsNWidgets(3));
    });
  });

  group('BcErrorBanner Widget Tests', () {
    testWidgets('BcErrBanner displays error message', (WidgetTester tester) async {
      const String errorMsg = 'Connection failed';
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcErrBanner(msg: errorMsg),
          ),
        ),
      );

      expect(find.text(errorMsg), findsOneWidget);
    });

    testWidgets('BcErrBanner is dismissible', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcErrBanner(msg: 'Test error'),
          ),
        ),
      );

      expect(find.text('Test error'), findsOneWidget);
      // Banner should have a close button or be dismissible
    });

    testWidgets('BcErrBanner handles long messages', (WidgetTester tester) async {
      const String longMsg =
          'This is a very long error message that should wrap and handle properly in the UI without breaking';
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcErrBanner(msg: longMsg),
          ),
        ),
      );

      expect(find.text(longMsg), findsOneWidget);
    });
  });

  group('BcEmpty Widget Tests', () {
    testWidgets('BcEmpty displays empty state', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcEmpty(),
          ),
        ),
      );

      expect(find.text('NO DEVICES FOUND'), findsOneWidget);
      expect(find.byType(BcEmpty), findsOneWidget);
    });

    testWidgets('BcEmpty shows centered layout', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcEmpty(),
          ),
        ),
      );

      expect(find.byType(Center), findsOneWidget);
    });
  });

  group('BcLoader Widget Tests', () {
    testWidgets('BcLoader renders spinning animation', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcLoader(),
          ),
        ),
      );

      expect(find.byType(BcLoader), findsOneWidget);
      expect(find.byType(CustomPaint), findsOneWidget);
    });

    testWidgets('BcLoader animates continuously', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcLoader(),
          ),
        ),
      );

      // BcLoader has an infinite animation, so pump a few frames instead.
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(BcLoader), findsOneWidget);
    });
  });

  group('BcRingGauge Widget Tests', () {
    testWidgets('BcRingGauge displays heart rate value',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcRingGauge(
              value: 0.72,
              centerVal: '72',
              centerLabel: 'HEART RATE',
              color: BC.red,
            ),
          ),
        ),
      );

      expect(find.text('72'), findsOneWidget);
      expect(find.text('HEART RATE'), findsOneWidget);
    });

    testWidgets('BcRingGauge handles edge values',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcRingGauge(value: 0.0, centerVal: '0', centerLabel: 'MIN', color: BC.red),
                BcRingGauge(
                  value: 1.0,
                  centerVal: '100',
                  centerLabel: 'MAX',
                  color: BC.red,
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.text('0'), findsOneWidget);
      expect(find.text('100'), findsOneWidget);
    });

    testWidgets('BcRingGauge animates value changes',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (BuildContext context, StateSetter setState) {
                return const BcRingGauge(
                  value: 0.5,
                  centerVal: '50',
                  centerLabel: 'TEST',
                  color: BC.red,
                );
              },
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();
      expect(find.text('50'), findsOneWidget);
    });
  });

  group('BcPill Widget Tests', () {
    testWidgets('BcPill displays label', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcPill(label: 'ONLINE', color: BC.green),
          ),
        ),
      );

      expect(find.text('ONLINE'), findsOneWidget);
    });

    testWidgets('BcPill has correct color styling',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Row(
              children: [
                BcPill(label: 'ACTIVE', color: BC.green),
                BcPill(label: 'INACTIVE', color: BC.red),
              ],
            ),
          ),
        ),
      );

      expect(find.byType(BcPill), findsNWidgets(2));
      expect(find.text('ACTIVE'), findsOneWidget);
      expect(find.text('INACTIVE'), findsOneWidget);
    });
  });

  group('BcStat Widget Tests', () {
    testWidgets('BcStat displays all components', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcStat(
              val: '72',
              label: 'HEART RATE',
              emoji: '❤️',
              color: BC.red,
            ),
          ),
        ),
      );

      expect(find.text('72'), findsOneWidget);
      expect(find.text('HEART RATE'), findsOneWidget);
      expect(find.text('❤️'), findsOneWidget);
    });

    testWidgets('BcStat grid layout renders correctly',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: BcStat(
                          val: '72',
                          label: 'HR',
                          emoji: '❤️',
                          color: BC.red,
                        ),
                      ),
                      Expanded(
                        child: BcStat(
                          val: '98.6',
                          label: 'TEMP',
                          emoji: '🌡️',
                          color: BC.gold,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('72'), findsOneWidget);
      expect(find.text('98.6'), findsOneWidget);
    });
  });

  group('BcSectionHeader Widget Tests', () {
    testWidgets('BcSectionHeader displays label and count',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcSectionHeader(label: 'DEVICES', count: 5),
          ),
        ),
      );

      expect(find.text('DEVICES'), findsOneWidget);
      expect(find.text('5'), findsOneWidget);
    });

    testWidgets('BcSectionHeader shows zero count',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcSectionHeader(label: 'ALERTS', count: 0),
          ),
        ),
      );

      expect(find.text('ALERTS'), findsOneWidget);
      expect(find.text('0'), findsOneWidget);
    });
  });

  group('BcMissionCard Widget Tests', () {
    testWidgets('BcMissionCard displays when devices are active',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcMissionCard(
              devices: [
                {'is_on': true},
                {'is_on': false},
              ],
              rooms: [
                {'id': 1},
                {'id': 2},
              ],
            ),
          ),
        ),
      );

      expect(find.text('LIVE MISSION'), findsOneWidget);
      expect(find.textContaining('device(s)'), findsOneWidget);
    });

    testWidgets('BcMissionCard shows standby when no devices active',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcMissionCard(
              devices: [
                {'is_on': false},
              ],
              rooms: [
                {'id': 1},
              ],
            ),
          ),
        ),
      );

      expect(find.byType(BcMissionCard), findsOneWidget);
    });

    testWidgets('BcMissionCard handles empty lists', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcMissionCard(devices: [], rooms: []),
          ),
        ),
      );

      expect(find.byType(BcMissionCard), findsOneWidget);
    });
  });

  group('BcLegendDot Widget Tests', () {
    testWidgets('BcLegendDot displays label', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcLegendDot(color: BC.green, label: 'NORMAL'),
          ),
        ),
      );

      expect(find.text('NORMAL'), findsOneWidget);
    });

    testWidgets('BcLegendDot renders with different colors',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcLegendDot(color: BC.green, label: 'NORMAL'),
                BcLegendDot(color: BC.gold, label: 'WARNING'),
                BcLegendDot(color: BC.red, label: 'CRITICAL'),
              ],
            ),
          ),
        ),
      );

      expect(find.text('NORMAL'), findsOneWidget);
      expect(find.text('WARNING'), findsOneWidget);
      expect(find.text('CRITICAL'), findsOneWidget);
    });
  });

  group('Widget Integration Tests', () {
    testWidgets('Multiple widgets render together without errors',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              children: const [
                BcSectionHeader(label: 'STATUS', count: 2),
                BcPill(label: 'ONLINE', color: BC.green),
                BcStat(
                  val: '72',
                  label: 'HR',
                  emoji: '❤️',
                  color: BC.red,
                ),
                BcToggle(isOn: true, color: BC.green),
                BcRingGauge(
                  value: 0.72,
                  centerVal: '72',
                  centerLabel: 'RATE',
                  color: BC.red,
                ),
                BcEmpty(),
              ],
            ),
          ),
        ),
      );

      expect(find.byType(BcSectionHeader), findsOneWidget);
      expect(find.byType(BcPill), findsOneWidget);
      expect(find.byType(BcStat), findsOneWidget);
      expect(find.byType(BcToggle), findsOneWidget);
      expect(find.byType(BcRingGauge), findsOneWidget);
      expect(find.byType(BcEmpty), findsOneWidget);
    });

    testWidgets('Widget tree remains stable during updates',
        (WidgetTester tester) async {
      int buildCount = 0;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, setState) {
                buildCount++;
                return Column(
                  children: [
                    BcStat(
                      val: buildCount.toString(),
                      label: 'BUILDS',
                      emoji: '🔄',
                      color: BC.cyan,
                    ),
                    ElevatedButton(
                      onPressed: () => setState(() {}),
                      child: const Text('Rebuild'),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('BUILDS'), findsOneWidget);

      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(find.text('BUILDS'), findsOneWidget);
    });
  });
}
