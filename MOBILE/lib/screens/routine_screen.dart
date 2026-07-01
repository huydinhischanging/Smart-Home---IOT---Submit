import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/bc.dart';
import '../modules/automation/automation_provider.dart';
import '../models/event_model.dart';
import '../modules/automation/local_event_store.dart';
import '../widgets/common_widgets.dart';

class RoutineScreen extends ConsumerStatefulWidget {
  const RoutineScreen({super.key});
  @override
  ConsumerState<RoutineScreen> createState() => _RoutineState();
}


class _RoutineState extends ConsumerState<RoutineScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tab;
  List<EventModel> _localEvents = [];
  bool _loadingLocal = true;

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 2, vsync: this);
    Future.microtask(() async {
      ref.read(automationProvider.notifier).loadAll();
      await _loadLocalEvents();
    });
  }

  Future<void> _loadLocalEvents() async {
    final events = await LocalEventStore.loadEvents();
    setState(() {
      _localEvents = events;
      _loadingLocal = false;
    });
  }

  Future<void> _addEventSheet() async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        final navigator = Navigator.of(ctx);
        return _AddEventSheet(
          onCreate: (event) async {
            if (event.type == EventType.medicine) {
              final error = await ref.read(automationProvider.notifier).createReminder(
                name: event.title,
                dose: event.dose ?? '',
                time: event.time,
                days: event.days,
              );
              if (error == null) navigator.pop();
              return error;
            } else {
              await LocalEventStore.addEvent(event);
              await _loadLocalEvents();
              navigator.pop();
              return null;
            }
          },
        );
      },
    );
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext ctx) {
    final automation = ref.watch(automationProvider);
    final allEvents = [
      ...automation.reminders.map((r) => EventModel.fromJson({...r, 'type': 'medicine'})),
      ..._localEvents
    ];
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        child: Column(children: [
          // Header
          Container(
            margin: const EdgeInsets.fromLTRB(14, 12, 14, 0),
            padding: const EdgeInsets.fromLTRB(16, 14, 14, 0),
            decoration: BoxDecoration(
              color: BC.panel.withValues(alpha: 0.88),
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: BC.gold.withValues(alpha: 0.18)),
              boxShadow: [
                BoxShadow(
                    color: Colors.black.withValues(alpha: 0.25),
                    blurRadius: 18,
                    offset: const Offset(0, 8)),
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
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('ROUTINES',
                            style: TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 15,
                              letterSpacing: 3,
                              color: BC.gold,
                              fontWeight: FontWeight.bold,
                            )),
                        Text('SCHEDULE & REMINDERS',
                            style: TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 8,
                              letterSpacing: 1.9,
                              color: BC.txtDim,
                            )),
                      ]),
                ),
              ]),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                    child: BcPill(
                        label: '${allEvents.where((e) => e.type == EventType.medicine).length} MEDICINES',
                        color: BC.green)),
                const SizedBox(width: 8),
                Expanded(
                    child: BcPill(
                        label: '${allEvents.where((e) => e.type != EventType.medicine).length} OTHER EVENTS',
                        color: BC.cyan)),
              ]),
              const SizedBox(height: 10),
              // Tab bar
              TabBar(
                controller: _tab,
                indicatorColor: BC.green,
                indicatorSize: TabBarIndicatorSize.label,
                dividerColor: Colors.transparent,
                labelColor: BC.green,
                unselectedLabelColor: BC.txtDim,
                labelStyle: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 10,
                  letterSpacing: 2,
                  fontWeight: FontWeight.bold,
                ),
                unselectedLabelStyle: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 10,
                  letterSpacing: 2,
                ),
                tabs: const [
                  Tab(text: 'LIST'),
                  Tab(text: 'CALENDAR'),
                ],
              ),
            ]),
          ),
          // Tab views
          Expanded(
            child: TabBarView(
              controller: _tab,
              children: [
                _EventListTab(
                  events: allEvents,
                  loading: automation.loadingReminders || _loadingLocal,
                  onAdd: _addEventSheet,
                  onRefresh: () async {
                    await ref.read(automationProvider.notifier).loadReminders();
                    await _loadLocalEvents();
                  },
                ),
                _CalendarTab(events: allEvents),
              ],
            ),
          ),
        ]),
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════
// LIST TAB (all event types)
// ══════════════════════════════════════════════════════════════
class _EventListTab extends StatelessWidget {
  final List<EventModel> events;
  final bool loading;
  final VoidCallback onAdd;
  final RefreshCallback onRefresh;

