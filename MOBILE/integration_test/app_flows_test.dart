import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:integration_test/integration_test.dart';
import 'package:smart_home_mobile/core/api_context_provider.dart';
import 'package:smart_home_mobile/core/auth_provider.dart';
import 'package:smart_home_mobile/core/http_client_provider.dart';
import 'package:smart_home_mobile/modules/alert/alert_provider.dart';
import 'package:smart_home_mobile/modules/auth/auth_service.dart';
import 'package:smart_home_mobile/modules/dashboard/dashboard_provider.dart';
import 'package:smart_home_mobile/modules/sensor/sensor_provider.dart';
import 'package:smart_home_mobile/screens/alfred_screen.dart';
import 'package:smart_home_mobile/screens/dashboard_screen.dart';
import 'package:smart_home_mobile/screens/health_screen.dart';
import 'package:smart_home_mobile/screens/login_screen.dart';
import 'package:smart_home_mobile/screens/map_screen.dart';
import 'package:smart_home_mobile/screens/notifications_screen.dart';
import 'package:smart_home_mobile/screens/routine_screen.dart';
import 'package:smart_home_mobile/screens/settings_screen.dart';

class _SeededDashboardNotifier extends DashboardNotifier {
  _SeededDashboardNotifier(super.ref, DashboardState initialState) {
    state = initialState;
  }

  @override
  Future<void> load() async {}

  @override
  Future<void> refreshDevices() async {}
}

class _SeededAlertNotifier extends AlertNotifier {
  _SeededAlertNotifier(super.ref, AlertState initialState) {
    state = initialState;
  }

  @override
  Future<void> load({int limit = 50}) async {}
}

class _InMemoryAuthNotifier extends AuthNotifier {
  _InMemoryAuthNotifier([AuthState initialState = const AuthState(isLoading: false)])
      : super() {
    state = initialState;
  }

  @override
  Future<void> login({
    required String token,
    required String username,
    int? userId,
    String? email,
  }) async {
    state = AuthState(
      token: token,
      username: username,
      userId: userId,
      email: email,
      isLoading: false,
    );
  }

  @override
  Future<void> logout() async {
    state = const AuthState(isLoading: false);
  }
}

class _SeededSensorNotifier extends SensorNotifier {
  _SeededSensorNotifier(super.ref, SensorState initialState) {
    state = initialState;
  }

  @override
  Future<void> loadHrRecords({int limit = 100}) async {}
}

