import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../core/bc.dart';
import '../core/cfg_provider.dart';
import '../core/auth_provider.dart';
import '../core/api_headers.dart';
import '../widgets/common_widgets.dart';

class RoutineScreen extends ConsumerStatefulWidget {
  const RoutineScreen({super.key});
  @override
  ConsumerState<RoutineScreen> createState() => _RoutineState();
}

class _RoutineState extends ConsumerState<RoutineScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tab;
  List<Map<String, dynamic>> _schedules = [];
  List<Map<String, dynamic>> _automations = [];
  List<Map<String, dynamic>> _devices = [];
  bool _loadingS = true, _loadingA = true;
  String? _errS, _errA;

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 2, vsync: this);
    _loadSchedules();
    _loadAutomations();
    _loadDevices();
  }

  @override
  void dispose() { _tab.dispose(); super.dispose(); }

  String get _base => ref.read(cfgProvider);
  Map<String, String> get _headers =>
      apiJsonHeaders(ref.read(authProvider).bearerHeader);

  Future<void> _loadDevices() async {
    try {
      final r = await http.get(
        Uri.parse('$_base/api/devices'),
        headers: _headers,
      ).timeout(const Duration(seconds: 8));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body);
        if (mounted) setState(() => _devices = (d is List ? d : (d['data'] ?? d['devices'] ?? [])).cast<Map<String, dynamic>>());
      }
    } catch (_) {}
  }

  Future<void> _loadSchedules() async {
    setState(() { _loadingS = true; _errS = null; });
    try {
      final r = await http.get(
        Uri.parse('$_base/api/automation/schedules'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body);
        _schedules = (d['data'] ?? []).cast<Map<String, dynamic>>();
        _errS = null;
      } else {
        _errS = 'Error ${r.statusCode}';
      }
    } catch (_) {
      _errS = 'Cannot reach server.';
    }
    if (mounted) setState(() => _loadingS = false);
  }

  Future<void> _loadAutomations() async {
    setState(() { _loadingA = true; _errA = null; });
    try {
      final r = await http.get(
        Uri.parse('$_base/api/automation/automations'),
        headers: _headers,
      ).timeout(const Duration(seconds: 10));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body);
        _automations = (d['data'] ?? []).cast<Map<String, dynamic>>();
        _errA = null;
      } else {
        _errA = 'Error ${r.statusCode}';
      }
    } catch (_) {
      _errA = 'Cannot reach server.';
    }
    if (mounted) setState(() => _loadingA = false);
  }

  Future<void> _toggleSchedule(Map<String, dynamic> s) async {
    final id     = s['id'];
    final newVal = !(s['is_active'] == true);
    try {
      final r = await http.patch(
        Uri.parse('$_base/api/automation/schedules/$id'),
        headers: _headers,
        body: jsonEncode({'is_active': newVal}),
      ).timeout(const Duration(seconds: 6));
      if (r.statusCode == 200 && mounted) {
        setState(() {
          final i = _schedules.indexWhere((x) => x['id'] == id);
          if (i >= 0) _schedules[i] = {..._schedules[i], 'is_active': newVal};
        });
      }
    } catch (_) {}
  }

  Future<void> _deleteSchedule(Map<String, dynamic> s) async {
    final id = s['id'];
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: BC.panel,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Delete schedule?', style: TextStyle(
          fontFamily: 'monospace', fontSize: 13, color: BC.txt,
        )),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('CANCEL', style: TextStyle(color: BC.txtDim, fontFamily: 'monospace')),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('DELETE', style: TextStyle(color: BC.red, fontFamily: 'monospace')),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      final r = await http.delete(
        Uri.parse('$_base/api/automation/schedules/$id'),
        headers: _headers,
      ).timeout(const Duration(seconds: 6));
      if ((r.statusCode == 200 || r.statusCode == 204) && mounted) {
        setState(() => _schedules.removeWhere((x) => x['id'] == id));
      }
    } catch (_) {}
  }

  Future<void> _toggleAutomation(Map<String, dynamic> a) async {
    final id     = a['id'];
    final newVal = !(a['is_active'] == true);
    try {
      final r = await http.patch(
        Uri.parse('$_base/api/automation/automations/$id'),
        headers: _headers,
        body: jsonEncode({'is_active': newVal}),
      ).timeout(const Duration(seconds: 6));
      if (r.statusCode == 200 && mounted) {
        setState(() {
          final i = _automations.indexWhere((x) => x['id'] == id);
          if (i >= 0) _automations[i] = {..._automations[i], 'is_active': newVal};
        });
      }
    } catch (_) {}
  }

  Future<void> _showAddScheduleSheet() async {
    if (_devices.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('No devices available.', style: TextStyle(fontFamily: 'monospace')),
        backgroundColor: BC.panel,
      ));
      return;
    }
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _AddScheduleSheet(
        devices: _devices,
        base: _base,
        headers: _headers,
        onCreated: () {
          _loadSchedules();
          Navigator.of(ctx).pop();
        },
      ),
    );
  }

  @override
  Widget build(BuildContext ctx) => Scaffold(
    backgroundColor: Colors.transparent,
    body: SafeArea(child: Column(children: [
      // ── Header ──────────────────────────────
      Container(
        margin: const EdgeInsets.fromLTRB(14, 12, 14, 0),
        padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
        decoration: BoxDecoration(
          color: BC.panel.withValues(alpha: 0.88),
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: BC.gold.withValues(alpha: 0.18)),
          boxShadow: [
            BoxShadow(color: Colors.black.withValues(alpha: 0.25), blurRadius: 18, offset: const Offset(0, 8)),
          ],
        ),
        child: Column(children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: BC.goldDim,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: BC.goldBorder),
              ),
              child: const Text('⚡', style: TextStyle(fontSize: 18)),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('ROUTINES', style: TextStyle(
                  fontFamily: 'monospace', fontSize: 15, letterSpacing: 3,
                  color: BC.gold, fontWeight: FontWeight.bold,
                )),
                Text('AUTOMATION & SCHEDULES', style: TextStyle(
                  fontFamily: 'monospace', fontSize: 8,
                  letterSpacing: 1.9, color: BC.txtDim,
                )),
              ]),
            ),
          ]),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: BcPill(label: '${_schedules.length} SCHEDULES', color: BC.cyan)),
            const SizedBox(width: 8),
            Expanded(child: BcPill(label: '${_automations.length} AUTOMATIONS', color: BC.purple)),
          ]),
        ]),
      ),

      // ── Tab bar ─────────────────────────────
      Container(
        margin: const EdgeInsets.fromLTRB(14, 10, 14, 0),
        decoration: BoxDecoration(
          color: BC.elevated,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: BC.border),
        ),
        child: TabBar(
          controller: _tab,
          padding: const EdgeInsets.all(4),
          indicator: BoxDecoration(
            color: BC.goldDim,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: BC.goldBorder),
          ),
          labelColor: BC.gold,
          unselectedLabelColor: BC.txtDim,
          labelStyle: const TextStyle(fontFamily: 'monospace', fontSize: 10, letterSpacing: 1.5, fontWeight: FontWeight.bold),
          unselectedLabelStyle: const TextStyle(fontFamily: 'monospace', fontSize: 10, letterSpacing: 1),
          tabs: const [
            Tab(text: '⏰  SCHEDULES'),
            Tab(text: '⚙️  AUTOMATIONS'),
          ],
        ),
      ),

      // ── Tab views ───────────────────────────
      Expanded(
        child: TabBarView(
          controller: _tab,
          children: [
            _SchedulesTab(
              schedules: _schedules,
              loading: _loadingS,
              err: _errS,
              devices: _devices,
              onRefresh: _loadSchedules,
              onToggle: _toggleSchedule,
              onDelete: _deleteSchedule,
              onAdd: _showAddScheduleSheet,
            ),
            _AutomationsTab(
              automations: _automations,
              loading: _loadingA,
              err: _errA,
              onRefresh: _loadAutomations,
              onToggle: _toggleAutomation,
            ),
          ],
        ),
      ),
    ])),
  );
}