  const _EventListTab({
    required this.events,
    required this.loading,
    required this.onAdd,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    if (loading) return const BcLoader();
    return RefreshIndicator(
      color: BC.green,
      backgroundColor: BC.panel,
      onRefresh: onRefresh,
      child: Stack(children: [
        if (events.isEmpty)
          ListView(padding: const EdgeInsets.all(14), children: const [
            SizedBox(height: 50),
            Center(
                child: Column(children: [
              Text('📅', style: TextStyle(fontSize: 48)),
              SizedBox(height: 12),
              Text('NO EVENTS',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 11,
                    color: BC.txtDim,
                    letterSpacing: 3,
                  )),
              SizedBox(height: 8),
              Text('Tap + to add an event',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 9,
                    color: BC.txtDim,
                  )),
            ])),
          ])
        else
          ListView.builder(
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 100),
            itemCount: events.length,
            itemBuilder: (_, i) {
              final e = events[i];
              final icon = _iconForType(e.type);
              final color = _colorForType(e.type);
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: e.type == EventType.medicine && e.takenToday
                      ? BC.green.withValues(alpha: 0.06)
                      : BC.card,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                      color: e.type == EventType.medicine && e.takenToday
                          ? BC.green.withValues(alpha: 0.40)
                          : color.withOpacity(0.3)),
                ),
                child: Row(children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.13),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: color.withOpacity(0.4)),
                    ),
                    child: Center(child: Text(icon, style: const TextStyle(fontSize: 20))),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                        Text(e.title.toUpperCase(),
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 12,
                              color: BC.txt,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.5,
                            )),
                        if (e.type == EventType.medicine && e.dose != null) ...[
                          const SizedBox(height: 4),
                          Row(children: [
                            const Icon(Icons.medication_outlined, color: BC.txtDim, size: 10),
                            const SizedBox(width: 4),
                            Text(e.dose!, style: const TextStyle(fontFamily: 'monospace', fontSize: 9, color: BC.txtDim)),
                          ]),
                        ],
                        if (e.notes != null && e.notes!.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Row(children: [
                            const Icon(Icons.notes, color: BC.txtDim, size: 10),
                            const SizedBox(width: 4),
                            Flexible(child: Text(e.notes!, style: const TextStyle(fontFamily: 'monospace', fontSize: 9, color: BC.txtDim))),
                          ]),
                        ],
                        const SizedBox(height: 2),
                        Row(children: [
                          const Icon(Icons.schedule, color: BC.cyan, size: 10),
                          const SizedBox(width: 4),
                          Text('${e.time}  ·  ${e.days}', style: const TextStyle(fontFamily: 'monospace', fontSize: 9, color: BC.cyan)),
                        ]),
                      ])),
                  if (e.type == EventType.medicine)
                    Column(children: [
                      GestureDetector(
                        onTap: () {/* TODO: mark taken */},
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: e.takenToday ? BC.green.withValues(alpha: 0.18) : BC.elevated,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: e.takenToday ? BC.green.withValues(alpha: 0.5) : BC.border),
                          ),
                          child: Text(
                            e.takenToday ? 'TAKEN' : 'TAKE',
                            style: TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 9,
                              color: e.takenToday ? BC.green : BC.txtDim,
                              letterSpacing: 1,
                            ),
                          ),
                        ),
                      ),
                    ]),
                ]),
              );
            },
          ),
        // FAB
        Positioned(
          bottom: 24,
          right: 14,
          child: GestureDetector(
            onTap: onAdd,
            child: Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [BC.green, Color(0xFF66FFAA)],
                ),
                boxShadow: [
                  BoxShadow(
                      color: BC.green.withValues(alpha: 0.4),
                      blurRadius: 16,
                      offset: const Offset(0, 6)),
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

String _iconForType(EventType t) {
  switch (t) {
    case EventType.medicine: return '💊';
    case EventType.activity: return '🏃';
    case EventType.appointment: return '📋';
    case EventType.note: return '📝';
  }
}

Color _colorForType(EventType t) {
  switch (t) {
    case EventType.medicine: return BC.cyan;
    case EventType.activity: return Colors.purple;
    case EventType.appointment: return Colors.green;
    case EventType.note: return Colors.pink;
  }
}

// ══════════════════════════════════════════════════════════════
// ADD EVENT bottom sheet (multi-type)
// ══════════════════════════════════════════════════════════════
class _AddEventSheet extends StatefulWidget {
  final Future<String?> Function(EventModel event) onCreate;
  const _AddEventSheet({required this.onCreate});
  @override
  State<_AddEventSheet> createState() => _AddEventSheetState();
}

class _AddEventSheetState extends State<_AddEventSheet> {
  EventType _type = EventType.medicine;
  final _titleCtrl = TextEditingController();
  final _doseCtrl = TextEditingController(text: '1 tablet');
  final _timeCtrl = TextEditingController(text: '08:00');
  String _days = 'daily';
  final _notesCtrl = TextEditingController();
  bool _busy = false;
  String? _err;

  static const _dayOptions = [
    'daily',
    'Mon-Fri',
    'Mon,Wed,Fri',
    'Sat,Sun',
  ];

  Future<void> _submit() async {
    final title = _titleCtrl.text.trim();
    if (title.isEmpty) {
      setState(() => _err = 'Title is required.');
      return;
    }
    setState(() {
      _busy = true;
      _err = null;
    });
    final event = EventModel(
      type: _type,
      title: title,
      dose: _type == EventType.medicine ? _doseCtrl.text.trim() : null,
      time: _timeCtrl.text.trim(),
      days: _days,
      notes: _notesCtrl.text.trim(),
    );
    final error = await widget.onCreate(event);
    if (mounted && error != null) setState(() => _err = error);
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext ctx) => Container(
        margin: const EdgeInsets.fromLTRB(10, 0, 10, 10),
        padding: EdgeInsets.only(
          left: 20,
          right: 20,
          top: 20,
          bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
        ),
        decoration: BoxDecoration(
          color: BC.panel,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: BC.border),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  for (final t in EventType.values)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: ChoiceChip(
                        label: Text(_iconForType(t)),
                        selected: _type == t,
                        onSelected: (v) => setState(() => _type = t),
                        selectedColor: _colorForType(t).withOpacity(0.18),
                        labelStyle: const TextStyle(fontSize: 18),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _titleCtrl,
                decoration: InputDecoration(
                  labelText: 'Title',
                  labelStyle: const TextStyle(fontFamily: 'monospace', color: BC.txtDim, fontSize: 11),
                  filled: true,
                  fillColor: BC.elevated,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: BC.border),
                  ),
                ),
              ),
              if (_type == EventType.medicine) ...[
                const SizedBox(height: 10),
                TextField(
                  controller: _doseCtrl,
                  decoration: InputDecoration(
                    labelText: 'Dosage',
                    labelStyle: const TextStyle(fontFamily: 'monospace', color: BC.txtDim, fontSize: 11),
                    filled: true,
                    fillColor: BC.elevated,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: const BorderSide(color: BC.border),
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 10),
              TextField(
                controller: _timeCtrl,
                decoration: InputDecoration(
                  labelText: 'Time (HH:MM)',
                  labelStyle: const TextStyle(fontFamily: 'monospace', color: BC.txtDim, fontSize: 11),
                  filled: true,
                  fillColor: BC.elevated,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: BC.border),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: _days,
                items: _dayOptions.map((d) => DropdownMenuItem(value: d, child: Text(d))).toList(),
                onChanged: (v) => setState(() => _days = v ?? 'daily'),
                decoration: InputDecoration(
                  labelText: 'Recurrence',
                  labelStyle: const TextStyle(fontFamily: 'monospace', color: BC.txtDim, fontSize: 11),
                  filled: true,
                  fillColor: BC.elevated,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: BC.border),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _notesCtrl,
                decoration: InputDecoration(
                  labelText: 'Notes (optional)',
                  labelStyle: const TextStyle(fontFamily: 'monospace', color: BC.txtDim, fontSize: 11),
                  filled: true,
                  fillColor: BC.elevated,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: BC.border),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              if (_err != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(_err!, style: const TextStyle(color: Colors.red, fontSize: 12)),
                ),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  ElevatedButton(
                    onPressed: _busy ? null : _submit,
                    child: _busy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('SAVE'),
                  ),
                  const SizedBox(width: 10),
                  TextButton(
                    onPressed: _busy ? null : () => Navigator.of(ctx).pop(),
                    child: const Text('CANCEL'),
                  ),
                ],
              ),
            ],
          ),
        ),
      );
}

