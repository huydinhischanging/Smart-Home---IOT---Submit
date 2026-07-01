import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_home_mobile/core/bc.dart';
import 'package:smart_home_mobile/modules/alert/alert_provider.dart';
import 'package:smart_home_mobile/screens/notifications_screen.dart';
import 'package:smart_home_mobile/widgets/common_widgets.dart';

class _FakeAlertNotifier extends AlertNotifier {
  _FakeAlertNotifier(
    super.ref, {
    required AlertState initialState,
  }) : super() {
    state = initialState;
  }

  int loadCalls = 0;
  int markAllCalls = 0;
  final List<int> markReadCalls = [];

  void emitState(AlertState nextState) {
    state = nextState;
  }

  @override
  Future<void> load({int limit = 50}) async {
    loadCalls += 1;
  }

  @override
  Future<void> markRead(int alertId) async {
    markReadCalls.add(alertId);
    state = state.copyWith(
      alerts: state.alerts
          .map((alert) => alert.id == alertId ? alert.asRead() : alert)
          .toList(),
      unread: state.alerts.where((alert) => !alert.isRead && alert.id != alertId).length,
    );
  }

  @override
  Future<void> markAllRead() async {
    markAllCalls += 1;
    state = state.copyWith(
      alerts: state.alerts.map((alert) => alert.asRead()).toList(),
      unread: 0,
    );
  }
}

AlertItem _alert({
  required int id,
  required String level,
  required String message,
  bool isRead = false,
}) {
  return AlertItem(
    id: id,
    deviceCode: 'device-$id',
    message: message,
    level: level,
    isRead: isRead,
    createdAt: '2026-04-15T08:30:00Z',
  );
}

Future<void> _pumpNotificationsScreen(
  WidgetTester tester, {
  required AlertState alertState,
  void Function(_FakeAlertNotifier notifier)? onNotifier,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        alertProvider.overrideWith((ref) {
          final notifier = _FakeAlertNotifier(ref, initialState: alertState);
          onNotifier?.call(notifier);
          return notifier;
        }),
        notifBadgeProvider.overrideWith((_) => 0),
      ],
      child: const MaterialApp(home: NotificationsScreen()),
    ),
  );

  await tester.pump();
}

Future<void> _disposeScreen(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump();
}

ProviderContainer _containerFor(WidgetTester tester) {
  return ProviderScope.containerOf(tester.element(find.byType(NotificationsScreen)));
}

Finder _filterChip(String label) => find.text(label).first;

Finder _tileForMessage(String message) {
  return find.ancestor(
    of: find.text(message),
    matching: find.byType(BcNotifTile),
  ).first;
}

void main() {
  testWidgets('notifications shows loader while loading', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeAlertNotifier notifier;

    await _pumpNotificationsScreen(
      tester,
      alertState: const AlertState(loading: true),
      onNotifier: (value) => notifier = value,
    );

    expect(find.byType(BcLoader), findsOneWidget);
    expect(notifier.loadCalls, 1);
  });

  testWidgets('notifications shows error banner and supports refresh', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeAlertNotifier notifier;

    await _pumpNotificationsScreen(
      tester,
      alertState: const AlertState(error: 'Server offline'),
      onNotifier: (value) => notifier = value,
    );

    expect(find.text('Server offline'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.refresh_rounded));
    await tester.pump();
    expect(notifier.loadCalls, 2);

    await tester.widget<RefreshIndicator>(find.byType(RefreshIndicator)).onRefresh();
    expect(notifier.loadCalls, 3);
  });

  testWidgets('notifications shows empty state when no alerts match', (tester) async {
    addTearDown(() async => _disposeScreen(tester));

    await _pumpNotificationsScreen(
      tester,
      alertState: const AlertState(alerts: [], unread: 0),
    );

    expect(find.text('NO ALERTS'), findsOneWidget);
    expect(find.text('MARK ALL'), findsNothing);
  });

  testWidgets('notifications filters by unread critical and warning', (tester) async {
    addTearDown(() async => _disposeScreen(tester));

    await _pumpNotificationsScreen(
      tester,
      alertState: AlertState(
        alerts: [
          _alert(id: 1, level: 'critical', message: 'Smoke detected'),
          _alert(id: 2, level: 'warning', message: 'Door left open'),
          _alert(id: 3, level: 'info', message: 'Routine completed', isRead: true),
        ],
        unread: 2,
      ),
    );

    expect(find.text('Smoke detected'), findsOneWidget);
    expect(find.text('Door left open'), findsOneWidget);
    expect(find.text('Routine completed'), findsOneWidget);

    await tester.tap(_filterChip('UNREAD'));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('Smoke detected'), findsOneWidget);
    expect(find.text('Door left open'), findsOneWidget);
    expect(find.text('Routine completed'), findsNothing);

    await tester.tap(_filterChip('CRITICAL'));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('Smoke detected'), findsOneWidget);
    expect(find.text('Door left open'), findsNothing);

    await tester.tap(_filterChip('WARNING'));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('Smoke detected'), findsNothing);
    expect(find.text('Door left open'), findsOneWidget);

    await tester.tap(_filterChip('ALL'));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('Routine completed'), findsOneWidget);
  });

  testWidgets('notifications marks unread alerts read and syncs badge count', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeAlertNotifier notifier;

    await _pumpNotificationsScreen(
      tester,
      alertState: AlertState(
        alerts: [
          _alert(id: 1, level: 'critical', message: 'Smoke detected'),
          _alert(id: 2, level: 'info', message: 'Daily summary ready', isRead: true),
        ],
        unread: 1,
      ),
      onNotifier: (value) => notifier = value,
    );

    final container = _containerFor(tester);
    expect(container.read(notifBadgeProvider), 0);

    notifier.emitState(
      AlertState(
        alerts: [
          _alert(id: 1, level: 'critical', message: 'Smoke detected'),
          _alert(id: 2, level: 'info', message: 'Daily summary ready', isRead: true),
        ],
        unread: 3,
      ),
    );
    await tester.pump();
    expect(container.read(notifBadgeProvider), 3);

    await tester.tap(_tileForMessage('Smoke detected'));
    await tester.pump(const Duration(milliseconds: 250));

    expect(notifier.markReadCalls, [1]);
    expect(container.read(notifBadgeProvider), 0);
    expect(find.text('0 UNREAD'), findsOneWidget);

    await tester.tap(_tileForMessage('Daily summary ready'));
    await tester.pump();
    expect(notifier.markReadCalls, [1]);
  });

  testWidgets('notifications mark all reads everything and hides action', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeAlertNotifier notifier;

    await _pumpNotificationsScreen(
      tester,
      alertState: AlertState(
        alerts: [
          _alert(id: 1, level: 'critical', message: 'Smoke detected'),
          _alert(id: 2, level: 'warning', message: 'Door left open'),
        ],
        unread: 2,
      ),
      onNotifier: (value) => notifier = value,
    );

    expect(find.text('MARK ALL'), findsOneWidget);

    await tester.tap(find.text('MARK ALL'));
    await tester.pump(const Duration(milliseconds: 250));

    expect(notifier.markAllCalls, 1);
    expect(find.text('MARK ALL'), findsNothing);
    expect(find.text('0 UNREAD'), findsOneWidget);
  });
}