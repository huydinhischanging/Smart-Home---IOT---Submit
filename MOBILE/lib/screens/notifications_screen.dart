import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/bc.dart';
import '../modules/alert/alert_provider.dart';
import '../widgets/common_widgets.dart';

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});
  @override
  ConsumerState<NotificationsScreen> createState() => _NotifState();
}

class _NotifState extends ConsumerState<NotificationsScreen> {
  String _filter = 'ALL'; // ALL | UNREAD | CRITICAL | WARNING

  static const _filters = ['ALL', 'UNREAD', 'CRITICAL', 'WARNING'];

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(alertProvider.notifier).load(limit: 80));
  }

  Future<void> _load() async {
    await ref.read(alertProvider.notifier).load(limit: 80);
  }

  Future<void> _markRead(AlertItem alert) async {
    if (alert.isRead) return;
    await ref.read(alertProvider.notifier).markRead(alert.id);
  }

  Future<void> _markAllRead() async {
    await ref.read(alertProvider.notifier).markAllRead();
  }

  Future<void> _deleteAlert(AlertItem alert) async {
    await ref.read(alertProvider.notifier).deleteAlert(alert.id);
  }

  Future<void> _clearRead() async {
    await ref.read(alertProvider.notifier).clearReadAlerts();
  }

  List<AlertItem> _filtered(List<AlertItem> alerts) {
    switch (_filter) {
      case 'UNREAD':
        return alerts.where((a) => !a.isRead).toList();
      case 'CRITICAL':
        return alerts.where((a) => a.level.toLowerCase() == 'critical').toList();
      case 'WARNING':
        return alerts.where((a) => a.level.toLowerCase() == 'warning').toList();
      default:
        return alerts;
    }
  }

  @override
  Widget build(BuildContext ctx) {
    final alerts = ref.watch(alertProvider);
    ref.listen<AlertState>(alertProvider, (_, next) {
      ref.read(notifBadgeProvider.notifier).state = next.unread;
    });
    final filtered = _filtered(alerts.alerts);

    return Scaffold(
    backgroundColor: Colors.transparent,
    body: SafeArea(child: Column(children: [
      // ── Header ──────────────────────────────
      Container(
        margin: const EdgeInsets.fromLTRB(14, 12, 14, 0),
        padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
        decoration: BoxDecoration(
          color: BC.panel.withValues(alpha: 0.88),
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: BC.red.withValues(alpha: 0.18)),
          boxShadow: [
            BoxShadow(color: Colors.black.withValues(alpha: 0.25), blurRadius: 18, offset: const Offset(0, 8)),
          ],
        ),
        child: Column(children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: BC.red.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: BC.red.withValues(alpha: 0.30)),
              ),
              child: const Text('🚨', style: TextStyle(fontSize: 18)),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('ALERT CENTER', style: TextStyle(
                  fontFamily: 'monospace', fontSize: 15, letterSpacing: 3,
                  color: BC.red, fontWeight: FontWeight.bold,
                )),
                Text('SYSTEM NOTIFICATIONS', style: TextStyle(
                  fontFamily: 'monospace', fontSize: 8,
                  letterSpacing: 1.9, color: BC.txtDim,
                )),
              ]),
            ),
            if (alerts.unread > 0)
              GestureDetector(
                onTap: _markAllRead,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                  decoration: BoxDecoration(
                    color: BC.gold.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: BC.goldBorder),
                  ),
                  child: const Text('MARK ALL', style: TextStyle(
                    fontFamily: 'monospace', fontSize: 8,
                    color: BC.gold, letterSpacing: 1,
                  )),
                ),
              ),
            const SizedBox(width: 6),
            GestureDetector(
              onTap: _clearRead,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                decoration: BoxDecoration(
                  color: BC.red.withValues(alpha: 0.07),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: BC.red.withValues(alpha: 0.25)),
                ),
                child: const Text('CLEAR READ', style: TextStyle(
                  fontFamily: 'monospace', fontSize: 8,
                  color: BC.red, letterSpacing: 1,
                )),
              ),
            ),
            const SizedBox(width: 6),
            GestureDetector(
              onTap: _load,
              child: Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: BC.elevated,
                  border: Border.all(color: BC.border),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.refresh_rounded, color: BC.txtDim, size: 18),
              ),
            ),
          ]),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: BcPill(
              label: '${alerts.unread} UNREAD',
              color: alerts.unread > 0 ? BC.red : BC.txtDim,
            )),
            const SizedBox(width: 8),
            Expanded(child: BcPill(
              label: '${alerts.alerts.length} TOTAL',
              color: BC.cyan,
            )),
          ]),
        ]),
      ),

      // ── Filter chips ─────────────────────────
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 2),
        child: Row(children: _filters.map((f) {
          final active = _filter == f;
          Color fColor;
          switch (f) {
            case 'CRITICAL': fColor = BC.red;  break;
            case 'WARNING':  fColor = BC.gold; break;
            case 'UNREAD':   fColor = BC.cyan; break;
            default:         fColor = BC.txt;
          }
          return GestureDetector(
            onTap: () => setState(() => _filter = f),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              margin: const EdgeInsets.only(right: 8),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: BoxDecoration(
                color: active ? fColor.withValues(alpha: 0.15) : BC.elevated,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: active ? fColor.withValues(alpha: 0.55) : BC.border,
                  width: active ? 1.5 : 1,
                ),
              ),
              child: Text(f, style: TextStyle(
                fontFamily: 'monospace', fontSize: 9,
                color: active ? fColor : BC.txtDim,
                letterSpacing: 1.5, fontWeight: active ? FontWeight.bold : FontWeight.normal,
              )),
            ),
          );
        }).toList()),
      ),

      // ── Body ────────────────────────────────
      Expanded(
        child: alerts.loading
          ? const BcLoader()
          : RefreshIndicator(
              color: BC.red, backgroundColor: BC.panel,
              onRefresh: _load,
              child: alerts.error != null
                ? ListView(children: [
                    const SizedBox(height: 20),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 14),
                      child: BcErrBanner(msg: alerts.error!),
                    ),
                  ])
                : filtered.isEmpty
                  ? ListView(children: const [
                      SizedBox(height: 60),
                      Center(child: Column(children: [
                        Text('✅', style: TextStyle(fontSize: 48)),
                        SizedBox(height: 12),
                        Text('NO ALERTS', style: TextStyle(
                          fontFamily: 'monospace', fontSize: 11,
                          color: BC.txtDim, letterSpacing: 3,
                        )),
                      ])),
                    ])
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(14, 10, 14, 110),
                      itemCount: filtered.length,
                      itemBuilder: (_, i) {
                        final alert = filtered[i];
                        return Dismissible(
                          key: ValueKey(alert.id),
                          direction: DismissDirection.endToStart,
                          background: Container(
                            alignment: Alignment.centerRight,
                            padding: const EdgeInsets.only(right: 20),
                            margin: const EdgeInsets.only(bottom: 8),
                            decoration: BoxDecoration(
                              color: BC.red.withValues(alpha: 0.18),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: const Icon(Icons.delete_outline_rounded,
                                color: BC.red, size: 22),
                          ),
                          onDismissed: (_) => _deleteAlert(alert),
                          child: BcNotifTile(
                            alert: {
                              'id': alert.id,
                              'device_code': alert.deviceCode,
                              'message': alert.message,
                              'level': alert.level,
                              'is_read': alert.isRead,
                              'created_at': alert.createdAt,
                            },
                            onTap: () => _markRead(alert),
                          ),
                        );
                      },
                    ),
            ),
      ),
    ])),
  );
  }
}
