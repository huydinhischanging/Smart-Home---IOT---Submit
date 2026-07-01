import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:async';
import '../core/bc.dart';
import '../core/auth_provider.dart';
import '../core/cfg_provider.dart';
import '../core/socket_service.dart';
import '../modules/dashboard/dashboard_provider.dart';
import '../widgets/common_widgets.dart';
import 'settings_screen.dart';
import 'notifications_screen.dart';

class DashScreen extends ConsumerStatefulWidget {
  const DashScreen({super.key});
  @override
  ConsumerState<DashScreen> createState() => _DashState();
}

class _DashState extends ConsumerState<DashScreen>
    with TickerProviderStateMixin {
  late AnimationController _scan;
  StreamSubscription<Map<String, dynamic>>? _deviceSub;
  StreamSubscription<Map<String, dynamic>>? _alertSub;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _scan = AnimationController(
      vsync: this, duration: const Duration(seconds: 5),
    )..repeat();
    Future.microtask(() => ref.read(dashboardProvider.notifier).load());
    _connectSocket();
    // Keep a slow polling fallback (15 s) in case socket drops
    _pollTimer = Timer.periodic(const Duration(seconds: 15), (_) async {
      if (!mounted) return;
      await ref.read(dashboardProvider.notifier).refreshDevices();
    });
  }

  void _connectSocket() {
    final auth    = ref.read(authProvider);
    final baseUrl = ref.read(cfgProvider);
    if (auth.token == null) return;

    final svc = ref.read(socketServiceProvider);
    svc.connect(baseUrl, auth.token!);

    _deviceSub = svc.onDeviceUpdate.listen((data) {
      if (!mounted) return;
      final code = data['device_code'] as String?;
      if (code == null) return;
      ref.read(dashboardProvider.notifier).applyDeviceUpdate(data);
    });

    _alertSub = svc.onNewAlert.listen((data) {
      if (!mounted) return;
      final msg   = data['message'] as String? ?? 'New alert';
      final level = (data['level'] as String? ?? 'warning').toUpperCase();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('[$level] $msg',
              style: const TextStyle(fontFamily: 'monospace')),
          backgroundColor: level == 'CRITICAL' ? Colors.red.shade900 : BC.panel,
          duration: const Duration(seconds: 5),
        ),
      );
    });
  }

  @override
  void dispose() {
    _deviceSub?.cancel();
    _alertSub?.cancel();
    _pollTimer?.cancel();
    _scan.dispose();
    super.dispose();
  }

  Future<void> _toggle(dynamic dev) async {
    final was = dev['is_on'] == true;
    await ref
        .read(dashboardProvider.notifier)
        .setDevicePower(Map<String, dynamic>.from(dev), !was);
  }

  @override
  Widget build(BuildContext ctx) {
    final dashboard = ref.watch(dashboardProvider);
    final h = MediaQuery.of(ctx).size.height;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(children: [
        // scanline
        AnimatedBuilder(
          animation: _scan,
          builder: (_, __) => Positioned(
            top: _scan.value * h - 2, left: 0, right: 0,
            child: Container(
              height: 2,
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [
                  Colors.transparent,
                  BC.gold.withValues(alpha: 0.08),
                  Colors.transparent,
                ]),
              ),
            ),
          ),
        ),
        SafeArea(child: Column(children: [
          _TopBar(
            devices: dashboard.devices,
            onRefresh: () => ref.read(dashboardProvider.notifier).load(),
          ),
          Expanded(
            child: dashboard.loading
              ? const BcLoader()
              : RefreshIndicator(
                  color: BC.gold, backgroundColor: BC.panel,
                  onRefresh: () => ref.read(dashboardProvider.notifier).load(),
                  child: _Body(
                    devices: dashboard.devices,
                    rooms: dashboard.rooms,
                    err: dashboard.error,
                    onToggle: _toggle,
                  ),
                ),
          ),
        ])),
      ]),
    );
  }
}

