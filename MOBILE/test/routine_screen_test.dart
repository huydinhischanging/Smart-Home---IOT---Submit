import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_home_mobile/modules/automation/automation_provider.dart';
import 'package:smart_home_mobile/screens/routine_screen.dart';
import 'package:smart_home_mobile/widgets/common_widgets.dart';

class _FakeAutomationNotifier extends AutomationNotifier {
  _FakeAutomationNotifier(super.ref, {required AutomationState initialState})
      : super() {
    state = initialState;
  }

  int loadAllCalls = 0;
  int loadRemindersCalls = 0;
  final List<int> markedTakenIds = [];
  final List<int> deletedIds = [];
  final List<Map<String, Object?>> createdReminders = [];
  String? nextCreateError;

  @override
  Future<void> loadAll() async => loadAllCalls += 1;

  @override
  Future<void> loadReminders() async => loadRemindersCalls += 1;

  @override
  Future<void> markReminderTaken(int id) async {
    markedTakenIds.add(id);
    state = state.copyWith(
      reminders: state.reminders.map((item) {
        if (item['id'] == id) {
          return {...item, 'taken_today': !(item['taken_today'] == true)};
        }
        return item;
      }).toList(),
    );
  }

  @override
  Future<void> deleteReminder(int id) async {
    deletedIds.add(id);
    state = state.copyWith(
      reminders: state.reminders.where((item) => item['id'] != id).toList(),
    );
  }

  @override
  Future<String?> createReminder({
    required String name,
    required String dose,
    required String time,
    required String days,
  }) async {
    createdReminders.add({'name': name, 'dose': dose, 'time': time, 'days': days});
    if (nextCreateError != null) return nextCreateError;
    state = state.copyWith(
      reminders: [
        ...state.reminders,
        {'id': 999, 'name': name, 'dose': dose, 'time': time, 'days': days, 'taken_today': false},
      ],
    );
    return null;
  }
}

Future<void> _pump(
  WidgetTester tester, {
  required AutomationState automationState,
  void Function(_FakeAutomationNotifier)? onNotifier,
}) async {
  SharedPreferences.setMockInitialValues({});
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        automationProvider.overrideWith((ref) {
          final n = _FakeAutomationNotifier(ref, initialState: automationState);
          onNotifier?.call(n);
          return n;
        }),
      ],
      child: const MaterialApp(home: RoutineScreen()),
    ),
  );
  // Let the microtask (loadAll + _loadLocalEvents via SharedPreferences) resolve.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}

Future<void> _dismiss(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump();
}

Future<void> _settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 350));
}