// ══════════════════════════════════════════════════════════════
// CALENDAR TAB — weekly view with conflict detection
// ══════════════════════════════════════════════════════════════
class _CalendarTab extends StatelessWidget {
  final List<EventModel> events;

  const _CalendarTab({required this.events});

  static const _dayLabels = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];

  // Maps recurrence pattern → list of day indices (0=Mon … 6=Sun)
  static List<int> _activeDays(String pattern) {
    switch (pattern) {
      case 'daily':       return [0, 1, 2, 3, 4, 5, 6];
      case 'Mon-Fri':     return [0, 1, 2, 3, 4];
      case 'Mon,Wed,Fri': return [0, 2, 4];
      case 'Sat,Sun':     return [5, 6];
      default:            return [0, 1, 2, 3, 4, 5, 6];
    }
  }

  @override
  Widget build(BuildContext context) {
    if (events.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('📅', style: TextStyle(fontSize: 40)),
            SizedBox(height: 12),
            Text('NO SCHEDULE YET',
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 11,
                  color: BC.txtDim,
                  letterSpacing: 3,
                )),
            SizedBox(height: 6),
            Text('Add events in the LIST tab',
                style: TextStyle(
                    fontFamily: 'monospace', fontSize: 9, color: BC.txtDim)),
          ],
        ),
      );
    }

    // Build day → events map
    final byDay = List.generate(7, (_) => <EventModel>[]);
    for (final e in events) {
      for (final d in _activeDays(e.days)) {
        byDay[d].add(e);
      }
    }

    // Sort each day by time
    for (final list in byDay) {
      list.sort((a, b) => a.time.compareTo(b.time));
    }

    // Detect conflicts: same day + same HH:MM → flag
    final Set<String> conflicts = {};
    for (int d = 0; d < 7; d++) {
      final times = <String, int>{};
      for (final e in byDay[d]) {
        final t = e.time;
        times[t] = (times[t] ?? 0) + 1;
      }
      times.forEach((t, n) {
        if (n > 1) conflicts.add('$d:$t');
      });
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 100),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Conflict warning banner
          if (conflicts.isNotEmpty)
            Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: BC.gold.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
                border:
                    Border.all(color: BC.gold.withValues(alpha: 0.38)),
              ),
              child: Row(children: [
                const Text('⚠', style: TextStyle(fontSize: 14, color: BC.gold)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '${conflicts.length} TIME CONFLICT${conflicts.length > 1 ? "S" : ""} DETECTED — HIGHLIGHTED IN YELLOW',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 9,
                      color: BC.gold,
                      letterSpacing: 1.1,
                    ),
                  ),
                ),
              ]),
            ),

          // Legend row
          const Wrap(
            spacing: 14,
            children: [
              _LegendDot(color: BC.cyan,  label: 'MEDICINE'),
              _LegendDot(color: Colors.purple, label: 'ACTIVITY'),
              _LegendDot(color: Colors.green, label: 'APPOINTMENT'),
              _LegendDot(color: Colors.pink, label: 'NOTE'),
              _LegendDot(color: BC.gold,  label: 'TIME CONFLICT'),
            ],
          ),
          const SizedBox(height: 14),

          // Weekly grid (horizontally scrollable)
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: List.generate(
                7,
                (d) => _DayColumn(
                  dayLabel: _dayLabels[d],
                  dayIndex: d,
                  events: byDay[d],
                  conflicts: conflicts,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Legend dot ─────────────────────────────────────────────────
class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(shape: BoxShape.circle, color: color),
          ),
          const SizedBox(width: 5),
          Text(label,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 8,
                color: BC.txtDim,
                letterSpacing: 1,
              )),
        ],
      );
}