// ── Top bar ───────────────────────────────
class _TopBar extends ConsumerWidget {
  final List devices;
  final VoidCallback onRefresh;
  const _TopBar({required this.devices, required this.onRefresh});

  @override
  Widget build(BuildContext ctx, WidgetRef ref) {
    final badge = ref.watch(notifBadgeProvider);
    final on = devices.where((d) => d['is_on'] == true).length;
    return Container(
      margin: const EdgeInsets.fromLTRB(14, 12, 14, 0),
      padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
      decoration: BoxDecoration(
        color: BC.panel.withValues(alpha: 0.88),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: BC.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.25),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
          BoxShadow(
            color: BC.gold.withValues(alpha: 0.05),
            blurRadius: 16,
            spreadRadius: 1,
          ),
        ],
      ),
      child: Column(children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: BC.goldDim,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: BC.gold.withValues(alpha: 0.4)),
            ),
                child: const Text('🤵', style: TextStyle(fontSize: 18)),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('ALFRED SMART HOME', style: TextStyle(
                fontFamily: 'monospace', fontSize: 15, letterSpacing: 3.4,
                color: BC.gold, fontWeight: FontWeight.bold,
              )),
              SizedBox(height: 3),
              Text('ELDER CARE SYSTEM', style: TextStyle(
                fontFamily: 'monospace', fontSize: 8,
                letterSpacing: 1.9, color: BC.txtDim,
              )),
            ]),
          ),
          GestureDetector(
            onTap: onRefresh,
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: BC.elevated,
                border: Border.all(color: BC.border),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.refresh_rounded, color: BC.txt, size: 18),
            ),
          ),
          const SizedBox(width: 6),
          // notification bell
          GestureDetector(
            onTap: () => Navigator.of(ctx).push(
              MaterialPageRoute(builder: (_) => const NotificationsScreen()),
            ),
            child: Stack(alignment: Alignment.topRight, children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: BC.elevated,
                  border: Border.all(
                    color: badge > 0
                        ? BC.red.withValues(alpha: 0.45)
                        : BC.border,
                  ),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  Icons.notifications_outlined,
                  color: badge > 0 ? BC.red : BC.txtDim,
                  size: 18,
                ),
              ),
              if (badge > 0)
                Positioned(
                  top: 4, right: 4,
                  child: Container(
                    padding: const EdgeInsets.all(3),
                    decoration: BoxDecoration(
                      color: BC.red,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(color: BC.red.withValues(alpha: 0.6), blurRadius: 4),
                      ],
                    ),
                    child: Text(
                      badge > 9 ? '9+' : '$badge',
                      style: const TextStyle(
                        fontFamily: 'monospace', fontSize: 6,
                        color: Colors.white, fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
            ]),
          ),
          const SizedBox(width: 6),
          GestureDetector(
            onTap: () => Navigator.of(ctx).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: BC.elevated,
                border: Border.all(color: BC.border),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.settings_outlined, color: BC.txtDim, size: 18),
            ),
          ),
        ]),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: BcPill(label: '$on ONLINE',          color: BC.green)),
          const SizedBox(width: 8),
          Expanded(child: BcPill(label: '${devices.length} REGISTERED', color: BC.cyan)),
        ]),
      ]),
    );
  }
}