void main() {
  testWidgets('routine screen shows loader while reminders loading and calls loadAll', (tester) async {
    addTearDown(() async => _dismiss(tester));
    late _FakeAutomationNotifier notifier;

    await _pump(
      tester,
      automationState: const AutomationState(loadingReminders: true),
      onNotifier: (n) => notifier = n,
    );

    expect(find.byType(BcLoader), findsOneWidget);
    expect(notifier.loadAllCalls, 1);
  });

  testWidgets('routine screen shows empty state when no events', (tester) async {
    addTearDown(() async => _dismiss(tester));

    await _pump(tester, automationState: const AutomationState());

    expect(find.text('NO EVENTS'), findsOneWidget);
  });

  testWidgets('routine screen shows reminder list items', (tester) async {
    addTearDown(() async => _dismiss(tester));

    await _pump(
      tester,
      automationState: const AutomationState(
        reminders: [
          {'id': 1, 'name': 'Aspirin', 'dose': '1 tablet', 'time': '08:00', 'days': 'daily', 'taken_today': false},
          {'id': 2, 'name': 'Vitamin D', 'dose': '1 capsule', 'time': '12:00', 'days': 'daily', 'taken_today': true},
        ],
      ),
    );

    expect(find.text('ASPIRIN'), findsOneWidget);
    expect(find.text('VITAMIN D'), findsOneWidget);
    expect(find.text('TAKE'), findsOneWidget);
    expect(find.text('TAKEN'), findsOneWidget);
  });

  testWidgets('routine screen TAKE button calls markReminderTaken', (tester) async {
    addTearDown(() async => _dismiss(tester));
    late _FakeAutomationNotifier notifier;

    await _pump(
      tester,
      automationState: const AutomationState(
        reminders: [
          {'id': 5, 'name': 'Aspirin', 'dose': '1 tablet', 'time': '08:00', 'days': 'daily', 'taken_today': false},
        ],
      ),
      onNotifier: (n) => notifier = n,
    );

    await tester.tap(find.text('TAKE'));
    await tester.pump();

    expect(notifier.markedTakenIds, [5]);
  });

  testWidgets('routine screen delete button removes reminder', (tester) async {
    addTearDown(() async => _dismiss(tester));
    late _FakeAutomationNotifier notifier;

    await _pump(
      tester,
      automationState: const AutomationState(
        reminders: [
          {'id': 3, 'name': 'Ibuprofen', 'dose': '400mg', 'time': '09:00', 'days': 'Mon-Fri', 'taken_today': false},
        ],
      ),
      onNotifier: (n) => notifier = n,
    );

    await tester.tap(find.byIcon(Icons.delete_outline));
    await tester.pump();

    expect(notifier.deletedIds, [3]);
  });

  testWidgets('routine screen error banner is shown and pull-to-refresh works', (tester) async {
    addTearDown(() async => _dismiss(tester));
    late _FakeAutomationNotifier notifier;

    await _pump(
      tester,
      automationState: const AutomationState(reminderError: 'Server offline'),
      onNotifier: (n) => notifier = n,
    );

    expect(find.text('Server offline'), findsOneWidget);

    await tester.widget<RefreshIndicator>(find.byType(RefreshIndicator)).onRefresh();
    expect(notifier.loadRemindersCalls, 1);
  });

  testWidgets('routine screen FAB opens add event sheet and creates medicine reminder', (tester) async {
    addTearDown(() async => _dismiss(tester));
    late _FakeAutomationNotifier notifier;

    await _pump(
      tester,
      automationState: const AutomationState(),
      onNotifier: (n) => notifier = n,
    );

    await tester.tap(find.byIcon(Icons.add));
    await _settle(tester);

    // Sheet is open — 'SAVE' button is visible
    expect(find.widgetWithText(ElevatedButton, 'SAVE'), findsOneWidget);

    await tester.enterText(
      find.widgetWithText(TextField, 'Title'),
      'Aspirin',
    );
    await tester.pump();

    await tester.tap(find.widgetWithText(ElevatedButton, 'SAVE'));
    await _settle(tester);

    expect(notifier.createdReminders.first['name'], 'Aspirin');
    // Sheet should be dismissed after successful save
    expect(find.widgetWithText(ElevatedButton, 'SAVE'), findsNothing);
  });

  testWidgets('add event sheet shows error and stays open on failure', (tester) async {
    addTearDown(() async => _dismiss(tester));
    late _FakeAutomationNotifier notifier;

    await _pump(
      tester,
      automationState: const AutomationState(),
      onNotifier: (n) {
        notifier = n;
        notifier.nextCreateError = 'Server error.';
      },
    );

    await tester.tap(find.byIcon(Icons.add));
    await _settle(tester);

    await tester.enterText(
      find.widgetWithText(TextField, 'Title'),
      'Test',
    );
    await tester.pump();
    await tester.tap(find.widgetWithText(ElevatedButton, 'SAVE'));
    await tester.pump();

    expect(find.text('Server error.'), findsOneWidget);
    // Sheet stays open
    expect(find.widgetWithText(ElevatedButton, 'SAVE'), findsOneWidget);
  });

  testWidgets('add event sheet shows validation error when title is empty', (tester) async {
    addTearDown(() async => _dismiss(tester));

    await _pump(tester, automationState: const AutomationState());

    await tester.tap(find.byIcon(Icons.add));
    await _settle(tester);

    await tester.tap(find.widgetWithText(ElevatedButton, 'SAVE'));
    await tester.pump();

    expect(find.text('Title is required.'), findsOneWidget);
  });
}
