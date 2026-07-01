import 'package:flutter/material.dart';
import 'dart:math' as math;
import '../core/bc.dart';

// ── Pill status badge ──────────────────────
class BcPill extends StatelessWidget {
  final String label;
  final Color color;
  const BcPill({super.key, required this.label, required this.color});

  @override
  Widget build(BuildContext ctx) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.35)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color,
              boxShadow: [
                BoxShadow(color: color.withValues(alpha: 0.9), blurRadius: 5)
              ],
            ),
          ),
          const SizedBox(width: 7),
          Text(label,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 9,
                color: color,
                letterSpacing: 1.4,
                fontWeight: FontWeight.w700,
              )),
        ]),
      );
}

// ── Section header with divider ────────────
class BcSectionHeader extends StatelessWidget {
  final String label;
  final int count;
  const BcSectionHeader({super.key, required this.label, required this.count});

  @override
  Widget build(BuildContext ctx) => Row(children: [
        Text(label,
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 10,
              color: BC.txt,
              letterSpacing: 3,
              fontWeight: FontWeight.bold,
            )),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: BC.goldDim,
            border: Border.all(color: BC.goldBorder),
            borderRadius: BorderRadius.circular(3),
          ),
          child: Text('$count',
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 9,
                color: BC.gold,
              )),
        ),
        const SizedBox(width: 10),
        Expanded(child: Container(height: 1, color: BC.border)),
      ]);
}

// ── Stat card (2×2 grid) ───────────────────
class BcStat extends StatelessWidget {
  final String val, label, emoji;
  final Color color;
  const BcStat({
    super.key,
    required this.val,
    required this.label,
    required this.emoji,
    required this.color,
  });

  @override
  Widget build(BuildContext ctx) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          color: BC.panel.withValues(alpha: 0.88),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: color.withValues(alpha: 0.22)),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [color.withValues(alpha: 0.10), Colors.transparent],
          ),
        ),
        child: Row(children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: color.withValues(alpha: 0.20)),
            ),
            child: Center(
                child: Text(emoji, style: const TextStyle(fontSize: 18))),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(val,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 24,
                    color: color,
                    fontWeight: FontWeight.bold,
                    height: 1,
                    shadows: [
                      Shadow(color: color.withValues(alpha: 0.6), blurRadius: 8)
                    ],
                  )),
              Text(label,
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 8,
                    color: BC.txtDim,
                    letterSpacing: 1.8,
                  )),
            ],
          ),
        ]),
      );
}

// ── Mission / hero card ────────────────────
class BcMissionCard extends StatelessWidget {
  final List devices;
  final List rooms;
  const BcMissionCard({super.key, required this.devices, required this.rooms});

  @override
  Widget build(BuildContext context) {
    final active = devices.where((d) => d['is_on'] == true).length;
    final readiness =
        devices.isEmpty ? 0 : ((active / devices.length) * 100).round();
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: BC.border),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            BC.panelHi.withValues(alpha: 0.95),
            BC.panel.withValues(alpha: 0.92),
            BC.card.withValues(alpha: 0.95),
          ],
        ),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withValues(alpha: 0.30),
              blurRadius: 22,
              offset: const Offset(0, 10)),
          BoxShadow(
              color: BC.gold.withValues(alpha: 0.08),
              blurRadius: 24,
              spreadRadius: 1),
        ],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: BC.goldDim,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: BC.goldBorder),
            ),
            child: const Text('LIVE MISSION',
                style: TextStyle(
                  fontSize: 9,
                  letterSpacing: 2,
                  color: BC.gold,
                  fontWeight: FontWeight.bold,
                )),
          ),
          const Spacer(),
          Text('$readiness%',
              style: const TextStyle(
                fontSize: 28,
                color: BC.green,
                fontWeight: FontWeight.bold,
                height: 1,
              )),
        ]),
        const SizedBox(height: 14),
        const Text(
          'Command deck synchronized with home infrastructure.',
          style: TextStyle(
              fontSize: 18,
              color: Colors.white,
              fontWeight: FontWeight.w700,
              height: 1.2),
        ),
        const SizedBox(height: 8),
        Text(
          active > 0
              ? '$active device(s) are active across ${rooms.length} zone(s). Mobile control armed.'
              : 'All systems in standby. Wake devices, inspect zones, and issue Alfred commands.',
          style: const TextStyle(fontSize: 12, color: BC.txt, height: 1.6),
        ),
      ]),
    );
  }
}

// ── Toggle switch ──────────────────────────
class BcToggle extends StatelessWidget {
  final bool isOn;
  final Color color;
  const BcToggle({super.key, required this.isOn, required this.color});