// ── Body ──────────────────────────────────
class _Body extends StatelessWidget {
  final List devices, rooms;
  final String? err;
  final Function(dynamic) onToggle;
  const _Body({
    required this.devices,
    required this.rooms,
    required this.err,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext ctx) => ListView(
    padding: const EdgeInsets.fromLTRB(14, 16, 14, 110),
    children: [
      if (err != null) ...[BcErrBanner(msg: err!), const SizedBox(height: 12)],
      BcMissionCard(devices: devices, rooms: rooms),
      const SizedBox(height: 14),
      _StatsRow(devices: devices, rooms: rooms),
      const SizedBox(height: 18),
      if (rooms.isNotEmpty) ...[
        BcSectionHeader(label: 'TACTICAL ZONES', count: rooms.length),
        const SizedBox(height: 10),
        _RoomsGrid(rooms: rooms, devices: devices),
        const SizedBox(height: 18),
      ],
      BcSectionHeader(label: 'EQUIPMENT REGISTRY', count: devices.length),
      const SizedBox(height: 10),
      if (devices.isEmpty && err == null) const BcEmpty(),
      ...devices.map((d) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: _DevCard(dev: d, onToggle: () => onToggle(d)),
      )),
      const SizedBox(height: 20),
    ],
  );
}

// ── Stats 2×2 grid ────────────────────────
class _StatsRow extends StatelessWidget {
  final List devices, rooms;
  const _StatsRow({required this.devices, required this.rooms});
  @override
  Widget build(BuildContext ctx) {
    final on      = devices.where((d) => d['is_on'] == true).length;
    final standby = devices.length - on;
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      childAspectRatio: 1.55,
      children: [
        BcStat(val: '${devices.length}', label: 'DEVICES',  emoji: '📟', color: BC.cyan),
        BcStat(val: '$on',               label: 'ACTIVE',   emoji: '⚡', color: BC.green),
        BcStat(val: '$standby',          label: 'STANDBY',  emoji: '🛡️', color: BC.txt),
        BcStat(val: '${rooms.length}',   label: 'ZONES',    emoji: '🏠', color: BC.gold),
      ],
    );
  }
}

// ── Rooms grid ─────────────────────────────
class _RoomsGrid extends StatelessWidget {
  final List rooms, devices;
  const _RoomsGrid({required this.rooms, required this.devices});

  @override
  Widget build(BuildContext ctx) => GridView.builder(
    shrinkWrap: true,
    physics: const NeverScrollableScrollPhysics(),
    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
      crossAxisCount: 2,
      mainAxisSpacing: 8, crossAxisSpacing: 8,
      mainAxisExtent: 80,
    ),
    itemCount: rooms.length,
    itemBuilder: (_, i) {
      final r       = rooms[i];
      final rid     = r['id']?.toString();
      final rd      = devices.where((d) => d['room_id']?.toString() == rid).toList();
      final ac      = rd.where((d) => d['is_on'] == true).length;
      final hasActive = ac > 0;
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: BC.card,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: hasActive ? BC.goldBorder : BC.border),
          gradient: hasActive
            ? LinearGradient(
                begin: Alignment.topLeft, end: Alignment.bottomRight,
                colors: [BC.gold.withValues(alpha: 0.05), Colors.transparent],
              )
            : null,
        ),
        child: Row(children: [
          const Text('🏠', style: TextStyle(fontSize: 22)),
          const SizedBox(width: 10),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(r['name'] ?? '', style: const TextStyle(
                fontFamily: 'monospace', fontSize: 11,
                color: BC.gold, fontWeight: FontWeight.bold, letterSpacing: 0.5,
              ), maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 3),
              Text('${rd.length} DEV · $ac ON', style: const TextStyle(
                fontFamily: 'monospace', fontSize: 9,
                color: BC.txtDim, letterSpacing: 1,
              )),
            ],
          )),
          Container(
            width: 8, height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: hasActive ? BC.green : BC.txtDim,
              boxShadow: hasActive
                ? [BoxShadow(color: BC.green.withValues(alpha: 0.8), blurRadius: 6)]
                : null,
            ),
          ),
        ]),
      );
    },
  );
}

// ── Device card ────────────────────────────
class _DevCard extends StatelessWidget {
  final dynamic dev;
  final VoidCallback onToggle;
  const _DevCard({required this.dev, required this.onToggle});