Widget _buildTestApp({
  required Widget home,
  required http.Client client,
  List<Override> overrides = const [],
  Map<String, WidgetBuilder> routes = const {},
}) {
  return ProviderScope(
    overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
      ...overrides,
    ],
    child: MaterialApp(home: home, routes: routes),
  );
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('dashboard screen loads device data and toggles a device', (tester) async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices/control') {
        return http.Response('{"success":true}', 200);
      }
      return http.Response('Not found', 404);
    });

    await tester.pumpWidget(_buildTestApp(
      home: const DashScreen(),
      client: client,
      overrides: [
        dashboardProvider.overrideWith(
          (ref) => _SeededDashboardNotifier(
            ref,
            const DashboardState(
              devices: [
                {'name': 'Lamp', 'room': 'Living', 'room_id': '1', 'is_on': true},
              ],
              rooms: [
                {'id': '1', 'name': 'Living'},
              ],
            ),
          ),
        ),
      ],
    ));
    await tester.pump(const Duration(milliseconds: 300));

    await tester.scrollUntilVisible(
      find.text('LAMP'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('LAMP'), findsOneWidget);
    expect(find.text('Living'), findsWidgets);
    expect(find.text('ONLINE'), findsOneWidget);

    await tester.tap(find.text('LAMP'));
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('STANDBY'), findsWidgets);
  });

  testWidgets('alfred screen sends a message and renders reply', (tester) async {
    final client = MockClient(
      (_) async => http.Response('{"reply":"All systems nominal."}', 200),
    );

    await tester.pumpWidget(_buildTestApp(home: const AlfredScreen(), client: client));
    await tester.pump(const Duration(milliseconds: 200));

    await tester.enterText(find.byType(TextField), 'status');
    await tester.tap(find.byIcon(Icons.send_rounded));
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('status'), findsOneWidget);
    expect(find.text('All systems nominal.'), findsOneWidget);
  });

  testWidgets('login screen authenticates with mocked backend', (tester) async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/auth/login' && request.method == 'POST') {
        return http.Response(
          '{"status":"success","token":"token-123","user":{"id":7,"username":"demo-operator"}}',
          200,
        );
      }
      return http.Response('Not found', 404);
    });

    await tester.pumpWidget(_buildTestApp(
      home: const LoginScreen(),
      client: client,
      overrides: [
        authProvider.overrideWith((_) => _InMemoryAuthNotifier()),
        authServiceProvider.overrideWithValue(
          AuthService(baseUrl: 'http://example.test', client: client),
        ),
      ],
      routes: {
        '/settings': (_) => const SettingsScreen(),
      },
    ));
    await tester.pump(const Duration(milliseconds: 400));

    final container = ProviderScope.containerOf(tester.element(find.byType(LoginScreen)));

    await tester.enterText(find.byKey(const ValueKey('login.identity')), 'demo@smarthome.local');
    await tester.enterText(find.byKey(const ValueKey('login.password')), 'Demo@1234');
    await tester.tap(find.byKey(const ValueKey('login.submit')));
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(milliseconds: 400));

    final authState = container.read(authProvider);
    expect(authState.isLoggedIn, true);
    expect(authState.username, 'demo-operator');
  });

  testWidgets('login screen opens settings route and quick select fills url', (tester) async {
    final client = MockClient((_) async => http.Response('Not found', 404));

    await tester.pumpWidget(_buildTestApp(
      home: const LoginScreen(),
      client: client,
      overrides: [
        authProvider.overrideWith((_) => _InMemoryAuthNotifier()),
      ],
      routes: {
        '/settings': (_) => const SettingsScreen(),
      },
    ));
    await tester.pump(const Duration(milliseconds: 400));

    await tester.tap(find.text('Configure server URL'));
    await tester.pumpAndSettle();

    expect(find.text('SETTINGS'), findsOneWidget);

    await tester.tap(find.text('iOS Simulator'));
    await tester.pump(const Duration(milliseconds: 200));

    final editable = tester.widget<EditableText>(find.byType(EditableText).first);
    expect(editable.controller.text, 'http://localhost:5000');
  });

  testWidgets('routine screen opens sheet and creates a schedule', (tester) async {
    var scheduleCreated = false;
    final client = MockClient((request) async {
      if (request.url.path == '/api/devices') {
        return http.Response('{"data":[{"id":1,"name":"Lamp"}]}', 200);
      }
      if (request.url.path == '/api/automation/schedules' && request.method == 'GET') {
        return http.Response(
          scheduleCreated
              ? '{"data":[{"id":10,"device_id":1,"action":"1","cron_expr":"0 7 * * *","is_active":true}]}'
              : '{"data":[]}',
          200,
        );
      }
      if (request.url.path == '/api/automation/automations') {
        return http.Response('{"data":[]}', 200);
      }
      if (request.url.path == '/api/automation/schedules' && request.method == 'POST') {
        scheduleCreated = true;
        return http.Response('{"success":true,"id":10}', 201);
      }
      return http.Response('Not found', 404);
    });

    await tester.pumpWidget(_buildTestApp(home: const RoutineScreen(), client: client));
    await tester.pumpAndSettle();

    expect(find.text('NO SCHEDULES'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle();

    expect(find.text('NEW SCHEDULE'), findsOneWidget);
    await tester.tap(find.byIcon(Icons.expand_more));
    await tester.pumpAndSettle();
    await tester.tap(find.text('LAMP').last);
    await tester.pumpAndSettle();

    await tester.tap(find.text('CREATE SCHEDULE'));
    await tester.pumpAndSettle();

    expect(find.text('Lamp'), findsOneWidget);
    expect(find.text('0 7 * * *'), findsOneWidget);
  });

  testWidgets('settings screen saves and resets backend url', (tester) async {
    final client = MockClient((_) async => http.Response('Not found', 404));

    await tester.pumpWidget(_buildTestApp(home: const SettingsScreen(), client: client));
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('SETTINGS'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'http://demo.local:7000/');
    await tester.tap(find.text('SAVE'));
    await tester.pump(const Duration(milliseconds: 250));
    await tester.pump(const Duration(milliseconds: 250));

    expect(find.text('Server URL saved.'), findsOneWidget);
    expect(find.textContaining('Current: http://demo.local:7000'), findsOneWidget);

    await tester.tap(find.text('RESET'));
    await tester.pump(const Duration(milliseconds: 250));
    await tester.pump(const Duration(milliseconds: 250));

    expect(find.textContaining('Current: http://127.0.0.1:5000'), findsOneWidget);
  });

  testWidgets('settings screen signs out the active account', (tester) async {
    final client = MockClient((_) async => http.Response('Not found', 404));

    await tester.pumpWidget(_buildTestApp(
      home: const SettingsScreen(),
      client: client,
      overrides: [
        authProvider.overrideWith(
          (_) => _InMemoryAuthNotifier(
            const AuthState(
              token: 'token-xyz',
              username: 'bruce',
              userId: 1,
              isLoading: false,
            ),
          ),
        ),
      ],
    ));
    await tester.pump(const Duration(milliseconds: 400));

    final container = ProviderScope.containerOf(tester.element(find.byType(SettingsScreen)));

    expect(find.text('AUTHENTICATED'), findsOneWidget);
    await tester.tap(find.text('SIGN OUT').first);
    await tester.pumpAndSettle();

    expect(find.text('Sign out?'), findsOneWidget);
    expect(find.textContaining('Log out?'), findsOneWidget);

    await tester.tap(find.text('SIGN OUT').last);
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 300));

    expect(container.read(authProvider).isLoggedIn, false);
    expect(find.text('Not logged in.'), findsOneWidget);
  });

  testWidgets('notifications screen filters unread alerts and marks all read', (tester) async {
    final client = MockClient((request) async {
      if (request.method == 'PATCH' && request.url.path.contains('/api/alerts/')) {
        return http.Response('{"success":true}', 200);
      }
      return http.Response('Not found', 404);
    });

    await tester.pumpWidget(_buildTestApp(
      home: const NotificationsScreen(),
      client: client,
      overrides: [
        alertProvider.overrideWith(
          (ref) => _SeededAlertNotifier(
            ref,
            const AlertState(
              alerts: [
                AlertItem(
                  id: 1,
                  deviceCode: 'SOS-01',
                  message: 'SOS trigger detected',
                  level: 'critical',
                  isRead: false,
                  createdAt: '2026-04-14T08:00:00Z',
                ),
                AlertItem(
                  id: 2,
                  deviceCode: 'MED-02',
                  message: 'Medicine reminder sent',
                  level: 'warning',
                  isRead: true,
                  createdAt: '2026-04-14T08:05:00Z',
                ),
                AlertItem(
                  id: 3,
                  deviceCode: 'DOOR-03',
                  message: 'Front door left open',
                  level: 'warning',
                  isRead: false,
                  createdAt: '2026-04-14T08:10:00Z',
                ),
              ],
              unread: 2,
            ),
          ),
        ),
      ],
    ));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('2 UNREAD'), findsOneWidget);
    expect(find.text('MARK ALL'), findsOneWidget);

    await tester.tap(find.text('UNREAD'));
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('SOS trigger detected'), findsOneWidget);
    expect(find.text('Front door left open'), findsOneWidget);
    expect(find.text('Medicine reminder sent'), findsNothing);

    await tester.tap(find.text('MARK ALL'));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('0 UNREAD'), findsOneWidget);
    expect(find.text('MARK ALL'), findsNothing);
  });

  testWidgets('notifications screen marks a single alert as read', (tester) async {
    final client = MockClient((request) async {
      if (request.method == 'PATCH' && request.url.path.contains('/api/alerts/')) {
        return http.Response('{"success":true}', 200);
      }
      return http.Response('Not found', 404);
    });

    await tester.pumpWidget(_buildTestApp(
      home: const NotificationsScreen(),
      client: client,
      overrides: [
        alertProvider.overrideWith(
          (ref) => _SeededAlertNotifier(
            ref,
            const AlertState(
              alerts: [
                AlertItem(
                  id: 1,
                  deviceCode: 'SOS-01',
                  message: 'SOS trigger detected',
                  level: 'critical',
                  isRead: false,
                  createdAt: '2026-04-14T08:00:00Z',
                ),
                AlertItem(
                  id: 2,
                  deviceCode: 'DOOR-03',
                  message: 'Front door left open',
                  level: 'warning',
                  isRead: false,
                  createdAt: '2026-04-14T08:10:00Z',
                ),
              ],
              unread: 2,
            ),
          ),
        ),
      ],
    ));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('2 UNREAD'), findsOneWidget);

    await tester.tap(find.text('SOS trigger detected'));
    await tester.pump(const Duration(milliseconds: 250));

    expect(find.text('1 UNREAD'), findsOneWidget);
  });

  testWidgets('health screen renders summary and readings', (tester) async {
    final client = MockClient((_) async => http.Response('Not found', 404));

    await tester.pumpWidget(_buildTestApp(
      home: const HealthScreen(),
      client: client,
      overrides: [
        sensorProvider.overrideWith(
          (ref) => _SeededSensorNotifier(
            ref,
            const SensorState(
              hrRecords: [
                HrRecord(
                  bpm: 72,
                  severity: 'normal',
                  mood: 'steady',
                  risk: 'low',
                  recordedAt: '2026-04-14T08:00:00Z',
                ),
                HrRecord(
                  bpm: 118,
                  severity: 'warning',
                  mood: 'stressed',
                  risk: 'elevated',
                  recordedAt: '2026-04-14T08:05:00Z',
                ),
              ],
              summary: {
                'avg_bpm': 95.0,
                'min_bpm': 72,
                'max_bpm': 118,
                'count': 2,
                'normal_rate_percent': 50.0,
                'severity_counts': {
                  'normal': 1,
                  'warning': 1,
                },
              },
            ),
          ),
        ),
      ],
    ));
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('HEALTH MONITOR'), findsOneWidget);
    expect(find.text('VITALS SUMMARY'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('RECENT READINGS'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('RECENT READINGS'), findsOneWidget);
    expect(find.text('118'), findsWidgets);
    expect(find.textContaining('risk: elevated'), findsOneWidget);
  });

  testWidgets('map screen switches floor and updates visible device list', (tester) async {
    final client = MockClient((request) async {
      switch (request.url.path) {
        case '/api/devices':
          return http.Response('{"data":[{"name":"Lamp","room":"Living","room_id":"101","floor_id":"1","is_on":true},{"name":"Fan","room":"Bedroom","room_id":"201","floor_id":"2","is_on":false}]}', 200);
        case '/api/rooms':
          return http.Response('{"data":[{"id":"101","name":"Living"},{"id":"201","name":"Bedroom"}]}', 200);
        case '/api/map/floors':
          return http.Response('{"data":[{"id":"1","name":"Floor 1","has_blueprint":false,"device_count":1},{"id":"2","name":"Floor 2","has_blueprint":false,"device_count":1}]}', 200);
        case '/api/map/layout/1':
          return http.Response('{"data":{"rooms":[{"id":"101","name":"Living","points":[{"x":0,"y":0}]}],"map_cache":{}}}', 200);
        case '/api/map/layout/2':
          return http.Response('{"data":{"rooms":[{"id":"201","name":"Bedroom","points":[{"x":1,"y":1}]}],"map_cache":{}}}', 200);
      }
      return http.Response('Not found', 404);
    });

    await tester.pumpWidget(_buildTestApp(home: const MapScreen(), client: client));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.textContaining('Lamp'), findsOneWidget);
    expect(find.text('FLOOR 2'), findsOneWidget);

    await tester.tap(find.text('FLOOR 2'));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.textContaining('Fan'), findsOneWidget);
    expect(find.textContaining('Bedroom'), findsWidgets);
  });
}