// ── Schedules tab ──────────────────────────
class _SchedulesTab extends StatelessWidget {
  final List<Map<String, dynamic>> schedules, devices;
  final bool loading;
  final String? err;
  final RefreshCallback onRefresh;
  final VoidCallback onAdd;
  final Function(Map<String, dynamic>) onToggle, onDelete;
  const _SchedulesTab({
    required this.schedules, required this.devices,
    required this.loading, required this.err,
    required this.onRefresh, required this.onAdd,
    required this.onToggle, required this.onDelete,
  });

  String _deviceName(dynamic id) {
    final d = devices.firstWhere(
      (x) => x['id']?.toString() == id?.toString(),
      orElse: () => <String, dynamic>{},
    );
    return (d['name'] ?? 'Device #$id').toString();
  }

  @override
  Widget build(BuildContext ctx) {
    if (loading) return const BcLoader();
    return RefreshIndicator(
      color: BC.gold, backgroundColor: BC.panel,
      onRefresh: onRefresh,
      child: Stack(children: [
        if (err != null)
          ListView(padding: const EdgeInsets.all(14), children: [BcErrBanner(msg: err!)])
        else if (schedules.isEmpty)
          ListView(padding: const EdgeInsets.all(14), children: [
            const SizedBox(height: 50),
            const Center(child: Column(children: [
              Text('⏰', style: TextStyle(fontSize: 48)),
              SizedBox(height: 12),
              Text('NO SCHEDULES', style: TextStyle(
                fontFamily: 'monospace', fontSize: 11,
                color: BC.txtDim, letterSpacing: 3,
              )),
              SizedBox(height: 8),
              Text('Tap + to create a timed automation', style: TextStyle(
                fontFamily: 'monospace', fontSize: 9,
                color: BC.txtDim,
              )),
            ])),
          ])
        else
          ListView.builder(
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 100),
            itemCount: schedules.length,
            itemBuilder: (_, i) {
              final s      = schedules[i];
              final active = s['is_active'] == true;
              final devName = _deviceName(s['device_id']);
              final action  = (s['action'] ?? '').toString();
              final cron    = (s['cron_expr'] ?? '').toString();
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: active ? BC.goldDim : BC.card,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: active ? BC.goldBorder : BC.border),
                ),
                child: Row(children: [
                  Container(
                    width: 42, height: 42,
                    decoration: BoxDecoration(
                      color: active ? BC.gold.withValues(alpha: 0.15) : BC.elevated,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: active ? BC.goldBorder : BC.border),
                    ),
                    child: Center(child: Text(
                      action.contains('1') || action.toLowerCase().contains('on') ? '💡' : '🔌',
                      style: const TextStyle(fontSize: 20),
                    )),
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(devName, style: const TextStyle(
                      fontFamily: 'monospace', fontSize: 12,
                      color: BC.txt, fontWeight: FontWeight.bold,
                    )),
                    const SizedBox(height: 4),
                    Text('ACTION: $action', style: const TextStyle(
                      fontFamily: 'monospace', fontSize: 9,
                      color: BC.txtDim, letterSpacing: 1,
                    )),
                    const SizedBox(height: 2),
                    Row(children: [
                      const Icon(Icons.schedule, color: BC.txtDim, size: 10),
                      const SizedBox(width: 4),
                      Text(cron, style: const TextStyle(
                        fontFamily: 'monospace', fontSize: 9,
                        color: BC.cyan,
                      )),
                    ]),
                  ])),
                  Column(children: [
                    GestureDetector(
                      onTap: () => onToggle(s),
                      child: BcToggle(isOn: active, color: BC.gold),
                    ),
                    const SizedBox(height: 8),
                    GestureDetector(
                      onTap: () => onDelete(s),
                      child: Container(
                        padding: const EdgeInsets.all(6),
                        decoration: BoxDecoration(
                          color: BC.red.withValues(alpha: 0.07),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: BC.red.withValues(alpha: 0.25)),
                        ),
                        child: const Icon(Icons.delete_outline, color: BC.red, size: 14),
                      ),
                    ),
                  ]),
                ]),
              );
            },
          ),

        // FAB
        Positioned(
          bottom: 24, right: 14,
          child: GestureDetector(
            onTap: onAdd,
            child: Container(
              width: 56, height: 56,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  begin: Alignment.topLeft, end: Alignment.bottomRight,
                  colors: [BC.gold, Color(0xFFFFD966)],
                ),
                boxShadow: [
                  BoxShadow(color: BC.gold.withValues(alpha: 0.4), blurRadius: 16, offset: const Offset(0, 6)),
                ],
              ),
              child: const Icon(Icons.add, color: BC.bg, size: 26),
            ),
          ),
        ),
      ]),
    );
  }
}

