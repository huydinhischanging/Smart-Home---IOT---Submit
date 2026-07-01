import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import '../core/bc.dart';
import '../modules/sensor/sensor_provider.dart';
import '../widgets/common_widgets.dart';

class HealthScreen extends ConsumerStatefulWidget {
  const HealthScreen({super.key});
  @override
  ConsumerState<HealthScreen> createState() => _HealthState();
}

class _HealthState extends ConsumerState<HealthScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() async {
      final n = ref.read(sensorProvider.notifier);
      await Future.wait([n.loadHrRecords(), n.loadHrvSummary()]);
    });
  }

  Future<void> _load() async {
    final n = ref.read(sensorProvider.notifier);
    await Future.wait([n.loadHrRecords(), n.loadHrvSummary()]);
  }

  @override
  Widget build(BuildContext ctx) {
    final sensor = ref.watch(sensorProvider);
    final records = sensor.hrRecords
        .map((record) => <String, dynamic>{
              'bpm': record.bpm,
              'severity': record.severity,
              'mood': record.mood,
              'risk': record.risk,
              'recorded_at': record.recordedAt,
            })
        .toList()
        .reversed
        .toList();

    return Scaffold(
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
        child: sensor.loading
          ? const BcLoader()
          : RefreshIndicator(
              color: BC.red, backgroundColor: BC.panel,
              onRefresh: _load,
              child: sensor.error != null
                ? ListView(children: [
                    const SizedBox(height: 20),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 14),
                      child: BcErrBanner(msg: sensor.error!),
                    ),
                  ])
                : _HealthBody(records: records, summary: sensor.summary, hrvSummary: sensor.hrvSummary),
            ),
      ),
    ])),
  );
  }
}

class _HealthBody extends StatelessWidget {
  final List<Map<String, dynamic>> records;
  final Map<String, dynamic>? summary;
  final Map<String, dynamic>? hrvSummary;
  const _HealthBody({required this.records, required this.summary, this.hrvSummary});

  // records is newest-first (reversed in _HealthState)
  Map<String, dynamic>? get _latest => records.isNotEmpty ? records.first : null;

  @override
  Widget build(BuildContext ctx) => ListView(
    padding: const EdgeInsets.fromLTRB(14, 14, 14, 110),
    children: [
      // ── Live BPM hero — most prominent element ──
      _LiveBpmHero(latest: _latest),
      const SizedBox(height: 14),
      // ── Vitals summary — compute from records ──
      if (records.isNotEmpty) ...[
        _SummaryCard(summary: summary, records: records),
        const SizedBox(height: 14),
      ],
      if (records.length >= 2) ...[
        _ChartCard(records: records),
        const SizedBox(height: 14),
      ],
      _SeverityBreakdown(summary: summary),
      const SizedBox(height: 14),
      if (hrvSummary != null) ...[
        _HrvCard(hrv: hrvSummary),
        const SizedBox(height: 14),
      ],
      BcSectionHeader(label: 'RECENT READINGS', count: records.length),
      const SizedBox(height: 10),
      if (records.isEmpty)
        const _NoData(),
      // Show newest first
      ...records.take(40).map((rec) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: _RecordRow(rec: rec),
      )),
    ],
  );
}

// ── Live BPM hero card ─────────────────────
class _LiveBpmHero extends StatefulWidget {
  final Map<String, dynamic>? latest;
  const _LiveBpmHero({required this.latest});
  @override
  State<_LiveBpmHero> createState() => _LiveBpmHeroState();
}

