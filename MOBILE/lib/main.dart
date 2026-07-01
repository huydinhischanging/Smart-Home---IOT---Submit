import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/bc.dart';
import 'core/auth_provider.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/map_screen.dart';
import 'screens/alfred_screen.dart';
import 'screens/health_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/routine_screen.dart';

// ──────────────────────────────────────────
// ENTRY POINT
// ──────────────────────────────────────────
Future<void> bootstrapApp() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: BC.bg,
    systemNavigationBarIconBrightness: Brightness.light,
  ));
  runApp(const ProviderScope(child: _App()));
}

void main() {
  bootstrapApp();
}

// ──────────────────────────────────────────
// APP — auth gate + mood-reactive theme
// ──────────────────────────────────────────
class _App extends ConsumerWidget {
  const _App();

  @override
  Widget build(BuildContext ctx, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final mood = ref.watch(moodProvider);

    Widget home;
    if (auth.isLoading) {
      home = const _SplashScreen();
    } else if (auth.isLoggedIn) {
      home = const _Shell();
    } else {
      home = const LoginScreen();
    }

    return MaterialApp(
      title: 'Alfred Smart Home',
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(accent: mood.accent),
      home: home,
      routes: {
        '/settings': (_) => const SettingsScreen(),
        '/notifications': (_) => const NotificationsScreen(),
      },
    );
  }
}

// ──────────────────────────────────────────
// SHELL — 5-tab scaffold
// ──────────────────────────────────────────
class _Shell extends StatefulWidget {
  const _Shell();
  @override
  State<_Shell> createState() => _ShellState();
}

class _ShellState extends State<_Shell> {
  int _i = 0;

  @override
  Widget build(BuildContext ctx) => Scaffold(
        backgroundColor: Colors.transparent,
        extendBody: true,
        body: Stack(children: [
          const Positioned.fill(child: TacticalBackdrop()),
          IndexedStack(
            index: _i,
            children: const [
              DashScreen(),
              RoutineScreen(),
              AlfredScreen(),
              HealthScreen(),
              NotificationsScreen(),
              MapScreen(),
            ],
          ),
        ]),
        bottomNavigationBar: _BottomBar(
          idx: _i,
          onTap: (i) => setState(() => _i = i),
        ),
      );
}

// ──────────────────────────────────────────
// BOTTOM NAV BAR — 5 tabs with notif badge
// ──────────────────────────────────────────
class _BottomBar extends ConsumerWidget {
  final int idx;
  final ValueChanged<int> onTap;
  const _BottomBar({required this.idx, required this.onTap});

  @override
  Widget build(BuildContext ctx, WidgetRef ref) {
    final badge = ref.watch(notifBadgeProvider);
    final mood = ref.watch(moodProvider);
    return Container(
      margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
      child: SafeArea(
        top: false,
        child: Container(
          height: 68,
          decoration: BoxDecoration(
            color: BC.panel.withValues(alpha: 0.92),
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: BC.border),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.35),
                blurRadius: 20,
                offset: const Offset(0, 8),
              ),
              BoxShadow(
                color: mood.accent.withValues(alpha: 0.06),
                blurRadius: 28,
                spreadRadius: 1,
              ),
            ],
          ),
          child: Row(children: [
            _BTab(
                icon: '🏠',
                label: 'CONTROL',
                active: idx == 0,
                onTap: () => onTap(0),
                accent: mood.accent),
            _BTab(
                icon: '⚡',
                label: 'ROUTINES',
                active: idx == 1,
                onTap: () => onTap(1),
                accent: mood.accent),
            _BTab(
                icon: '🤖',
                label: 'ALFRED',
                active: idx == 2,
                onTap: () => onTap(2),
                accent: mood.accent),
            _BTab(
                icon: '💗',
                label: 'HEALTH',
                active: idx == 3,
                onTap: () => onTap(3),
                accent: mood.accent),
            _BTab(
              icon: '⚠️',
              label: 'ALERTS',
              active: idx == 4,
              onTap: () => onTap(4),
              accent: mood.accent,
              badge: badge,
            ),
            _BTab(
              icon: '🗺️',
              label: 'MAP',
              active: idx == 5,
              onTap: () => onTap(5),
              accent: mood.accent,
            ),
          ]),
        ),
      ),
    );
  }
}

class _BTab extends StatelessWidget {
  final String icon, label;
  final bool active;
  final VoidCallback onTap;
  final Color accent;
  final int badge;
  const _BTab({
    required this.icon,
    required this.label,
    required this.active,
    required this.onTap,
    required this.accent,
    this.badge = 0,
  });

  @override
  Widget build(BuildContext ctx) => Expanded(
        child: GestureDetector(
          onTap: onTap,
          behavior: HitTestBehavior.opaque,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
            decoration: BoxDecoration(
              color:
                  active ? accent.withValues(alpha: 0.14) : Colors.transparent,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: active
                    ? accent.withValues(alpha: 0.45)
                    : Colors.transparent,
              ),
            ),
            child: Stack(children: [
              Positioned.fill(
                child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(icon, style: TextStyle(fontSize: active ? 18 : 16)),
                      const SizedBox(height: 2),
                      Text(label,
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 7,
                            letterSpacing: 1.4,
                            color: active ? accent : BC.txtDim,
                            fontWeight:
                                active ? FontWeight.bold : FontWeight.normal,
                          )),
                    ]),
              ),
              if (badge > 0)
                Positioned(
                  top: 4,
                  right: 6,
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                    decoration: BoxDecoration(
                      color: BC.red,
                      borderRadius: BorderRadius.circular(8),
                      boxShadow: [
                        BoxShadow(
                            color: BC.red.withValues(alpha: 0.6), blurRadius: 6)
                      ],
                    ),
                    child: Text(
                      badge > 99 ? '99+' : '$badge',
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 7,
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
            ]),
          ),
        ),
      );
}

// ──────────────────────────────────────────
// SPLASH — shown while auth is loading
// ──────────────────────────────────────────
class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext ctx) => Scaffold(
        backgroundColor: BC.bg,
        body: Stack(children: [
          const Positioned.fill(child: TacticalBackdrop()),
          Center(
              child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('🤵', style: TextStyle(fontSize: 64)),
              const SizedBox(height: 20),
              const Text('ALFRED SMART HOME',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 22,
                    color: BC.gold,
                    letterSpacing: 6,
                    fontWeight: FontWeight.bold,
                  )),
              const SizedBox(height: 6),
              const Text('ELDER CARE SYSTEM',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 9,
                    color: BC.txtDim,
                    letterSpacing: 3,
                  )),
              const SizedBox(height: 40),
              const SizedBox(
                width: 120,
                child: LinearProgressIndicator(
                  backgroundColor: BC.border,
                  color: BC.gold,
                  minHeight: 2,
                ),
              ),
              const SizedBox(height: 12),
              Text('INITIALIZING...',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 8,
                    color: BC.txtDim.withValues(alpha: 0.6),
                    letterSpacing: 2,
                  )),
            ],
          )),
        ]),
      );
}