// ── Automations tab ────────────────────────
class _AutomationsTab extends StatelessWidget {
  final List<Map<String, dynamic>> automations;
  final bool loading;
  final String? err;
  final RefreshCallback onRefresh;
  final Function(Map<String, dynamic>) onToggle;
  const _AutomationsTab({
    required this.automations, required this.loading,
    required this.err, required this.onRefresh, required this.onToggle,
  });

  @override
  Widget build(BuildContext ctx) {
    if (loading) return const BcLoader();
    return RefreshIndicator(
      color: BC.purple, backgroundColor: BC.panel,
      onRefresh: onRefresh,
      child: automations.isEmpty
        ? ListView(padding: const EdgeInsets.all(14), children: [
            const SizedBox(height: 50),
            const Center(child: Column(children: [
              Text('⚙️', style: TextStyle(fontSize: 48)),
              SizedBox(height: 12),
              Text('NO AUTOMATIONS', style: TextStyle(
                fontFamily: 'monospace', fontSize: 11,
                color: BC.txtDim, letterSpacing: 3,
              )),
              SizedBox(height: 8),
              Text('Configure automations via the web portal', style: TextStyle(
                fontFamily: 'monospace', fontSize: 9,
                color: BC.txtDim,
              )),
            ])),
          ])
        : ListView.builder(
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 100),
            itemCount: automations.length,
            itemBuilder: (_, i) {
              final a      = automations[i];
              final active = a['is_active'] == true;
              final name   = (a['name'] ?? a['trigger_type'] ?? 'Automation #${a['id']}').toString();
              final trigger = (a['trigger_type'] ?? a['trigger'] ?? '').toString();
              final actions = (a['actions'] ?? a['action'] ?? '').toString();
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: active ? BC.purple.withValues(alpha: 0.06) : BC.card,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: active ? BC.purple.withValues(alpha: 0.40) : BC.border,
                  ),
                ),
                child: Row(children: [
                  Container(
                    width: 42, height: 42,
                    decoration: BoxDecoration(
                      color: active ? BC.purple.withValues(alpha: 0.14) : BC.elevated,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: active ? BC.purple.withValues(alpha: 0.40) : BC.border,
                      ),
                    ),
                    child: const Center(child: Text('🤖', style: TextStyle(fontSize: 20))),
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(name.toUpperCase(), style: const TextStyle(
                      fontFamily: 'monospace', fontSize: 12,
                      color: BC.txt, fontWeight: FontWeight.bold, letterSpacing: 0.5,
                    )),
                    if (trigger.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Row(children: [
                        const Icon(Icons.sensors, color: BC.cyan, size: 10),
                        const SizedBox(width: 4),
                        Expanded(child: Text('TRIGGER: $trigger', style: const TextStyle(
                          fontFamily: 'monospace', fontSize: 9,
                          color: BC.cyan,
                        ))),
                      ]),
                    ],
                    if (actions.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Row(children: [
                        const Icon(Icons.play_arrow, color: BC.green, size: 10),
                        const SizedBox(width: 4),
                        Expanded(child: Text(
                          actions.length > 40 ? '${actions.substring(0, 40)}…' : actions,
                          style: const TextStyle(
                            fontFamily: 'monospace', fontSize: 9, color: BC.txtDim,
                          ),
                        )),
                      ]),
                    ],
                  ])),
                  GestureDetector(
                    onTap: () => onToggle(a),
                    child: BcToggle(isOn: active, color: BC.purple),
                  ),
                ]),
              );
            },
          ),
    );
  }
}

