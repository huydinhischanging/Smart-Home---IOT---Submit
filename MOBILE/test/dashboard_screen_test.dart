import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_home_mobile/core/auth_provider.dart';
import 'package:smart_home_mobile/core/cfg_provider.dart';
import 'package:smart_home_mobile/core/socket_service.dart';
import 'package:smart_home_mobile/core/bc.dart';
import 'package:smart_home_mobile/modules/dashboard/dashboard_provider.dart';
import 'package:smart_home_mobile/modules/report/report_email_provider.dart';
import 'package:smart_home_mobile/screens/dashboard_screen.dart';
import 'package:smart_home_mobile/widgets/common_widgets.dart';

class _FakeAuthNotifier extends AuthNotifier {
  _FakeAuthNotifier(super.state) : super.test();
}

class _FakeCfgNotifier extends CfgNotifier {
  _FakeCfgNotifier(String initialState) : super() {
    state = initialState;
  }
}

class _FakeReportEmailNotifier extends ReportEmailNotifier {
  _FakeReportEmailNotifier(super.ref) : super();
}

class _FakeDashboardNotifier extends DashboardNotifier {
  _FakeDashboardNotifier(
    super.ref, {
    required DashboardState initialState,
  }) : super() {
    state = initialState;
  }

  int loadCalls = 0;
  int refreshCalls = 0;
  final List<Map<String, Object?>> powerCalls = [];

  @override
  Future<void> load() async {
    loadCalls += 1;
  }

  @override
  Future<void> refreshDevices() async {
    refreshCalls += 1;
  }

  @override
  Future<bool> setDevicePower(Map<String, dynamic> device, bool isOn) async {
    final deviceName = (device['name'] as String?) ?? '';
    powerCalls.add({'deviceName': deviceName, 'isOn': isOn});
    state = state.copyWith(
      devices: state.devices.map((d) {
        if (d['name'] == deviceName) return {...d, 'is_on': isOn};
        return d;
      }).toList(),
    );
    return true;
  }

}

class _FakeSocketService extends SocketService {
  final _deviceCtrl = StreamController<Map<String, dynamic>>.broadcast();
  final _alertCtrl = StreamController<Map<String, dynamic>>.broadcast();

  String? connectedBaseUrl;
  String? connectedToken;

  @override
  Stream<Map<String, dynamic>> get onDeviceUpdate => _deviceCtrl.stream;

  @override
  Stream<Map<String, dynamic>> get onNewAlert => _alertCtrl.stream;

  @override
  void connect(String baseUrl, String token) {
    connectedBaseUrl = baseUrl;
    connectedToken = token;
  }

  void emitDevice(Map<String, dynamic> payload) => _deviceCtrl.add(payload);

  void emitAlert(Map<String, dynamic> payload) => _alertCtrl.add(payload);

  @override
  void disconnect() {}

  @override
  void dispose() {
    _deviceCtrl.close();
    _alertCtrl.close();
  }
}

Future<void> _pumpDashScreen(
  WidgetTester tester, {
  required DashboardState dashboardState,
  _FakeSocketService? socketService,
  AuthState authState = const AuthState(
    token: 'token',
    username: 'Demo User',
    email: 'demo@example.com',
    isLoading: false,
  ),
  String cfgState = 'http://127.0.0.1:5000',
  int notifBadge = 0,
  void Function(_FakeDashboardNotifier notifier)? onDashboardNotifier,
}) async {
  SharedPreferences.setMockInitialValues({});
  final socket = socketService ?? _FakeSocketService();

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authProvider.overrideWith((_) => _FakeAuthNotifier(authState)),
        cfgProvider.overrideWith((_) => _FakeCfgNotifier(cfgState)),
        reportEmailProvider.overrideWith((ref) => _FakeReportEmailNotifier(ref)),
        dashboardProvider.overrideWith((ref) {
          final notifier = _FakeDashboardNotifier(ref, initialState: dashboardState);
          onDashboardNotifier?.call(notifier);
          return notifier;
        }),
        socketServiceProvider.overrideWithValue(socket),
        notifBadgeProvider.overrideWith((_) => notifBadge),
      ],
      child: const MaterialApp(home: DashScreen()),
    ),
  );

  await tester.pump();
}

