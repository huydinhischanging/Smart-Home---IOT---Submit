import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../core/bc.dart';
import '../core/cfg_provider.dart';
import '../core/auth_provider.dart';
import '../widgets/common_widgets.dart';

class HealthScreen extends ConsumerStatefulWidget {
  const HealthScreen({super.key});
  @override
  ConsumerState<HealthScreen> createState() => _HealthState();
}

class _HealthState extends ConsumerState<HealthScreen> {
  List<Map<String, dynamic>> _records = [];
  Map<String, dynamic>? _summary;
  bool _loading = true;
  String? _err;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _err = null; });
    final base  = ref.read(cfgProvider);
    final auth  = ref.read(authProvider);

    if (!auth.isLoggedIn) {
      setState(() { _loading = false; _err = 'Login required to view health data.'; });
      return;
    }

    try {
      final r = await http.get(
        Uri.parse('$base/api/patient/hr-records?limit=100'),
        headers: {
          'Content-Type': 'application/json',
          ...auth.bearerHeader,
        },
      ).timeout(const Duration(seconds: 12));

      if (r.statusCode == 200) {
        final data = jsonDecode(r.body);
        final raw = data['records'];
        _records = (raw is List ? raw : [])
            .cast<Map<String, dynamic>>()
            .reversed
            .toList();  // oldest first for chart
        _summary = data['summary'] as Map<String, dynamic>?;
        _err = null;
      } else if (r.statusCode == 401) {
        _err = 'Session expired. Please log out and log in again.';
      } else {
        _err = 'Server error (${r.statusCode}).';
      }
    } catch (e) {
      _err = 'Cannot reach server. Is backend running?';
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext ctx) => Scaffold(
    backgroundColor: Colors.transparent,
    body: SafeArea(child: Column(children: [
      // ── header ────────────────────────────
      Container(
        padding: const EdgeInsets.fromLTRB(16, 10, 12, 10),
        decoration: const BoxDecoration(
          color: BC.panel,
          border: Border(bottom: BorderSide(color: BC.border)),
        ),
        child: Row(children: [
          const Text('💗', style: TextStyle(fontSize: 20)),
          const SizedBox(width: 10),
          const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('HEALTH MONITOR', style: TextStyle(
              fontFamily: 'monospace', fontSize: 13,
              color: BC.red, letterSpacing: 3, fontWeight: FontWeight.bold,
            )),
            Text('HEART RATE RECORDS', style: TextStyle(
              fontFamily: 'monospace', fontSize: 7,
              color: BC.txtDim, letterSpacing: 2,
            )),
          ]),
          const Spacer(),
          GestureDetector(
            onTap: _load,
            child: Container(
              padding: const EdgeInsets.all(7),
              decoration: BoxDecoration(
                border: Border.all(color: BC.border),
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Icon(Icons.refresh_rounded, color: BC.txtDim, size: 17),
            ),
          ),
        ]),
      ),

      // ── body ──────────────────────────────
      Expanded(
        child: _loading
          ? const BcLoader()
          : RefreshIndicator(
              color: BC.red, backgroundColor: BC.panel,
              onRefresh: _load,
              child: _err != null
                ? ListView(children: [
                    const SizedBox(height: 20),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 14),
                      child: BcErrBanner(msg: _err!),
                    ),
                  ])
                : _HealthBody(records: _records, summary: _summary),
            ),
      ),
    ])),
  );
}

class _HealthBody extends StatelessWidget {
  final List<Map<String, dynamic>> records;
  final Map<String, dynamic>? summary;
  const _HealthBody({required this.records, required this.summary});

  @override
  Widget build(BuildContext ctx) => ListView(
    padding: const EdgeInsets.fromLTRB(14, 14, 14, 110),
    children: [
      if (summary != null) ...[
        _SummaryCard(summary: summary!),
        const SizedBox(height: 14),
      ],
      if (records.length >= 2) ...[
        _ChartCard(records: records),
        const SizedBox(height: 14),
      ],
      _SeverityBreakdown(summary: summary),
      const SizedBox(height: 14),
      BcSectionHeader(label: 'RECENT READINGS', count: records.length),
      const SizedBox(height: 10),
      if (records.isEmpty)
        const _NoData(),
      ...records.reversed.take(40).map((rec) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: _RecordRow(rec: rec),
      )),
    ],
  );
}