// ── Add Schedule bottom sheet ───────────────
class _AddScheduleSheet extends StatefulWidget {
  final List<Map<String, dynamic>> devices;
  final String base;
  final Map<String, String> headers;
  final VoidCallback onCreated;
  const _AddScheduleSheet({
    required this.devices, required this.base,
    required this.headers, required this.onCreated,
  });
  @override
  State<_AddScheduleSheet> createState() => _AddScheduleSheetState();
}

class _AddScheduleSheetState extends State<_AddScheduleSheet> {
  Map<String, dynamic>? _selectedDev;
  String _action = '1';
  final _cronCtrl = TextEditingController(text: '0 7 * * *');
  bool _busy = false;
  String? _err;

  static const _actions = [
    ('1', '💡 TURN ON'),
    ('0', '🔌 TURN OFF'),
  ];

  static const _cronPresets = [
    ('0 7 * * *',  '7:00 AM daily'),
    ('0 22 * * *', '10:00 PM daily'),
    ('0 7 * * 1-5','7:00 AM weekdays'),
    ('0 8 * * 0,6','8:00 AM weekend'),
  ];

  Future<void> _create() async {
    if (_selectedDev == null) {
      setState(() => _err = 'Select a device.');
      return;
    }
    setState(() { _busy = true; _err = null; });
    try {
      final r = await http.post(
        Uri.parse('${widget.base}/api/automation/schedules'),
        headers: widget.headers,
        body: jsonEncode({
          'device_id': _selectedDev!['id'],
          'action': _action,
          'cron_expr': _cronCtrl.text.trim(),
        }),
      ).timeout(const Duration(seconds: 10));
      if (r.statusCode == 201) {
        widget.onCreated();
      } else {
        final d = jsonDecode(r.body);
        setState(() => _err = d['message']?.toString() ?? 'Error ${r.statusCode}');
      }
    } catch (e) {
      setState(() => _err = 'Network error.');
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext ctx) => Container(
    margin: const EdgeInsets.fromLTRB(10, 0, 10, 10),
    padding: EdgeInsets.only(
      left: 20, right: 20, top: 20,
      bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
    ),
    decoration: BoxDecoration(
      color: BC.panel,
      borderRadius: BorderRadius.circular(24),
      border: Border.all(color: BC.border),
    ),
    child: SingleChildScrollView(child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // Handle
        Center(child: Container(
          width: 40, height: 4,
          decoration: BoxDecoration(
            color: BC.border, borderRadius: BorderRadius.circular(2),
          ),
        )),
        const SizedBox(height: 16),
        const Text('NEW SCHEDULE', style: TextStyle(
          fontFamily: 'monospace', fontSize: 13,
          color: BC.gold, letterSpacing: 3, fontWeight: FontWeight.bold,
        )),
        const SizedBox(height: 20),

        // Device selector
        const Text('DEVICE', style: TextStyle(
          fontFamily: 'monospace', fontSize: 9, color: BC.txtDim, letterSpacing: 2,
        )),
        const SizedBox(height: 8),
        Container(
          decoration: BoxDecoration(
            color: BC.elevated,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: BC.border),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<Map<String, dynamic>>(
              value: _selectedDev,
              hint: const Padding(
                padding: EdgeInsets.symmetric(horizontal: 14),
                child: Text('Select device…', style: TextStyle(
                  fontFamily: 'monospace', fontSize: 12, color: BC.txtDim,
                )),
              ),
              dropdownColor: BC.panel,
              isExpanded: true,
              icon: const Icon(Icons.expand_more, color: BC.txtDim),
              padding: const EdgeInsets.symmetric(horizontal: 14),
              items: widget.devices.map((d) => DropdownMenuItem(
                value: d,
                child: Text(
                  (d['name'] ?? '').toString().toUpperCase(),
                  style: const TextStyle(
                    fontFamily: 'monospace', fontSize: 12, color: BC.txt,
                  ),
                ),
              )).toList(),
              onChanged: (d) => setState(() => _selectedDev = d),
            ),
          ),
        ),
        const SizedBox(height: 16),

        // Action
        const Text('ACTION', style: TextStyle(
          fontFamily: 'monospace', fontSize: 9, color: BC.txtDim, letterSpacing: 2,
        )),
        const SizedBox(height: 8),
        Row(children: _actions.map(((String code, String label) rec) {
          final sel = _action == rec.$1;
          return Expanded(child: Padding(
            padding: EdgeInsets.only(right: rec.$1 == '1' ? 8 : 0),
            child: GestureDetector(
              onTap: () => setState(() => _action = rec.$1),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 160),
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: sel ? BC.goldDim : BC.elevated,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: sel ? BC.gold : BC.border),
                ),
                child: Center(child: Text(rec.$2, style: TextStyle(
                  fontFamily: 'monospace', fontSize: 10,
                  color: sel ? BC.gold : BC.txtDim,
                  letterSpacing: 0.5,
                ))),
              ),
            ),
          ));
        }).toList()),
        const SizedBox(height: 16),

        // Cron
        const Text('CRON EXPRESSION', style: TextStyle(
          fontFamily: 'monospace', fontSize: 9, color: BC.txtDim, letterSpacing: 2,
        )),
        const SizedBox(height: 8),
        TextField(
          controller: _cronCtrl,
          style: const TextStyle(fontFamily: 'monospace', fontSize: 13, color: BC.txt),
          decoration: const InputDecoration(
            hintText: '0 7 * * *',
            prefixIcon: Icon(Icons.schedule, color: BC.txtDim, size: 18),
          ),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 10),
        Wrap(spacing: 6, runSpacing: 6, children: _cronPresets.map((p) =>
          GestureDetector(
            onTap: () { _cronCtrl.text = p.$1; setState(() {}); },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: BC.cyanDim,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: BC.cyan.withValues(alpha: 0.25)),
              ),
              child: Text(p.$2, style: const TextStyle(
                fontFamily: 'monospace', fontSize: 8,
                color: BC.cyan, letterSpacing: 0.5,
              )),
            ),
          ),
        ).toList()),

        if (_err != null) ...[
          const SizedBox(height: 12),
          BcErrBanner(msg: _err!),
        ],

        const SizedBox(height: 20),
        SizedBox(
          width: double.infinity, height: 50,
          child: ElevatedButton(
            onPressed: _busy ? null : _create,
            style: ElevatedButton.styleFrom(
              backgroundColor: BC.gold,
              foregroundColor: BC.bg,
              disabledBackgroundColor: BC.goldDim,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              elevation: 0,
            ),
            child: _busy
              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: BC.bg, strokeWidth: 2))
              : const Text('CREATE SCHEDULE', style: TextStyle(
                  fontFamily: 'monospace', fontSize: 11,
                  letterSpacing: 2, fontWeight: FontWeight.bold,
                )),
          ),
        ),
      ],
    )),
  );
}
