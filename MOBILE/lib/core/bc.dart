import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:math' as math;

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// BATMAN OS COLOR SYSTEM
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class BC {
  static const bg        = Color(0xFF020509);
  static const panel     = Color(0xFF070E1C);
  static const card      = Color(0xFF0B1527);
  static const elevated  = Color(0xFF101E35);
  static const panelHi   = Color(0xFF15243C);

  static const gold      = Color(0xFFFFBE00);
  static const goldDim   = Color(0x22FFBE00);
  static const goldBorder= Color(0x55FFBE00);

  static const cyan      = Color(0xFF00D8FF);
  static const cyanDim   = Color(0x1500D8FF);

  static const green     = Color(0xFF00FF88);
  static const red       = Color(0xFFFF2244);
  static const purple    = Color(0xFFAA55FF);

  static const txt       = Color(0xFFB8CCE8);
  static const txtDim    = Color(0xFF3A5070);
  static const border    = Color(0x2AFFBE00);
  static const borderHi  = Color(0x88FFBE00);
}

// â”€â”€ Tactical backdrop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class TacticalBackdrop extends StatelessWidget {
  const TacticalBackdrop({super.key});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Stack(
        children: [
          const Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Color(0xFF060B16),
                    BC.bg,
                    Color(0xFF010305),
                  ],
                ),
              ),
            ),
          ),
          Positioned(
            top: -90, right: -60,
            child: Container(
              width: 220, height: 220,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [BC.gold.withValues(alpha: 0.18), Colors.transparent],
                ),
              ),
            ),
          ),
          Positioned(
            top: 180, left: -80,
            child: Container(
              width: 180, height: 180,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [BC.cyan.withValues(alpha: 0.12), Colors.transparent],
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: Opacity(
              opacity: 0.24,
              child: CustomPaint(painter: BackdropGridPainter()),
            ),
          ),
        ],
      ),
    );
  }
}

class BackdropGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = BC.gold.withValues(alpha: 0.10)
      ..strokeWidth = 1;
    const spacing = 28.0;
    for (double x = 0; x < size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }
  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// â”€â”€ App theme builder â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ThemeData buildAppTheme({Color accent = BC.gold}) => ThemeData.dark().copyWith(
  scaffoldBackgroundColor: Colors.transparent,
  textTheme: ThemeData.dark().textTheme.apply(
    bodyColor: BC.txt,
    displayColor: BC.txt,
    fontFamily: 'monospace',
  ),
  colorScheme: ColorScheme.dark(
    primary: accent,
    secondary: BC.cyan,
    surface: BC.panel,
    error: BC.red,
  ),
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: BC.elevated,
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: BC.border),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: BC.border),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: BorderSide(color: accent, width: 1.5),
    ),
    labelStyle: const TextStyle(color: BC.txtDim, fontFamily: 'monospace', fontSize: 12),
    hintStyle: const TextStyle(color: BC.txtDim, fontFamily: 'monospace', fontSize: 12),
  ),
);

// â”€â”€ Typing indicator animation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class TypingIndicator extends StatefulWidget {
  const TypingIndicator({super.key});
  @override
  State<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<TypingIndicator>
    with SingleTickerProviderStateMixin {
  late AnimationController _c;
  @override
  void initState() {
    super.initState();
    _c = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1400))
      ..repeat();
  }
  @override
  void dispose() { _c.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext ctx) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
    decoration: BoxDecoration(
      color: BC.cyanDim,
      border: Border.all(color: BC.cyan.withValues(alpha: 0.18)),
      borderRadius: const BorderRadius.only(
        topLeft: Radius.circular(14),
        topRight: Radius.circular(14),
        bottomRight: Radius.circular(14),
      ),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (i) => AnimatedBuilder(
        animation: _c,
        builder: (_, __) {
          final t = ((_c.value * 3) - i).clamp(0.0, 1.0);
          final y = math.sin(t * math.pi) * 5;
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 2.5),
            child: Transform.translate(
              offset: Offset(0, -y),
              child: Container(
                width: 7, height: 7,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: BC.cyan.withValues(alpha: 0.4 + t * 0.6),
                  boxShadow: [BoxShadow(
                    color: BC.cyan.withValues(alpha: t * 0.7), blurRadius: 4,
                  )],
                ),
              ),
            ),
          );
        },
      )),
    ),
  );
}

// ═══════════════════════════════════════════════════════════
// MOOD SYSTEM — matches web BATMAN OS 4 moods
// ═══════════════════════════════════════════════════════════

enum AppMood { normal, emergency, meditation, stealth }

extension AppMoodX on AppMood {
  String get label {
    switch (this) {
      case AppMood.normal:     return 'NORMAL';
      case AppMood.emergency:  return 'EMERGENCY';
      case AppMood.meditation: return 'MEDITATION';
      case AppMood.stealth:    return 'STEALTH';
    }
  }

  String get emoji {
    switch (this) {
      case AppMood.normal:     return '🦇';
      case AppMood.emergency:  return '🚨';
      case AppMood.meditation: return '🔮';
      case AppMood.stealth:    return '🌿';
    }
  }

  Color get accent {
    switch (this) {
      case AppMood.normal:     return const Color(0xFFFFBE00);
      case AppMood.emergency:  return const Color(0xFFFF3355);
      case AppMood.meditation: return const Color(0xFFA855F7);
      case AppMood.stealth:    return const Color(0xFF48A999);
    }
  }

  Color get accentDim {
    switch (this) {
      case AppMood.normal:     return const Color(0x22FFBE00);
      case AppMood.emergency:  return const Color(0x22FF3355);
      case AppMood.meditation: return const Color(0x22A855F7);
      case AppMood.stealth:    return const Color(0x2248A999);
    }
  }

  Color get bgColor {
    switch (this) {
      case AppMood.normal:     return const Color(0xFF020509);
      case AppMood.emergency:  return const Color(0xFF0A0002);
      case AppMood.meditation: return const Color(0xFF030208);
      case AppMood.stealth:    return const Color(0xFF010404);
    }
  }
}

// ── Mood persistence provider ───────────────────────────────
const _kMoodKey = 'app_mood';

class MoodNotifier extends StateNotifier<AppMood> {
  MoodNotifier() : super(AppMood.normal) { _load(); }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final idx = prefs.getInt(_kMoodKey) ?? 0;
    state = AppMood.values[idx.clamp(0, AppMood.values.length - 1)];
  }

  Future<void> set(AppMood mood) async {
    state = mood;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_kMoodKey, mood.index);
  }
}

final moodProvider = StateNotifierProvider<MoodNotifier, AppMood>(
  (_) => MoodNotifier(),
);

// ── Notification unread badge count ────────────────────────
final notifBadgeProvider = StateProvider<int>((_) => 0);