  static const _icons = {
    'light': '💡', 'lamp': '💡', 'den': '💡',
    'fan': '🌀', 'quat': '🌀',
    'ac': '❄️', 'air': '❄️', 'mayl': '❄️', 'may lanh': '❄️',
    'camera': '📷', 'cam': '📷',
    'door': '🚪', 'cua': '🚪',
    'tv': '📺', 'temp': '🌡️',
  };

  String _normalize(String value) {
    return value
        .toLowerCase()
        .replaceAll('đ', 'd')
        .replaceAll('ð', 'd')
        .replaceAll('máy lạnh', 'may lanh')
        .replaceAll('máy láº¡nh', 'may lanh')
        .replaceAll('quạt', 'quat')
        .replaceAll('quáº¡t', 'quat')
        .replaceAll('cửa', 'cua')
        .replaceAll('cá»­a', 'cua')
        .replaceAll('đèn', 'den')
        .replaceAll('⚙ï¸', '⚙️')
        .replaceAll('â„ï¸', '❄️')
        .replaceAll('🌡ï¸', '🌡️');
  }

  String get _emoji {
    final stored = _normalize((dev['icon'] ?? '').toString());
    if (stored.isNotEmpty && stored != '⚙️') return stored;
    final n = _normalize((dev['name'] ?? '').toString());
    for (final k in _icons.keys) { if (n.contains(k)) return _icons[k]!; }
    final t = _normalize((dev['type'] ?? '').toString());
    for (final k in _icons.keys) { if (t.contains(k)) return _icons[k]!; }
    return '🔌';
  }

  Color get _color {
    switch (_emoji) {
      case '💡': return BC.gold;
      case '🌀': return BC.cyan;
      case '❄️': return const Color(0xFF40E0FF);
      case '📷': return BC.red;
      case '📺': return BC.purple;
      case '🌡️': return const Color(0xFFFF8844);
      default:   return BC.green;
    }
  }

  @override
  Widget build(BuildContext ctx) {
    final isOn = dev['is_on'] == true;
    final name = (dev['name'] ?? '').toString().toUpperCase();
    final color = isOn ? _color : BC.txtDim;

    return GestureDetector(
      onTap: onToggle,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isOn ? _color.withValues(alpha: 0.05) : BC.card,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: isOn ? _color.withValues(alpha: 0.45) : BC.border,
            width: isOn ? 1.5 : 1,
          ),
          boxShadow: isOn
            ? [BoxShadow(color: _color.withValues(alpha: 0.12), blurRadius: 16, spreadRadius: 1)]
            : null,
        ),
        child: Row(children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: 48, height: 48,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isOn ? _color.withValues(alpha: 0.15) : BC.elevated,
              border: Border.all(
                color: isOn ? _color.withValues(alpha: 0.5) : BC.border,
              ),
              boxShadow: isOn
                ? [BoxShadow(color: _color.withValues(alpha: 0.4), blurRadius: 12)]
                : null,
            ),
                child: Center(child: Text(_emoji, style: const TextStyle(fontSize: 22))),
          ),
          const SizedBox(width: 14),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(name, style: TextStyle(
              fontFamily: 'monospace', fontSize: 12,
              color: isOn ? BC.txt : BC.txtDim,
              fontWeight: FontWeight.bold, letterSpacing: 0.8,
            )),
            const SizedBox(height: 5),
            Row(children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                width: 6, height: 6,
                decoration: BoxDecoration(
                  shape: BoxShape.circle, color: color,
                  boxShadow: isOn
                    ? [BoxShadow(color: color.withValues(alpha: 0.9), blurRadius: 6)]
                    : null,
                ),
              ),
              const SizedBox(width: 6),
              Text(isOn ? 'ONLINE' : 'STANDBY', style: TextStyle(
                fontFamily: 'monospace', fontSize: 9,
                color: color, letterSpacing: 1.5,
              )),
            ]),
          ])),
          BcToggle(isOn: isOn, color: _color),
        ]),
      ),
    );
  }
}