// ── Summary stats card ─────────────────────
class _SummaryCard extends StatelessWidget {
  final Map<String, dynamic> summary;
  const _SummaryCard({required this.summary});

  @override
  Widget build(BuildContext ctx) {
    final avg     = summary['avg_bpm'];
    final min     = summary['min_bpm'];
    final max     = summary['max_bpm'];
    final count   = summary['count'];
    final normal  = summary['normal_rate_percent'];
    final avgStr  = avg is num ? avg.toStringAsFixed(1) : '--';
    final normStr = normal is num ? '${normal.toStringAsFixed(1)}%' : '--';

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: BC.red.withValues(alpha: 0.22)),
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [
            BC.panelHi.withValues(alpha: 0.95),
            BC.panel.withValues(alpha: 0.92),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: BC.red.withValues(alpha: 0.06), blurRadius: 20, spreadRadius: 1,
          ),
        ],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: BC.red.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: BC.red.withValues(alpha: 0.30)),
            ),
            child: const Text('VITALS SUMMARY', style: TextStyle(
              fontSize: 9, letterSpacing: 2,
              color: BC.red, fontWeight: FontWeight.bold,
            )),
          ),
          const Spacer(),
          Text('$count records', style: const TextStyle(
            fontFamily: 'monospace', fontSize: 10, color: BC.txtDim,
          )),
        ]),
        const SizedBox(height: 16),
        // Ring gauge for avg BPM
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          BcRingGauge(
            value: avg is num ? (avg.clamp(0, 200) / 200.0) : 0,
            centerVal: avgStr,
            centerLabel: 'AVG BPM',
            color: bcSeverityColor(
              avg is num && avg > 120
                  ? 'critical'
                  : avg is num && avg > 100
                      ? 'warning'
                      : 'info',
            ),
            size: 130,
          ),
        ]),
        const SizedBox(height: 14),
        Row(children: [
          _VitalChip(label: 'AVG BPM', val: avgStr, color: BC.cyan),
          const SizedBox(width: 10),
          _VitalChip(label: 'MIN', val: '$min', color: BC.green),
          const SizedBox(width: 10),
          _VitalChip(label: 'MAX', val: '$max', color: BC.gold),
          const SizedBox(width: 10),
          _VitalChip(label: 'NORMAL', val: normStr, color: BC.green),
        ]),
      ]),
    );
  }
}

class _VitalChip extends StatelessWidget {
  final String label, val;
  final Color color;
  const _VitalChip({required this.label, required this.val, required this.color});

  @override
  Widget build(BuildContext ctx) => Expanded(child: Container(
    padding: const EdgeInsets.symmetric(vertical: 10),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: color.withValues(alpha: 0.22)),
    ),
    child: Column(children: [
      Text(val, style: TextStyle(
        fontFamily: 'monospace', fontSize: 20, color: color,
        fontWeight: FontWeight.bold,
        shadows: [Shadow(color: color.withValues(alpha: 0.5), blurRadius: 6)],
      )),
      const SizedBox(height: 3),
      Text(label, style: const TextStyle(
        fontFamily: 'monospace', fontSize: 7,
        color: BC.txtDim, letterSpacing: 1.5,
      )),
    ]),
  ));
}

// ── BPM Line Chart ─────────────────────────
class _ChartCard extends StatelessWidget {
  final List<Map<String, dynamic>> records;
  const _ChartCard({required this.records});

  Color _dotColor(String? sev) {
    switch (sev) {
      case 'critical': return BC.red;
      case 'warning':  return BC.gold;
      case 'caution':  return const Color(0xFFFF8844);
      default:         return BC.green;
    }
  }

