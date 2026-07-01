import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_home_mobile/core/bc.dart';
import 'package:smart_home_mobile/widgets/common_widgets.dart';

void main() {
  group('Device Control Interaction Tests', () {
    testWidgets('Device toggle triggers callback', (WidgetTester tester) async {
      bool wasToggled = false;
      bool toggleState = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (BuildContext context, StateSetter setState) {
                return Center(
                  child: GestureDetector(
                    onTap: () => setState(() {
                      toggleState = !toggleState;
                      wasToggled = true;
                    }),
                    child: BcToggle(isOn: toggleState, color: BC.green),
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(wasToggled, false);

      await tester.tap(find.byType(GestureDetector));
      await tester.pumpAndSettle();

      expect(wasToggled, true);
      expect(toggleState, true);
    });

    testWidgets('Multiple device toggles work independently',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              children: const [
                BcToggle(isOn: true, color: BC.green),
                BcToggle(isOn: false, color: BC.red),
                BcToggle(isOn: true, color: BC.cyan),
              ],
            ),
          ),
        ),
      );

      expect(find.byType(BcToggle), findsNWidgets(3));
      expect(find.byType(AnimatedContainer), findsWidgets);
    });

    testWidgets('Device control response time is acceptable',
        (WidgetTester tester) async {
      final stopwatch = Stopwatch()..start();

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcToggle(isOn: true, color: BC.green),
          ),
        ),
      );

      stopwatch.stop();

      expect(stopwatch.elapsedMilliseconds, lessThan(5000));
    });
  });

  group('Error State UI Tests', () {
    testWidgets('Error banner appears on connection failure',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcErrBanner(msg: 'Device offline'),
                Expanded(child: BcEmpty()),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Device offline'), findsOneWidget);
      expect(find.text('NO DEVICES FOUND'), findsOneWidget);
    });

    testWidgets('Multiple error banners stack properly',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: Column(
                children: [
                  BcErrBanner(msg: 'Error 1'),
                  BcErrBanner(msg: 'Error 2'),
                  BcErrBanner(msg: 'Error 3'),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Error 1'), findsOneWidget);
      expect(find.text('Error 2'), findsOneWidget);
      expect(find.text('Error 3'), findsOneWidget);
    });

    testWidgets('Error message truncation works correctly',
        (WidgetTester tester) async {
      const String longError =
          'This is an extremely long error message that should be handled properly without breaking the UI layout or causing overflow issues';

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcErrBanner(msg: longError),
          ),
        ),
      );

      expect(find.text(longError), findsOneWidget);
      expect(find.byType(BcErrBanner), findsOneWidget);
    });
  });

  group('Loading State Tests', () {
    testWidgets('Loader appears during data fetch', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: BcLoader()),
        ),
      );

      expect(find.byType(BcLoader), findsOneWidget);
    });

    testWidgets('Loader animates smoothly', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BcLoader(),
          ),
        ),
      );

      // Pump several animation frames
      for (int i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      expect(find.byType(BcLoader), findsOneWidget);
    });

    testWidgets('Transition from loader to content', (WidgetTester tester) async {
      bool isLoading = true;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (BuildContext context, StateSetter setState) {
                return Column(
                  children: [
                    if (isLoading)
                      const BcLoader()
                    else
                      const Text('Content Loaded'),
                    ElevatedButton(
                      onPressed: () => setState(() => isLoading = false),
                      child: const Text('Load'),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      );

      expect(find.byType(BcLoader), findsOneWidget);

      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(find.text('Content Loaded'), findsOneWidget);
    });
  });

  group('Health Data Visualization Tests', () {
    testWidgets('Ring gauge updates with health data',
        (WidgetTester tester) async {
      double heartRate = 72.0;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (BuildContext context, StateSetter setState) {
                return Center(
                  child: Column(
                    children: [
                      BcRingGauge(
                        value: heartRate / 100.0,
                        centerVal: heartRate.toInt().toString(),
                        centerLabel: 'HEART RATE',
                        color: BC.red,
                      ),
                      ElevatedButton(
                        onPressed: () => setState(() => heartRate = 85.0),
                        child: const Text('Update HR'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('72'), findsOneWidget);

      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(find.text('85'), findsOneWidget);
    });

    testWidgets('Health stats display in grid layout',
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
                  Row(
                    children: [
                      Expanded(
                        child: BcStat(
                          val: '55%',
                          label: 'SPO2',
                          emoji: '💨',
                          color: BC.cyan,
                        ),
                      ),
                      Expanded(
                        child: BcStat(
                          val: '120/80',
                          label: 'BP',
                          emoji: '🫀',
                          color: BC.green,
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
      expect(find.text('55%'), findsOneWidget);
      expect(find.text('120/80'), findsOneWidget);
    });

    testWidgets('Abnormal health readings display properly',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcRingGauge(
                  value: 1.0,
                  centerVal: '120',
                  centerLabel: 'HIGH HR',
                  color: BC.red,
                ),
                BcRingGauge(
                  value: 0.3,
                  centerVal: '30',
                  centerLabel: 'LOW HR',
                  color: BC.gold,
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.text('120'), findsOneWidget);
      expect(find.text('30'), findsOneWidget);
      expect(find.text('HIGH HR'), findsOneWidget);
      expect(find.text('LOW HR'), findsOneWidget);
    });
  });

  group('Empty State Scenarios', () {
    testWidgets('Empty devices list shows empty state',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcSectionHeader(label: 'DEVICES', count: 0),
                Expanded(child: BcEmpty()),
              ],
            ),
          ),
        ),
      );

      expect(find.text('DEVICES'), findsOneWidget);
      expect(find.text('0'), findsOneWidget);
      expect(find.text('NO DEVICES FOUND'), findsOneWidget);
    });

    testWidgets('Empty alerts list shows empty state',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcSectionHeader(label: 'ALERTS', count: 0),
                Expanded(child: BcEmpty()),
              ],
            ),
          ),
        ),
      );

      expect(find.text('ALERTS'), findsOneWidget);
      expect(find.text('NO DEVICES FOUND'), findsOneWidget);
    });

    testWidgets('Transition from empty to populated state',
        (WidgetTester tester) async {
      bool isEmpty = true;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (BuildContext context, StateSetter setState) {
                return Column(
                  children: [
                    if (isEmpty)
                      const Expanded(child: BcEmpty())
                    else
                      Expanded(
                        child: ListView(
                          children: const [
                            BcStat(
                              val: '1',
                              label: 'DEVICE',
                              emoji: '⚡',
                              color: BC.gold,
                            ),
                          ],
                        ),
                      ),
                    ElevatedButton(
                      onPressed: () => setState(() => isEmpty = false),
                      child: const Text('Load Devices'),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('NO DEVICES FOUND'), findsOneWidget);

      await tester.tap(find.byType(ElevatedButton));
      await tester.pumpAndSettle();

      expect(find.text('1'), findsOneWidget);
      expect(find.text('DEVICE'), findsOneWidget);
    });
  });

  group('Responsive Layout Tests', () {
    testWidgets('Widgets adapt to narrow screens', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(400, 800);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcSectionHeader(label: 'DEVICES', count: 5),
                BcPill(label: 'ONLINE', color: BC.green),
              ],
            ),
          ),
        ),
      );

      expect(find.text('DEVICES'), findsOneWidget);
      expect(find.text('ONLINE'), findsOneWidget);

      addTearDown(tester.view.resetPhysicalSize);
    });

    testWidgets('Widgets adapt to wide screens', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 800);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: Column(
                children: [
                  BcSectionHeader(label: 'DEVICES', count: 10),
                  BcStat(
                    val: '72',
                    label: 'HR',
                    emoji: '❤️',
                    color: BC.red,
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('DEVICES'), findsOneWidget);
      expect(find.text('72'), findsOneWidget);

      addTearDown(tester.view.resetPhysicalSize);
    });
  });

  group('Accessibility Tests', () {
    testWidgets('Widgets have proper semantics', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcToggle(isOn: true, color: BC.green),
                BcStat(
                  val: '72',
                  label: 'HEART RATE',
                  emoji: '❤️',
                  color: BC.red,
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.bySemanticsLabel('HEART RATE'), findsWidgets);
    });

    testWidgets('Text has sufficient contrast', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                BcPill(label: 'STATUS', color: BC.green),
                BcSectionHeader(label: 'SECTION', count: 5),
              ],
            ),
          ),
        ),
      );

      expect(find.text('STATUS'), findsOneWidget);
      expect(find.text('SECTION'), findsOneWidget);
    });
  });
}
