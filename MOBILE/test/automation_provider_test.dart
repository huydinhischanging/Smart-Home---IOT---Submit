import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smart_home_mobile/core/api_context_provider.dart';
import 'package:smart_home_mobile/core/http_client_provider.dart';
import 'package:smart_home_mobile/modules/automation/automation_provider.dart';

ProviderContainer _makeContainer(http.Client client) {
  return ProviderContainer(overrides: [
    apiBaseUrlProvider.overrideWithValue('http://example.test'),
    authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
    httpClientProvider.overrideWithValue(client),
  ]);
}

void main() {
  test('AutomationState copyWith replaces expected fields', () {
    const state = AutomationState(
      reminders: [
        {'id': 1, 'name': 'Aspirin'}
      ],
      loadingReminders: true,
      reminderError: 'old error',
      emailEnabled: true,
    );

    final next = state.copyWith(
      loadingReminders: false,
      reminderError: null,
    );

    expect(next.reminders, hasLength(1));
    expect(next.loadingReminders, false);
    expect(next.reminderError, isNull);
    expect(next.emailEnabled, true);
  });

  test('loadReminders populates reminders and emailEnabled', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/reminders') {
        return http.Response(
          '{"success":true,"data":[{"id":1,"name":"Aspirin","dose":"1 tablet","time":"08:00","days":"daily","taken_today":false}],"email_enabled":true}',
          200,
        );
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    await container.read(automationProvider.notifier).loadReminders();
    final state = container.read(automationProvider);

    expect(state.reminders, hasLength(1));
    expect(state.reminders.first['name'], 'Aspirin');
    expect(state.emailEnabled, true);
    expect(state.loadingReminders, false);
    expect(state.reminderError, isNull);
  });

  test('loadAll delegates to loadReminders', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/reminders') {
        return http.Response(
          '{"data":[{"id":2,"name":"Vitamin C"}],"email_enabled":false}',
          200,
        );
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    await container.read(automationProvider.notifier).loadAll();
    expect(container.read(automationProvider).reminders.first['name'], 'Vitamin C');
  });

  test('loadReminders surfaces HTTP and network errors', () async {
    var shouldThrow = false;
    final client = MockClient((request) async {
      if (request.url.path == '/api/reminders') {
        if (shouldThrow) throw http.ClientException('offline');
        return http.Response('Denied', 503);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(automationProvider.notifier);

    await notifier.loadReminders();
    expect(container.read(automationProvider).reminderError, 'Error 503');
    expect(container.read(automationProvider).loadingReminders, false);

    shouldThrow = true;
    await notifier.loadReminders();
    expect(container.read(automationProvider).reminderError, 'Cannot reach server.');
  });

  test('createReminder refreshes reminders on success', () async {
    var created = false;
    final client = MockClient((request) async {
      if (request.method == 'POST' && request.url.path == '/api/reminders') {
        created = true;
        return http.Response('{"success":true,"id":5}', 201);
      }
      if (request.method == 'GET' && request.url.path == '/api/reminders') {
        final payload = created
            ? '{"data":[{"id":5,"name":"Paracetamol","dose":"2 tablets","time":"20:00","days":"daily","taken_today":false}],"email_enabled":false}'
            : '{"data":[],"email_enabled":false}';
        return http.Response(payload, 200);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    final error = await container.read(automationProvider.notifier).createReminder(
      name: 'Paracetamol',
      dose: '2 tablets',
      time: '20:00',
      days: 'daily',
    );

    expect(error, isNull);
    expect(container.read(automationProvider).reminders, hasLength(1));
    expect(container.read(automationProvider).reminders.first['id'], 5);
  });

  test('createReminder returns API and network errors', () async {
    var shouldThrow = false;
    final client = MockClient((request) async {
      if (request.method == 'POST' && request.url.path == '/api/reminders') {
        if (shouldThrow) throw http.ClientException('offline');
        return http.Response('{"message":"Name is required"}', 400);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(automationProvider.notifier);

    expect(
      await notifier.createReminder(name: '', dose: '', time: '', days: ''),
      'Name is required',
    );

    shouldThrow = true;
    expect(
      await notifier.createReminder(name: '', dose: '', time: '', days: ''),
      'Network error.',
    );
  });

  test('markReminderTaken toggles taken_today from API response', () async {
    final client = MockClient((request) async {
      if (request.method == 'PATCH' && request.url.path == '/api/reminders/1/taken') {
        return http.Response(
          '{"success":true,"data":{"id":1,"name":"Aspirin","taken_today":true}}',
          200,
        );
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(automationProvider.notifier);
    notifier.state = notifier.state.copyWith(
      reminders: const [
        {'id': 1, 'name': 'Aspirin', 'taken_today': false}
      ],
    );

    await notifier.markReminderTaken(1);
    expect(container.read(automationProvider).reminders.first['taken_today'], true);
  });

  test('markReminderTaken ignores missing reminder and network failures', () async {
    final client = MockClient((request) async {
      throw http.ClientException('offline');
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(automationProvider.notifier);

    await notifier.markReminderTaken(999);
    expect(container.read(automationProvider).reminders, isEmpty);

    notifier.state = notifier.state.copyWith(
      reminders: const [
        {'id': 1, 'name': 'Aspirin', 'taken_today': false}
      ],
    );
    await notifier.markReminderTaken(1);
    expect(container.read(automationProvider).reminders.first['taken_today'], false);
  });

  test('deleteReminder removes item on 200/204, ignores failures', () async {
    var deleteStatus = 204;
    final client = MockClient((request) async {
      if (request.method == 'DELETE' && request.url.path == '/api/reminders/1') {
        return http.Response('', deleteStatus);
      }
      return http.Response('Not found', 404);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(automationProvider.notifier);
    notifier.state = notifier.state.copyWith(
      reminders: const [
        {'id': 1, 'name': 'Aspirin'},
        {'id': 2, 'name': 'Vitamin C'},
      ],
    );

    await notifier.deleteReminder(1);
    expect(container.read(automationProvider).reminders, hasLength(1));
    expect(container.read(automationProvider).reminders.first['id'], 2);

    deleteStatus = 500;
    await notifier.deleteReminder(2);
    expect(container.read(automationProvider).reminders, hasLength(1));
  });
}
