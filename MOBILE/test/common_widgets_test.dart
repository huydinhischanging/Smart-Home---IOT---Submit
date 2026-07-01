import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_home_mobile/core/bc.dart';
import 'package:smart_home_mobile/widgets/common_widgets.dart';

void main() {
  testWidgets('common widgets render visible labels and values', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(
            children: const [
              BcPill(label: 'ONLINE', color: BC.green),
              BcSectionHeader(label: 'DEVICES', count: 3),
              BcStat(val: '12', label: 'ACTIVE', emoji: '⚡', color: BC.gold),
              BcMissionCard(
                devices: [
                  {'is_on': true},
                  {'is_on': false},
                ],
                rooms: [
                  {'id': 1},
                  {'id': 2},
                ],
              ),
              BcToggle(isOn: true, color: BC.green),
              BcErrBanner(msg: 'Cannot reach cave server.'),
              BcEmpty(),
              BcLegendDot(color: BC.cyan, label: 'NORMAL'),
            ],
          ),
        ),
      ),
    );

    expect(find.text('ONLINE'), findsOneWidget);
    expect(find.text('DEVICES'), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
    expect(find.text('12'), findsOneWidget);
    expect(find.text('ACTIVE'), findsOneWidget);
    expect(find.text('LIVE MISSION'), findsOneWidget);
    expect(find.textContaining('1 device(s) are active across 2 zone(s)'), findsOneWidget);
    expect(find.text('Cannot reach cave server.'), findsOneWidget);
    expect(find.text('NO DEVICES FOUND'), findsOneWidget);
    expect(find.text('NORMAL'), findsOneWidget);
  });

  testWidgets('mission card standby branch and loader render', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              BcMissionCard(devices: [], rooms: []),
              Expanded(child: BcLoader()),
            ],
          ),
        ),
      ),
    );

    expect(find.text('0%'), findsOneWidget);
    expect(find.textContaining('All systems in standby'), findsOneWidget);
    expect(find.text('INITIALIZING SYSTEMS'), findsOneWidget);
    expect(find.byType(AnimatedBuilder), findsWidgets);
  });

  testWidgets('ring gauge updates and scene button taps', (tester) async {
    var tapped = 0;
    const gaugeKey = ValueKey('ring');

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              const BcRingGauge(
                key: gaugeKey,
                value: 0.75,
                centerVal: '72',
                centerLabel: 'BPM',
                color: BC.red,
                size: 100,
              ),
              BcSceneBtn(
                emoji: '🌙',
                label: 'SLEEP',
                color: BC.gold,
                onTap: () => tapped += 1,
              ),
            ],
          ),
        ),
      ),
    );

    await tester.pump(const Duration(milliseconds: 950));
    expect(find.text('72'), findsOneWidget);
    expect(find.text('BPM'), findsOneWidget);
    expect(find.text('SLEEP'), findsOneWidget);

    await tester.tap(find.text('SLEEP'));
    expect(tapped, 1);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              const BcRingGauge(
                key: gaugeKey,
                value: 0.20,
                centerVal: '60',
                centerLabel: 'BPM',
                color: BC.cyan,
                size: 100,
              ),
              BcSceneBtn(
                emoji: '🌙',
                label: 'SLEEP',
                color: BC.gold,
                onTap: () => tapped += 1,
              ),
            ],
          ),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 950));
    expect(find.text('60'), findsOneWidget);
  });

  testWidgets('notification tile formats severity, unread marker, fallback content, and invalid timestamp', (tester) async {
    var taps = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              BcNotifTile(
                alert: const {
                  'level': 'critical',
                  'message': 'Door forced open',
                  'created_at': '2026-04-15T08:30:00Z',
                  'is_read': false,
                },
                onTap: () => taps += 1,
              ),
              const BcNotifTile(
                alert: {
                  'severity': 'caution',
                  'content': 'Living room warm',
                  'timestamp': 'not-a-date',
                  'read': true,
                },
              ),
            ],
          ),
        ),
      ),
    );

    expect(find.text('CRITICAL'), findsOneWidget);
    expect(find.text('CAUTION'), findsOneWidget);
    expect(find.text('Door forced open'), findsOneWidget);
    expect(find.text('Living room warm'), findsOneWidget);
    expect(find.textContaining('/'), findsOneWidget);

    await tester.tap(find.text('Door forced open'));
    expect(taps, 1);
  });

  test('severity helper returns expected colors', () {
    expect(bcSeverityColor('critical'), BC.red);
    expect(bcSeverityColor('warning'), BC.gold);
    expect(bcSeverityColor('caution'), const Color(0xFFFF8844));
    expect(bcSeverityColor('info'), BC.cyan);
    expect(bcSeverityColor(null), BC.cyan);
  });
}