  @override
  Widget build(BuildContext ctx) {
    // Take last 50 points for chart clarity
    final pts = records.length > 50 ? records.sublist(records.length - 50) : records;

    final spots = pts.asMap().entries.map((e) {
      final bpm = (e.value['bpm'] ?? 0).toDouble();
      return FlSpot(e.key.toDouble(), bpm);
    }).toList();

    final allBpm = pts.map((r) => (r['bpm'] ?? 0).toDouble()).toList();
    final minY = (allBpm.reduce((a, b) => a < b ? a : b) - 10).clamp(30.0, 200.0);
    final maxY = (allBpm.reduce((a, b) => a > b ? a : b) + 10).clamp(30.0, 240.0);

    return Container(
      height: 200,
      padding: const EdgeInsets.fromLTRB(12, 18, 18, 12),
      decoration: BoxDecoration(
        color: BC.panel.withValues(alpha: 0.88),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: BC.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Padding(
          padding: EdgeInsets.only(left: 6, bottom: 10),
          child: Text('BPM TIMELINE', style: TextStyle(
            fontFamily: 'monospace', fontSize: 9,
            color: BC.txtDim, letterSpacing: 2,
          )),
        ),
        Expanded(
          child: LineChart(
            LineChartData(
              minY: minY,
              maxY: maxY,
              gridData: FlGridData(
                show: true,
                getDrawingHorizontalLine: (_) => const FlLine(
                  color: BC.border, strokeWidth: 0.5,
                ),
                getDrawingVerticalLine: (_) => const FlLine(
                  color: Colors.transparent,
                ),
              ),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 36,
                    interval: 20,
                    getTitlesWidget: (v, _) => Text('${v.toInt()}', style: const TextStyle(
                      fontFamily: 'monospace', fontSize: 8, color: BC.txtDim,
                    )),
                  ),
                ),
                bottomTitles: const AxisTitles(
                  sideTitles: SideTitles(showTitles: false),
                ),
                rightTitles: const AxisTitles(
                  sideTitles: SideTitles(showTitles: false),
                ),
                topTitles: const AxisTitles(
                  sideTitles: SideTitles(showTitles: false),
                ),
              ),
              borderData: FlBorderData(show: false),
              lineBarsData: [
                LineChartBarData(
                  spots: spots,
                  isCurved: true,
                  color: BC.red,
                  barWidth: 2,
                  dotData: FlDotData(
                    show: true,
                    getDotPainter: (spot, pct, bar, idx) {
                      final sev = pts[idx]['severity']?.toString();
                      return FlDotCirclePainter(
                        radius: sev == 'normal' ? 2.5 : 4.0,
                        color: _dotColor(sev),
                        strokeWidth: 0,
                      );
                    },
                  ),
                  belowBarData: BarAreaData(
                    show: true,
                    gradient: LinearGradient(
                      begin: Alignment.topCenter, end: Alignment.bottomCenter,
                      colors: [BC.red.withValues(alpha: 0.18), Colors.transparent],
                    ),
                  ),
                ),
                // Reference line at 100 BPM
                if (maxY > 100 && minY < 100)
                  LineChartBarData(
                    spots: [const FlSpot(0, 100), FlSpot((pts.length - 1).toDouble(), 100)],
                    isCurved: false,
                    color: BC.gold.withValues(alpha: 0.35),
                    barWidth: 1,
                    dotData: const FlDotData(show: false),
                    dashArray: [4, 4],
                  ),
              ],
              lineTouchData: LineTouchData(
                touchTooltipData: LineTouchTooltipData(
                  getTooltipItems: (spots) => spots.map((s) {
                    if (s.barIndex != 0) return null;
                    final idx = s.spotIndex;
                    final sev = idx < pts.length
                        ? (pts[idx]['severity']?.toString() ?? '')
                        : '';
                    return LineTooltipItem(
                      '${s.y.toInt()} BPM\n$sev',
                      TextStyle(
                        fontFamily: 'monospace', fontSize: 10, color: _dotColor(sev),
                      ),
                    );
                  }).toList(),
                ),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

// ── Severity breakdown ─────────────────────
class _SeverityBreakdown extends StatelessWidget {
  final Map<String, dynamic>? summary;
  const _SeverityBreakdown({required this.summary});

  @override
  Widget build(BuildContext ctx) {
    final counts = summary?['severity_counts'] as Map<String, dynamic>? ?? {};
    final items = [
      ('NORMAL',   counts['normal']   ?? 0, BC.green),
      ('CAUTION',  counts['caution']  ?? 0, const Color(0xFFFF8844)),
      ('WARNING',  counts['warning']  ?? 0, BC.gold),
      ('CRITICAL', counts['critical'] ?? 0, BC.red),
    ];
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: BC.panel.withValues(alpha: 0.88),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: BC.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('SEVERITY DISTRIBUTION', style: TextStyle(
          fontFamily: 'monospace', fontSize: 9,
          color: BC.txtDim, letterSpacing: 2,
        )),
        const SizedBox(height: 12),
        Row(children: items.map((item) {
          final (label, count, color) = item;
          final total = items.fold<int>(0, (s, i) => s + (i.$2 as int));
          final pct   = total > 0 ? ((count as int) / total * 100).round() : 0;
          return Expanded(child: Column(children: [
            Text('$count', style: TextStyle(
              fontFamily: 'monospace', fontSize: 20, color: color,
              fontWeight: FontWeight.bold,
              shadows: count > 0
                ? [Shadow(color: color.withValues(alpha: 0.5), blurRadius: 6)]
                : null,
            )),
            const SizedBox(height: 3),
            Text('$pct%', style: TextStyle(
              fontFamily: 'monospace', fontSize: 9, color: color.withValues(alpha: 0.7),
            )),
            const SizedBox(height: 3),
            Text(label, style: const TextStyle(
              fontFamily: 'monospace', fontSize: 7,
              color: BC.txtDim, letterSpacing: 1.2,
            )),
          ]));
        }).toList()),
      ]),
    );
  }
}

// ── Single HR record row ───────────────────
class _RecordRow extends StatelessWidget {
  final Map<String, dynamic> rec;
  const _RecordRow({required this.rec});

  Color get _sevColor {
    switch (rec['severity']?.toString()) {
      case 'critical': return BC.red;
      case 'warning':  return BC.gold;
      case 'caution':  return const Color(0xFFFF8844);
      default:         return BC.green;
    }
  }

  String _formatTime(String? raw) {
    if (raw == null) return '--';
    try {
      final dt = DateTime.parse(raw).toLocal();
      return DateFormat('HH:mm  dd/MM').format(dt);
    } catch (_) {
      return raw;
    }
  }

  @override
  Widget build(BuildContext ctx) {
    final color = _sevColor;
    final bpm   = rec['bpm'];
    final sev   = (rec['severity']?.toString() ?? 'normal').toUpperCase();
    final time  = _formatTime(rec['recorded_at']?.toString());
    final mood  = rec['mood']?.toString();
    final risk  = rec['risk']?.toString();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: BC.card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.20)),
      ),
      child: Row(children: [
        Container(
          width: 40, height: 40,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color.withValues(alpha: 0.10),
            border: Border.all(color: color.withValues(alpha: 0.30)),
          ),
          child: Center(child: Text(
            '${bpm ?? '--'}',
            style: TextStyle(
              fontFamily: 'monospace', fontSize: 13,
              color: color, fontWeight: FontWeight.bold,
            ),
          )),
        ),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: color.withValues(alpha: 0.25)),
              ),
              child: Text(sev, style: TextStyle(
                fontFamily: 'monospace', fontSize: 8,
                color: color, letterSpacing: 1,
              )),
            ),
            if (mood != null && mood.isNotEmpty) ...[
              const SizedBox(width: 6),
              Text('· $mood', style: const TextStyle(
                fontFamily: 'monospace', fontSize: 8, color: BC.txtDim,
              )),
            ],
          ]),
          const SizedBox(height: 4),
          Text(time, style: const TextStyle(
            fontFamily: 'monospace', fontSize: 9, color: BC.txtDim,
          )),
          if (risk != null && risk.isNotEmpty && risk != 'null')
            Text('risk: $risk', style: const TextStyle(
              fontFamily: 'monospace', fontSize: 8,
              color: BC.txtDim, height: 1.4,
            )),
        ])),
        Container(
          width: 8, height: 8,
          decoration: BoxDecoration(
            shape: BoxShape.circle, color: color,
            boxShadow: [BoxShadow(color: color.withValues(alpha: 0.6), blurRadius: 4)],
          ),
        ),
      ]),
    );
  }
}

// ── No data placeholder ────────────────────
class _NoData extends StatelessWidget {
  const _NoData();
  @override
  Widget build(BuildContext ctx) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 40),
    child: Center(child: Column(children: [
      const Text('💗', style: TextStyle(fontSize: 48)),
      const SizedBox(height: 14),
      const Text('NO RECORDS YET', style: TextStyle(
        fontFamily: 'monospace', fontSize: 11,
        color: BC.txtDim, letterSpacing: 3,
      )),
      const SizedBox(height: 6),
      Text('Records appear here once the Coospo HR band\nbegins transmitting to the backend.',
        textAlign: TextAlign.center,
        style: TextStyle(
          fontFamily: 'monospace', fontSize: 9,
          color: BC.txtDim.withValues(alpha: 0.6), height: 1.6,
        ),
      ),
    ])),
  );
}