  @override
  Widget build(BuildContext ctx) => AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        width: 50,
        height: 27,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          color: isOn ? color.withValues(alpha: 0.18) : BC.elevated,
          border: Border.all(
              color: isOn ? color.withValues(alpha: 0.7) : BC.border,
              width: 1.5),
          boxShadow: isOn
              ? [
                  BoxShadow(
                      color: color.withValues(alpha: 0.25), blurRadius: 10)
                ]
              : null,
        ),
        child: AnimatedAlign(
          duration: const Duration(milliseconds: 220),
          alignment: isOn ? Alignment.centerRight : Alignment.centerLeft,
          child: Padding(
            padding: const EdgeInsets.all(3),
            child: Container(
              width: 19,
              height: 19,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isOn ? color : BC.txtDim,
                boxShadow: isOn
                    ? [
                        BoxShadow(
                            color: color.withValues(alpha: 0.9), blurRadius: 8)
                      ]
                    : null,
              ),
            ),
          ),
        ),
      );
}

// ── Error banner ───────────────────────────
class BcErrBanner extends StatelessWidget {
  final String msg;
  const BcErrBanner({super.key, required this.msg});

  @override
  Widget build(BuildContext ctx) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: BC.red.withValues(alpha: 0.07),
          borderRadius: BorderRadius.circular(6),
          border: const Border(left: BorderSide(color: BC.red, width: 3)),
        ),
        child: Row(children: [
          const Icon(Icons.warning_amber_rounded, color: BC.red, size: 18),
          const SizedBox(width: 10),
          Expanded(
              child: Text(msg,
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 11,
                    color: BC.txtDim,
                    height: 1.5,
                  ))),
        ]),
      );
}

// ── Empty state ────────────────────────────
class BcEmpty extends StatelessWidget {
  const BcEmpty({super.key});
  @override
  Widget build(BuildContext ctx) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 40),
        child: Center(
            child: Column(children: [
          Text('🦇', style: TextStyle(fontSize: 52)),
          SizedBox(height: 14),
          Text('NO DEVICES FOUND',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                color: BC.txtDim,
                letterSpacing: 3,
              )),
        ])),
      );
}

// ── Spinning loader ────────────────────────
class BcLoader extends StatefulWidget {
  const BcLoader({super.key});
  @override
  State<BcLoader> createState() => _BcLoaderState();
}

class _BcLoaderState extends State<BcLoader>
    with SingleTickerProviderStateMixin {
  late AnimationController _c;
  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: const Duration(seconds: 2))
      ..repeat();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext ctx) => Center(
          child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedBuilder(
            animation: _c,
            builder: (_, __) => Transform.rotate(
              angle: _c.value * 2 * 3.141592,
              child: Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                      color: BC.gold.withValues(alpha: 0.3), width: 1),
                  gradient: const SweepGradient(
                      colors: [Colors.transparent, BC.gold]),
                ),
              ),
            ),
          ),
          const SizedBox(height: 18),
          const Text('INITIALIZING SYSTEMS',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 10,
                color: BC.txtDim,
                letterSpacing: 3,
              )),
        ],
      ));
}

// ── Legend dot ─────────────────────────────
class BcLegendDot extends StatelessWidget {
  final Color color;
  final String label;
  const BcLegendDot({super.key, required this.color, required this.label});

  @override
  Widget build(BuildContext ctx) =>
      Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color,
              boxShadow: [
                BoxShadow(color: color.withValues(alpha: 0.7), blurRadius: 4)
              ],
            )),
        const SizedBox(width: 5),
        Text(label,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 9,
              color: color,
              letterSpacing: 1,
            )),
      ]);
}

// ═══════════════════════════════════════════════════════════
// NEW WIDGETS
// ═══════════════════════════════════════════════════════════

// ── Ring gauge — heart rate / wellness ─────────────────────
class BcRingGauge extends StatefulWidget {
  final double value; // 0‥1
  final String centerVal; // e.g. "72"
  final String centerLabel; // e.g. "BPM"
  final Color color;
  final double size;
  const BcRingGauge({
    super.key,
    required this.value,
    required this.centerVal,
    required this.centerLabel,
    required this.color,
    this.size = 120,
  });
  @override
  State<BcRingGauge> createState() => _BcRingGaugeState();
}