Future<void> _disposeDashScreen(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump();
}

Future<void> _pumpRouteTransition(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 350));
}

void main() {
  testWidgets('dashboard shows loader while state is loading', (tester) async {
    addTearDown(() async => _disposeDashScreen(tester));
    await _pumpDashScreen(
      tester,
      dashboardState: const DashboardState(loading: true),
    );

    expect(find.byType(BcLoader), findsOneWidget);
  });

  testWidgets('dashboard shows error banner when provider has error', (tester) async {
    addTearDown(() async => _disposeDashScreen(tester));
    await _pumpDashScreen(
      tester,
      dashboardState: const DashboardState(
        devices: [],
        rooms: [],
        loading: false,
        error: 'Devices offline',
      ),
    );

    expect(find.text('Devices offline'), findsOneWidget);
    expect(find.text('NO DEVICES FOUND'), findsNothing);
  });

  testWidgets('dashboard shows empty state when there are no devices and no error',
      (tester) async {
    addTearDown(() async => _disposeDashScreen(tester));
    await _pumpDashScreen(
      tester,
      dashboardState: const DashboardState(
        devices: [],
        rooms: [],
        loading: false,
      ),
    );

    await tester.scrollUntilVisible(
      find.text('NO DEVICES FOUND'),
      250,
      scrollable: find.byType(Scrollable).first,
    );

    expect(find.text('NO DEVICES FOUND'), findsOneWidget);
  });

  testWidgets('dashboard top bar shows counts and opens settings/notifications',
      (tester) async {
    addTearDown(() async => _disposeDashScreen(tester));
    await _pumpDashScreen(
      tester,
      dashboardState: const DashboardState(
        devices: [
          {'name': 'Lamp', 'is_on': true, 'room_id': 1},
          {'name': 'Fan', 'is_on': false, 'room_id': 1},
        ],
        rooms: [
          {'id': 1, 'name': 'Living Room'},
        ],
      ),
      notifBadge: 3,
    );

    expect(find.text('1 ONLINE'), findsOneWidget);
    expect(find.text('2 REGISTERED'), findsOneWidget);
    expect(find.text('3'), findsOneWidget);

    await tester.ensureVisible(find.byIcon(Icons.settings_outlined).first);
    await tester.tap(find.byIcon(Icons.settings_outlined).first);
    await _pumpRouteTransition(tester);
    expect(find.text('SETTINGS'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.arrow_back_ios_rounded).first);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    await tester.ensureVisible(find.byIcon(Icons.notifications_outlined).first);
    await tester.tap(find.byIcon(Icons.notifications_outlined).first);
    await _pumpRouteTransition(tester);
    expect(find.text('ALERT CENTER'), findsOneWidget);
  });

  testWidgets('dashboard refresh controls trigger load actions', (tester) async {
    addTearDown(() async => _disposeDashScreen(tester));
    late _FakeDashboardNotifier notifier;

    await _pumpDashScreen(
      tester,
      dashboardState: const DashboardState(
        devices: [
          {'name': 'Lamp', 'is_on': true, 'room_id': 1},
        ],
        rooms: [
          {'id': 1, 'name': 'Living Room'},
        ],
      ),
      onDashboardNotifier: (value) => notifier = value,
    );

    final initialLoadCalls = notifier.loadCalls;

    await tester.tap(find.byIcon(Icons.refresh_rounded).first);
    await tester.pump();
    expect(notifier.loadCalls, initialLoadCalls + 1);

    await tester.widget<RefreshIndicator>(find.byType(RefreshIndicator)).onRefresh();
    expect(notifier.loadCalls, initialLoadCalls + 2);
  });

  testWidgets('dashboard polling fallback refreshes devices periodically',
      (tester) async {
    addTearDown(() async => _disposeDashScreen(tester));
    late _FakeDashboardNotifier notifier;

    await _pumpDashScreen(
      tester,
      dashboardState: const DashboardState(),
      onDashboardNotifier: (value) => notifier = value,
    );

    expect(notifier.refreshCalls, 0);
    await tester.pump(const Duration(seconds: 16));
    expect(notifier.refreshCalls, 1);
  });

  testWidgets('dashboard applies socket device updates and infers device icons',
      (tester) async {
    addTearDown(() async => _disposeDashScreen(tester));
    final socket = _FakeSocketService();

    await _pumpDashScreen(
      tester,
      socketService: socket,
      dashboardState: const DashboardState(
        devices: [
          {'name': 'Ceiling Fan', 'icon': '⚙️', 'is_on': false, 'room_id': 1, 'device_code': 'fan-1'},
          {'name': 'Cooler', 'type': 'ac', 'is_on': true, 'room_id': 1},
          {'name': 'Guard', 'type': 'camera', 'is_on': true, 'room_id': 1},
          {'name': 'Living TV', 'is_on': true, 'room_id': 1},
          {'name': 'Thermo', 'type': 'temp sensor', 'is_on': true, 'room_id': 1},
          {'name': 'Mystery Plug', 'type': 'misc', 'is_on': true, 'room_id': 1},
        ],
        rooms: [
          {'id': 1, 'name': 'Living Room'},
        ],
      ),
    );

    socket.emitDevice({'device_code': 'fan-1', 'is_on': true});
    socket.emitDevice({'is_on': false});
    await tester.pump();

    await tester.scrollUntilVisible(
      find.text('MYSTERY PLUG'),
      250,
      scrollable: find.byType(Scrollable).first,
    );

    expect(find.text('MYSTERY PLUG'), findsOneWidget);
    expect(find.text('ONLINE'), findsWidgets);
    expect(find.text('🔌'), findsOneWidget);
  });

  testWidgets('dashboard toggles device power when a device card is tapped',
      (tester) async {
    addTearDown(() async => _disposeDashScreen(tester));
    late _FakeDashboardNotifier notifier;
    await _pumpDashScreen(
      tester,
      dashboardState: const DashboardState(
        devices: [
          {'name': 'Lamp', 'is_on': false, 'room_id': 1, 'icon': '💡'},
        ],
        rooms: [
          {'id': 1, 'name': 'Living Room'},
        ],
      ),
      onDashboardNotifier: (value) => notifier = value,
    );

    await tester.scrollUntilVisible(
      find.text('LAMP'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pump();

    final lampFinder = find.text('LAMP');
    final lampCard = find.ancestor(
      of: lampFinder,
      matching: find.byType(GestureDetector),
    ).first;

    expect(
      find.descendant(of: lampCard, matching: find.text('STANDBY')),
      findsOneWidget,
    );

    await tester.tap(lampFinder);
    await tester.pump(const Duration(milliseconds: 300));

    expect(notifier.powerCalls, [
      {'deviceName': 'Lamp', 'isOn': true}
    ]);
    expect(
      find.descendant(of: lampCard, matching: find.text('ONLINE')),
      findsOneWidget,
    );
  });

  testWidgets('dashboard reacts to socket alerts with snackbar', (tester) async {
    addTearDown(() async => _disposeDashScreen(tester));
    final socket = _FakeSocketService();

    await _pumpDashScreen(
      tester,
      dashboardState: const DashboardState(),
      socketService: socket,
      cfgState: 'http://192.168.1.10:5000',
    );

    expect(socket.connectedBaseUrl, 'http://192.168.1.10:5000');
    expect(socket.connectedToken, 'token');

    socket.emitAlert({'level': 'critical', 'message': 'Smoke detected'});
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('[CRITICAL] Smoke detected'), findsOneWidget);
  });
}