class _LiveBpmHeroState extends State<_LiveBpmHero>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
    _scale = Tween<double>(begin: 0.7, end: 1.0).animate(
      CurvedAnimation(parent: _pulse, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  Color _sevColor(String? sev) {
    switch (sev) {
      case 'critical': return BC.red;
      case 'warning':  return BC.gold;
      case 'caution':  return const Color(0xFFFF8844);
      default:         return BC.green;
    }
  }

  @override
  Widget build(BuildContext ctx) {
    final latest = widget.latest;
    final bpm    = latest != null ? latest['bpm'] : null;
    final sev    = latest?['severity']?.toString();
    final color  = _sevColor(sev);
    final bpmStr = bpm != null ? '$bpm' : '--';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: color.withValues(alpha: 0.35)),
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [
            color.withValues(alpha: 0.08),
            BC.panel.withValues(alpha: 0.95),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.12), blurRadius: 24, spreadRadius: 2,
          ),
        ],
      ),
      child: Row(children: [
        // Big BPM number
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              AnimatedBuilder(
                animation: _scale,
                builder: (_, __) => Transform.scale(
                  scale: _scale.value,
                  child: Container(
                    width: 10, height: 10,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: latest != null ? color : BC.txtDim,
                      boxShadow: latest != null
                        ? [BoxShadow(color: color.withValues(alpha: 0.7), blurRadius: 8)]
                        : null,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                latest != null ? 'LIVE BPM' : 'WAITING...',
                style: TextStyle(
                  fontFamily: 'monospace', fontSize: 9, letterSpacing: 2,
                  color: latest != null ? color : BC.txtDim,
                ),
              ),
            ]),
            const SizedBox(height: 6),
            Text(
              bpmStr,
              style: TextStyle(
                fontFamily: 'monospace', fontSize: 56,
                color: color, fontWeight: FontWeight.bold, height: 1.0,
                shadows: latest != null
                  ? [Shadow(color: color.withValues(alpha: 0.5), blurRadius: 16)]
                  : null,
              ),
            ),
            const SizedBox(height: 2),
            const Text('BEATS PER MINUTE', style: TextStyle(
              fontFamily: 'monospace', fontSize: 8,
              color: BC.txtDim, letterSpacing: 2,
            )),
          ]),
        ),
        // Severity badge + time
        if (latest != null)
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: color.withValues(alpha: 0.35)),
              ),
              child: Text(
                (sev ?? 'normal').toUpperCase(),
                style: TextStyle(
                  fontFamily: 'monospace', fontSize: 9,
                  color: color, letterSpacing: 1,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _formatTime(latest['recorded_at']?.toString() ?? ''),
              style: const TextStyle(
                fontFamily: 'monospace', fontSize: 9, color: BC.txtDim,
              ),
            ),
          ]),
      ]),
    );
  }

  String _formatTime(String raw) {
    try {
      final dt = DateTime.parse(raw).toLocal();
      return DateFormat('HH:mm  dd/MM').format(dt);
    } catch (_) { return raw; }
  }
}

// ── Summary stats card ─────────────────────
class _SummaryCard extends StatelessWidget {
  final Map<String, dynamic>? summary;
  final List<Map<String, dynamic>> records;
  const _SummaryCard({required this.summary, required this.records});

  // Compute stats from actual records (authoritative — handles realtime additions)
  double? get _avg {
    if (records.isEmpty) return null;
    final bpms = records.map((r) => (r['bpm'] as num?)?.toDouble() ?? 0.0).toList();
    return bpms.reduce((a, b) => a + b) / bpms.length;
  }

  int? get _min {
    if (records.isEmpty) return null;
    return records
        .map((r) => (r['bpm'] as num?)?.toInt() ?? 9999)
        .reduce((a, b) => math.min(a, b));
  }

  int? get _max {
    if (records.isEmpty) return null;
    return records
        .map((r) => (r['bpm'] as num?)?.toInt() ?? 0)
        .reduce((a, b) => math.max(a, b));
  }

  double? get _normalRate {
    if (records.isEmpty) return null;
    // Use API value if summary is fresh (count matches), else compute
    final apiRate = summary?['normal_rate_percent'];
    final apiCount = summary?['count'];
    if (apiRate is num && apiCount is num && apiCount == records.length) {
      return apiRate.toDouble();
    }
    final normalCount = records.where((r) => r['severity'] == 'normal').length;
    return normalCount / records.length * 100;
  }