// ── Day column ─────────────────────────────────────────────────
class _DayColumn extends StatelessWidget {
  final String dayLabel;
  final int dayIndex;
  final List<EventModel> events;
  final Set<String> conflicts;

  const _DayColumn({
    required this.dayLabel,
    required this.dayIndex,
    required this.events,
    required this.conflicts,
  });

  bool _isConflict(String time) => conflicts.contains('$dayIndex:$time');

  @override
  Widget build(BuildContext context) {
    final hasDayConflict = events.any((e) => _isConflict(e.time));

    return Container(
      width: 88,
      margin: const EdgeInsets.only(right: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Day header
          Container(
            padding: const EdgeInsets.symmetric(vertical: 9),
            decoration: BoxDecoration(
              color: hasDayConflict
                  ? BC.gold.withValues(alpha: 0.13)
                  : BC.elevated,
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(10)),
              border: Border.all(
                color: hasDayConflict
                    ? BC.gold.withValues(alpha: 0.45)
                    : BC.border,
              ),
            ),
            child: Text(
              dayLabel,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 9,
                letterSpacing: 2,
                fontWeight: FontWeight.bold,
                color: hasDayConflict ? BC.gold : BC.txt,
              ),
            ),
          ),

          // Event slots
          Container(
            constraints: const BoxConstraints(minHeight: 60),
            decoration: BoxDecoration(
              color: BC.card,
              borderRadius:
                  const BorderRadius.vertical(bottom: Radius.circular(10)),
              border: Border(
                left: BorderSide(
                    color: hasDayConflict
                        ? BC.gold.withValues(alpha: 0.30)
                        : BC.border),
                right: BorderSide(
                    color: hasDayConflict
                        ? BC.gold.withValues(alpha: 0.30)
                        : BC.border),
                bottom: BorderSide(
                    color: hasDayConflict
                        ? BC.gold.withValues(alpha: 0.30)
                        : BC.border),
              ),
            ),
            child: events.isEmpty
                ? const SizedBox(
                    height: 60,
                    child: Center(
                      child: Text('—',
                          style: TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 12,
                              color: BC.txtDim)),
                    ),
                  )
                : Padding(
                    padding: const EdgeInsets.all(4),
                    child: Column(
                      children: events
                          .map((e) => _SlotCard(
                                event: e,
                                isConflict: _isConflict(e.time),
                              ))
                          .toList(),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

// ── Slot card inside a day column ─────────────────────────────
class _SlotCard extends StatelessWidget {
  final EventModel event;
  final bool isConflict;

  const _SlotCard({required this.event, required this.isConflict});

  @override
  Widget build(BuildContext context) {
    final time = event.time;
    final name = event.title.toUpperCase();
    final taken = event.type == EventType.medicine && event.takenToday;
    final icon = _iconForType(event.type);
    final color = _colorForType(event.type);

    final cardColor = isConflict
        ? BC.gold.withValues(alpha: 0.10)
        : taken
            ? BC.green.withValues(alpha: 0.08)
            : color.withOpacity(0.10);

    final borderColor = isConflict
        ? BC.gold.withValues(alpha: 0.55)
        : taken
            ? BC.green.withValues(alpha: 0.40)
            : color.withOpacity(0.55);

    final timeColor = isConflict ? BC.gold : color;
    final nameColor = isConflict ? BC.gold.withValues(alpha: 0.85) : BC.txt;

    return Container(
      margin: const EdgeInsets.only(bottom: 4),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 5),
      decoration: BoxDecoration(
        color: cardColor,
        borderRadius: BorderRadius.circular(7),
        border: Border.all(color: borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text(time,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 9,
                  color: timeColor,
                  fontWeight: FontWeight.bold,
                )),
            if (isConflict)
              const Padding(
                padding: EdgeInsets.only(left: 3),
                child: Text('⚠',
                    style: TextStyle(fontSize: 8, color: BC.gold)),
              ),
            Padding(
              padding: const EdgeInsets.only(left: 6),
              child: Text(icon, style: TextStyle(fontSize: 12, color: color)),
            ),
          ]),
          const SizedBox(height: 2),
          Text(
            name.length > 9 ? '${name.substring(0, 8)}…' : name,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 7,
              color: nameColor,
            ),
          ),
          if (event.type == EventType.medicine && taken)
            const Text('✓ TAKEN',
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 6,
                  color: BC.green,
                  fontWeight: FontWeight.bold,
                )),
          if (event.notes != null && event.notes!.isNotEmpty)
            Text(event.notes!, style: const TextStyle(fontSize: 6, color: BC.txtDim)),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════
// ADD REMINDER bottom sheet
// ══════════════════════════════════════════════════════════════
class _AddReminderSheet extends StatefulWidget {
  final Future<String?> Function(String name, String dose, String time,
      String days) onCreate;
  const _AddReminderSheet({required this.onCreate});
  @override
  State<_AddReminderSheet> createState() => _AddReminderSheetState();
}

class _AddReminderSheetState extends State<_AddReminderSheet> {
  final _nameCtrl = TextEditingController();
  final _doseCtrl = TextEditingController(text: '1 tablet');
  final _timeCtrl = TextEditingController(text: '08:00');
  String _days = 'daily';
  bool _busy = false;
  String? _err;

  static const _dayOptions = [
    'daily',
    'Mon-Fri',
    'Mon,Wed,Fri',
    'Sat,Sun',
  ];

  Future<void> _submit() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      setState(() => _err = 'Medicine name is required.');
      return;
    }
    setState(() {
      _busy = true;
      _err = null;
    });
    final error = await widget.onCreate(
      name,
      _doseCtrl.text.trim(),
      _timeCtrl.text.trim(),
      _days,
    );
    if (mounted && error != null) setState(() => _err = error);
    if (mounted) setState(() => _busy = false);
  }

  InputDecoration _inputDec(String label) => InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(
            fontFamily: 'monospace', color: BC.txtDim, fontSize: 11),
        filled: true,
        fillColor: BC.elevated,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: BC.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: BC.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: BC.green, width: 1.5),
        ),
      );

  @override
  Widget build(BuildContext ctx) => Container(
        margin: const EdgeInsets.fromLTRB(10, 0, 10, 10),
        padding: EdgeInsets.only(
          left: 20,
          right: 20,
          top: 20,
          bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
        ),
        decoration: BoxDecoration(
          color: BC.panel,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: BC.border),
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              // Handle
              Center(
                  child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: BC.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              )),
              const SizedBox(height: 16),
              const Text('NEW MEDICINE',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 13,
                    color: BC.green,
                    letterSpacing: 3,
                    fontWeight: FontWeight.bold,
                  )),
              const SizedBox(height: 20),

              TextField(
                controller: _nameCtrl,
                style: const TextStyle(
                    fontFamily: 'monospace', color: BC.txt, fontSize: 13),
                decoration: _inputDec('Medicine Name'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _doseCtrl,
                style: const TextStyle(
                    fontFamily: 'monospace', color: BC.txt, fontSize: 13),
                decoration: _inputDec('Dose (e.g. 1 tablet)'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _timeCtrl,
                style: const TextStyle(
                    fontFamily: 'monospace', color: BC.txt, fontSize: 13),
                decoration: _inputDec('Time (HH:MM)'),
                keyboardType: TextInputType.datetime,
              ),
              const SizedBox(height: 12),

              const Text('FREQUENCY',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 9,
                    color: BC.txtDim,
                    letterSpacing: 2,
                  )),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: _dayOptions
                    .map((opt) => GestureDetector(
                          onTap: () => setState(() => _days = opt),
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              color: _days == opt
                                  ? BC.green.withValues(alpha: 0.15)
                                  : BC.elevated,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: _days == opt
                                    ? BC.green.withValues(alpha: 0.5)
                                    : BC.border,
                              ),
                            ),
                            child: Text(opt,
                                style: TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 10,
                                  color: _days == opt ? BC.green : BC.txtDim,
                                )),
                          ),
                        ))
                    .toList(),
              ),

              if (_err != null) ...[
                const SizedBox(height: 12),
                Text(_err!,
                    style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 10,
                        color: BC.red)),
              ],

              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton(
                  onPressed: _busy ? null : _submit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: BC.green,
                    foregroundColor: BC.bg,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  child: _busy
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                              color: BC.bg, strokeWidth: 2))
                      : const Text('SAVE REMINDER',
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 11,
                            letterSpacing: 2,
                            fontWeight: FontWeight.bold,
                          )),
                ),
              ),
            ],
          ),
        ),
      );
}
