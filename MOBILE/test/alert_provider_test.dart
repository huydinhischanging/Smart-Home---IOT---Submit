import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smart_home_mobile/core/api_context_provider.dart';
import 'package:smart_home_mobile/core/http_client_provider.dart';
import 'package:smart_home_mobile/modules/alert/alert_provider.dart';

void main() {
  test('alert item parsing and state helpers use defaults', () {
    final item = AlertItem.fromJson(const {});
    const state = AlertState(
      alerts: [
        AlertItem(
          id: 9,
          deviceCode: 'S9',
          message: 'Fallback',
          level: 'info',
          isRead: false,
          createdAt: '2026-04-14T10:00:00Z',
        ),
      ],
      unread: 1,
      loading: true,
      error: 'boom',
    );

    expect(item.id, 0);
    expect(item.deviceCode, '');
    expect(item.message, '');
    expect(item.level, 'info');
    expect(item.isRead, false);
    expect(item.createdAt, '');
    expect(state.clearError().error, isNull);
    expect(state.clearError().alerts, hasLength(1));
    expect(state.clearError().unread, 1);
    expect(state.clearError().loading, true);
  });

  test('alert provider loads alerts and unread count', () async {
    final client = MockClient(
      (_) async => http.Response(
        '{"data":[{"id":1,"device_code":"S1","message":"SOS","level":"critical","is_read":false,"created_at":"2026-04-14T10:00:00Z"}],"unread":1}',
        200,
      ),
    );

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    await container.read(alertProvider.notifier).load();
    final state = container.read(alertProvider);

    expect(state.alerts, hasLength(1));
    expect(state.unread, 1);
    expect(state.alerts.single.level, 'critical');
  });

  test('alert provider load handles non-200 responses', () async {
    final client = MockClient((_) async => http.Response('Denied', 403));

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    await container.read(alertProvider.notifier).load(limit: 80);
    final state = container.read(alertProvider);

    expect(state.loading, false);
    expect(state.error, 'HTTP 403');
  });

  test('alert provider load handles exceptions', () async {
    final client = MockClient((_) async => throw http.ClientException('offline'));

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    await container.read(alertProvider.notifier).load();
    final state = container.read(alertProvider);

    expect(state.loading, false);
    expect(state.error, contains('offline'));
  });

  test('alert provider markRead updates unread and state', () async {
    final client = MockClient((_) async => http.Response('{"success":true}', 200));

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    final notifier = container.read(alertProvider.notifier);
    notifier.state = notifier.state.copyWith(
      alerts: const [
        AlertItem(
          id: 1,
          deviceCode: 'S1',
          message: 'SOS',
          level: 'critical',
          isRead: false,
          createdAt: '2026-04-14T10:00:00Z',
        )
      ],
      unread: 1,
    );

    await notifier.markRead(1);

    final state = container.read(alertProvider);
    expect(state.unread, 0);
    expect(state.alerts.single.isRead, true);
  });

  test('alert provider markRead reloads on patch failure', () async {
    var patchCalls = 0;
    var getCalls = 0;
    final client = MockClient((request) async {
      if (request.method == 'PATCH') {
        patchCalls += 1;
        throw http.ClientException('offline');
      }
      if (request.method == 'GET') {
        getCalls += 1;
        return http.Response(
          '{"data":[{"id":1,"device_code":"S1","message":"SOS","level":"critical","is_read":false,"created_at":"2026-04-14T10:00:00Z"}],"unread":1}',
          200,
        );
      }
      return http.Response('Not found', 404);
    });

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    final notifier = container.read(alertProvider.notifier);
    notifier.state = notifier.state.copyWith(
      alerts: const [
        AlertItem(
          id: 1,
          deviceCode: 'S1',
          message: 'SOS',
          level: 'critical',
          isRead: false,
          createdAt: '2026-04-14T10:00:00Z',
        )
      ],
      unread: 1,
    );

    await notifier.markRead(1);

    final state = container.read(alertProvider);
    expect(patchCalls, 1);
    expect(getCalls, 1);
    expect(state.unread, 1);
    expect(state.alerts.single.isRead, false);
  });

  test('alert provider markAllRead marks only unread alerts', () async {
    final patched = <int>[];
    final client = MockClient((request) async {
      if (request.method == 'PATCH') {
        final id = int.parse(request.url.pathSegments[2]);
        patched.add(id);
        return http.Response('{"success":true}', 200);
      }
      return http.Response('Not found', 404);
    });

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    final notifier = container.read(alertProvider.notifier);
    notifier.state = notifier.state.copyWith(
      alerts: const [
        AlertItem(
          id: 1,
          deviceCode: 'S1',
          message: 'SOS',
          level: 'critical',
          isRead: false,
          createdAt: '2026-04-14T10:00:00Z',
        ),
        AlertItem(
          id: 2,
          deviceCode: 'S2',
          message: 'Done',
          level: 'info',
          isRead: true,
          createdAt: '2026-04-14T10:00:00Z',
        ),
        AlertItem(
          id: 3,
          deviceCode: 'S3',
          message: 'Door',
          level: 'warning',
          isRead: false,
          createdAt: '2026-04-14T10:00:00Z',
        ),
      ],
      unread: 2,
    );

    await notifier.markAllRead();

    final state = container.read(alertProvider);
    expect(patched, [1, 3]);
    expect(state.unread, 0);
    expect(state.alerts.every((alert) => alert.isRead), true);
  });

  test('alert provider prepends alerts received from socket', () {
    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(MockClient((_) async => http.Response('{}', 200))),
    ]);
    addTearDown(container.dispose);

    final notifier = container.read(alertProvider.notifier);
    notifier.state = notifier.state.copyWith(
      alerts: const [
        AlertItem(
          id: 1,
          deviceCode: 'S1',
          message: 'Existing',
          level: 'warning',
          isRead: false,
          createdAt: '2026-04-14T10:00:00Z',
        ),
      ],
      unread: 1,
    );

    notifier.addFromSocket({
      'id': 2,
      'device_code': 'S2',
      'message': 'New alert',
      'level': 'critical',
      'created_at': '2026-04-15T08:00:00Z',
    });

    notifier.addFromSocket(const {'message': 'Fallback'});

    final state = container.read(alertProvider);
    expect(state.unread, 3);
    expect(state.alerts.first.message, 'Fallback');
    expect(state.alerts.first.level, 'info');
    expect(state.alerts[1].message, 'New alert');
    expect(state.alerts[1].deviceCode, 'S2');

    notifier.addFromSocket({'id': 'broken'});

    final afterMalformed = container.read(alertProvider);
    expect(afterMalformed.unread, 3);
    expect(afterMalformed.alerts, hasLength(3));
  });
}