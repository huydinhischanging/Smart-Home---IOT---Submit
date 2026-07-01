import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_home_mobile/core/bc.dart';

Widget _wrap(Widget child) {
  return ProviderScope(
    child: MaterialApp(home: Scaffold(body: child)),
  );
}

Future<void> _flushMicrotasks() async {
  for (var index = 0; index < 4; index += 1) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('buildAppTheme and AppMood metadata expose expected values', () {
    final theme = buildAppTheme(accent: BC.red);

    expect(theme.scaffoldBackgroundColor, Colors.transparent);
    expect(theme.colorScheme.primary, BC.red);
    expect(theme.colorScheme.secondary, BC.cyan);
    expect(theme.inputDecorationTheme.fillColor, BC.elevated);

    expect(AppMood.normal.label, 'NORMAL');
    expect(AppMood.normal.emoji, '🦇');
    expect(AppMood.normal.accent, const Color(0xFFFFBE00));
    expect(AppMood.normal.accentDim, const Color(0x22FFBE00));
    expect(AppMood.normal.bgColor, const Color(0xFF020509));

    expect(AppMood.emergency.label, 'EMERGENCY');
    expect(AppMood.emergency.emoji, '🚨');
    expect(AppMood.emergency.accent, const Color(0xFFFF3355));
    expect(AppMood.emergency.accentDim, const Color(0x22FF3355));
    expect(AppMood.emergency.bgColor, const Color(0xFF0A0002));

    expect(AppMood.meditation.label, 'MEDITATION');
    expect(AppMood.meditation.emoji, '🔮');
    expect(AppMood.meditation.accent, const Color(0xFFA855F7));
    expect(AppMood.meditation.accentDim, const Color(0x22A855F7));
    expect(AppMood.meditation.bgColor, const Color(0xFF030208));

    expect(AppMood.stealth.label, 'STEALTH');
    expect(AppMood.stealth.emoji, '🌿');
    expect(AppMood.stealth.accent, const Color(0xFF48A999));
    expect(AppMood.stealth.accentDim, const Color(0x2248A999));
    expect(AppMood.stealth.bgColor, const Color(0xFF010404));
  });

  testWidgets('tactical backdrop and typing indicator render painter-driven UI', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const Column(
          children: [
            Expanded(child: TacticalBackdrop()),
            TypingIndicator(),
          ],
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byType(CustomPaint), findsWidgets);
    expect(find.byType(AnimatedBuilder), findsWidgets);

    final painter = BackdropGridPainter();
    expect(painter.shouldRepaint(BackdropGridPainter()), false);
  });

  test('mood provider loads persisted value, clamps invalid index, and badge provider is mutable', () async {
    SharedPreferences.setMockInitialValues({'app_mood': 99});
    final container = ProviderContainer();
    addTearDown(container.dispose);

    expect(container.read(moodProvider), AppMood.normal);
    container.read(moodProvider.notifier);
    await _flushMicrotasks();
    expect(container.read(moodProvider), AppMood.stealth);

    expect(container.read(notifBadgeProvider), 0);
    container.read(notifBadgeProvider.notifier).state = 7;
    expect(container.read(notifBadgeProvider), 7);
  });

  test('mood notifier persists selected mood', () async {
    SharedPreferences.setMockInitialValues({});
    final notifier = MoodNotifier();
    addTearDown(notifier.dispose);

    await notifier.set(AppMood.emergency);
    final prefs = await SharedPreferences.getInstance();

    expect(notifier.state, AppMood.emergency);
    expect(prefs.getInt('app_mood'), AppMood.emergency.index);
  });
}