class _BcRingGaugeState extends State<BcRingGauge>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _anim = CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic);
    _ctrl.forward();
  }

  @override
  void didUpdateWidget(BcRingGauge old) {
    super.didUpdateWidget(old);
    if ((old.value - widget.value).abs() > 0.01) {
      _ctrl.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext ctx) {
    return AnimatedBuilder(
      animation: _anim,
      builder: (_, __) => SizedBox(
        width: widget.size,
        height: widget.size,
        child: Stack(children: [
          CustomPaint(
            size: Size(widget.size, widget.size),
            painter: _RingPainter(
              progress: _anim.value * widget.value,
              color: widget.color,
            ),
          ),
          Center(
              child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                widget.centerVal,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: widget.size * 0.22,
                  fontWeight: FontWeight.bold,
                  color: widget.color,
                  shadows: [
                    Shadow(
                        color: widget.color.withValues(alpha: 0.6),
                        blurRadius: 8),
                  ],
                ),
              ),
              Text(
                widget.centerLabel,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: widget.size * 0.08,
                  color: BC.txtDim,
                  letterSpacing: 1.5,
                ),
              ),
            ],
          )),
        ]),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  final double progress;
  final Color color;
  const _RingPainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final r = (size.width / 2) - 10;
    const sw = 8.0;

    // Track
    canvas.drawCircle(
      Offset(cx, cy),
      r,
      Paint()
        ..color = color.withValues(alpha: 0.10)
        ..style = PaintingStyle.stroke
        ..strokeWidth = sw,
    );

    // Arc
    if (progress > 0) {
      canvas.drawArc(
        Rect.fromCircle(center: Offset(cx, cy), radius: r),
        -math.pi / 2,
        2 * math.pi * progress,
        false,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = sw
          ..strokeCap = StrokeCap.round
          ..maskFilter = const MaskFilter.blur(BlurStyle.solid, 2),
      );
      // Glow
      canvas.drawArc(
        Rect.fromCircle(center: Offset(cx, cy), radius: r),
        -math.pi / 2,
        2 * math.pi * progress,
        false,
        Paint()
          ..color = color.withValues(alpha: 0.30)
          ..style = PaintingStyle.stroke
          ..strokeWidth = sw + 6
          ..strokeCap = StrokeCap.round
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
      );
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.progress != progress || old.color != color;
}

// ── Scene shortcut button ───────────────────────────────────
class BcSceneBtn extends StatelessWidget {
  final String emoji, label;
  final Color color;
  final VoidCallback onTap;
  const BcSceneBtn({
    super.key,
    required this.emoji,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext ctx) => GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.07),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: color.withValues(alpha: 0.28)),
            boxShadow: [
              BoxShadow(
                color: color.withValues(alpha: 0.08),
                blurRadius: 12,
                spreadRadius: 1,
              ),
            ],
          ),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(emoji, style: const TextStyle(fontSize: 22)),
            const SizedBox(height: 6),
            Text(label,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 8,
                  color: color,
                  letterSpacing: 1.4,
                  fontWeight: FontWeight.bold,
                )),
          ]),
        ),
      );
}

// ── Severity color helper ───────────────────────────────────
Color bcSeverityColor(String? sev) {
  switch ((sev ?? '').toLowerCase()) {
    case 'critical':
      return BC.red;
    case 'warning':
      return BC.gold;
    case 'caution':
      return const Color(0xFFFF8844);
    default:
      return BC.cyan;
  }
}

// ── Notification tile ───────────────────────────────────────
class BcNotifTile extends StatelessWidget {
  final Map<String, dynamic> alert;
  final VoidCallback? onTap;
  const BcNotifTile({super.key, required this.alert, this.onTap});

  @override
  Widget build(BuildContext ctx) {
    final sev = (alert['level'] ?? alert['severity'] ?? 'info') as String;
    final color = bcSeverityColor(sev);
    final isRead = alert['is_read'] == true || alert['read'] == true;
    final msg = (alert['message'] ?? alert['content'] ?? '').toString();
    final tsRaw = alert['created_at'] ?? alert['timestamp'] ?? '';
    String ts = '';
    try {
      final dt = DateTime.parse(tsRaw.toString()).toLocal();
      ts =
          '${dt.day.toString().padLeft(2, '0')}/${dt.month.toString().padLeft(2, '0')} '
          '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {}

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(
          color: isRead ? BC.card : color.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: BC.border),
        ),
        child: Row(children: [
          Container(
            width: 3,
            height: 56,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(999),
            ),
          ),
          const SizedBox(width: 11),
          Expanded(
              child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: color.withValues(alpha: 0.30)),
                  ),
                  child: Text(sev.toUpperCase(),
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 7,
                        color: color,
                        letterSpacing: 1.5,
                        fontWeight: FontWeight.bold,
                      )),
                ),
                if (!isRead) ...[
                  const SizedBox(width: 6),
                  Container(
                    width: 6,
                    height: 6,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: color,
                      boxShadow: [
                        BoxShadow(
                          color: color.withValues(alpha: 0.8),
                          blurRadius: 4,
                        )
                      ],
                    ),
                  ),
                ],
                const Spacer(),
                Text(ts,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 8,
                      color: BC.txtDim,
                      letterSpacing: 0.5,
                    )),
              ]),
              const SizedBox(height: 8),
              Text(msg,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: isRead ? BC.txtDim : BC.txt,
                    height: 1.45,
                  )),
            ],
          )),
        ]),
      ),
    );
  }
}