  @override
  Widget build(BuildContext ctx) {
    final count   = records.length;
    final avg     = _avg;
    final minBpm  = _min;
    final maxBpm  = _max;
    final normal  = _normalRate;
    final avgStr  = avg != null ? avg.toStringAsFixed(1) : '--';
    final minStr  = minBpm != null ? '$minBpm' : '--';
    final maxStr  = maxBpm != null ? '$maxBpm' : '--';
    final normStr = normal != null ? '${normal.toStringAsFixed(1)}%' : '--';

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
            value: avg != null ? (avg.clamp(0.0, 200.0) / 200.0) : 0,
            centerVal: avgStr,
            centerLabel: 'AVG BPM',
            color: bcSeverityColor(
              avg != null && avg > 120
                  ? 'critical'
                  : avg != null && avg > 100
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
          _VitalChip(label: 'MIN', val: minStr, color: BC.green),
          const SizedBox(width: 10),
          _VitalChip(label: 'MAX', val: maxStr, color: BC.gold),
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

// ── HRV Analysis card ──────────────────────
class _HrvCard extends StatelessWidget {
  final Map<String, dynamic>? hrv;
  const _HrvCard({required this.hrv});

  @override
  Widget build(BuildContext ctx) {
    if (hrv == null) return const SizedBox.shrink();
    final rmssd = (hrv!['rmssd'] as num?)?.toStringAsFixed(1) ?? '--';
    final sdnn  = (hrv!['sdnn']  as num?)?.toStringAsFixed(1) ?? '--';
    final pnn50 = (hrv!['pnn50'] as num?)?.toStringAsFixed(1) ?? '--';
    final lowPct = (hrv!['low_hrv_rate_pct'] as num?)?.toStringAsFixed(1);
    final risk   = hrv!['risk_distribution'] as Map<String, dynamic>? ?? {};

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: BC.cyan.withValues(alpha: 0.25)),
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [BC.cyan.withValues(alpha: 0.07), BC.panel.withValues(alpha: 0.92)],
        ),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: BC.cyan.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: BC.cyan.withValues(alpha: 0.30)),
            ),
            child: const Text('HRV ANALYSIS', style: TextStyle(
              fontSize: 9, letterSpacing: 2,
              color: BC.cyan, fontWeight: FontWeight.bold,
            )),
          ),
          if (lowPct != null) ...[
            const Spacer(),
            Text('$lowPct% low HRV', style: const TextStyle(
              fontFamily: 'monospace', fontSize: 9, color: BC.txtDim,
            )),
          ],
        ]),
        const SizedBox(height: 14),
        Row(children: [
          _HrvMetric(label: 'RMSSD', val: rmssd, unit: 'ms', color: BC.cyan),
          const SizedBox(width: 10),
          _HrvMetric(label: 'SDNN',  val: sdnn,  unit: 'ms', color: BC.green),
          const SizedBox(width: 10),
          _HrvMetric(label: 'PNN50', val: pnn50, unit: '%',  color: BC.gold),
        ]),
        if (risk.isNotEmpty) ...[
          const SizedBox(height: 14),
          const Text('RISK DISTRIBUTION', style: TextStyle(
            fontFamily: 'monospace', fontSize: 8,
            color: BC.txtDim, letterSpacing: 2,
          )),
          const SizedBox(height: 8),
          Row(children: [
            _HrvRiskBar(label: 'LOW',  count: risk['low']    ?? 0, color: BC.green),
            const SizedBox(width: 6),
            _HrvRiskBar(label: 'MED',  count: risk['medium'] ?? 0, color: BC.gold),
            const SizedBox(width: 6),
            _HrvRiskBar(label: 'HIGH', count: risk['high']   ?? 0, color: BC.red),
          ]),
        ],
      ]),
    );
  }
}

class _HrvMetric extends StatelessWidget {
  final String label, val, unit;
  final Color color;
  const _HrvMetric({required this.label, required this.val, required this.unit, required this.color});

  @override
  Widget build(BuildContext ctx) => Expanded(child: Container(
    padding: const EdgeInsets.symmetric(vertical: 12),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: color.withValues(alpha: 0.22)),
    ),
    child: Column(children: [
      RichText(text: TextSpan(children: [
        TextSpan(text: val, style: TextStyle(
          fontFamily: 'monospace', fontSize: 18, color: color,
          fontWeight: FontWeight.bold,
          shadows: [Shadow(color: color.withValues(alpha: 0.4), blurRadius: 6)],
        )),
        TextSpan(text: ' $unit', style: const TextStyle(
          fontFamily: 'monospace', fontSize: 9, color: BC.txtDim,
        )),
      ])),
      const SizedBox(height: 4),
      Text(label, style: const TextStyle(
        fontFamily: 'monospace', fontSize: 7,
        color: BC.txtDim, letterSpacing: 1.5,
      )),
    ]),
  ));
}

class _HrvRiskBar extends StatelessWidget {
  final String label;
  final dynamic count;
  final Color color;
  const _HrvRiskBar({required this.label, required this.count, required this.color});

  @override
  Widget build(BuildContext ctx) => Expanded(child: Container(
    padding: const EdgeInsets.symmetric(vertical: 8),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: color.withValues(alpha: 0.25)),
    ),
    child: Column(children: [
      Text('$count', style: TextStyle(
        fontFamily: 'monospace', fontSize: 16, color: color,
        fontWeight: FontWeight.bold,
      )),
      const SizedBox(height: 3),
      Text(label, style: const TextStyle(
        fontFamily: 'monospace', fontSize: 7,
        color: BC.txtDim, letterSpacing: 1,
      )),
    ]),
  ));
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

  String _formatTime(String raw) {
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
    final time  = _formatTime(rec['recorded_at']?.toString() ?? '');
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

