import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smart_home_mobile/core/api_context_provider.dart';
import 'package:smart_home_mobile/core/http_client_provider.dart';
import 'package:smart_home_mobile/modules/ai/alfred_provider.dart';

ProviderContainer _makeContainer(http.Client client) {
  return ProviderContainer(overrides: [
    apiBaseUrlProvider.overrideWithValue('http://example.test'),
    authHeadersProvider.overrideWithValue(const {'Authorization': 'Bearer token'}),
    httpClientProvider.overrideWithValue(client),
  ]);
}

void main() {
  test('alfred state copyWith and chat message json keep expected values', () {
    const msg = ChatMessage(role: 'user', content: 'status');
    const state = AlfredState(messages: [msg], thinking: true, error: 'old');
    final next = state.copyWith(thinking: false, error: null);
    final replaced = state.copyWith(messages: const [
      ChatMessage(role: 'assistant', content: 'ok')
    ]);

    expect(msg.toJson(), {'role': 'user', 'content': 'status'});
    expect(next.messages, hasLength(1));
    expect(next.thinking, false);
    expect(next.error, isNull);
    expect(replaced.messages.single.role, 'assistant');
  });

  test('alfred provider appends assistant reply on success', () async {
    late Map<String, dynamic> sentBody;
    final client = MockClient(
      (request) async {
        sentBody = {'body': request.body, 'path': request.url.path};
        return http.Response('{"reply":"Systems nominal."}', 200);
      },
    );

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    await container.read(alfredProvider.notifier).send('status');
    final state = container.read(alfredProvider);

    expect(sentBody['path'], '/api/ai/chat');
    expect(sentBody['body'], contains('"message":"status"'));
    expect(sentBody['body'], contains('"history":[]'));
    expect(state.messages, hasLength(2));
    expect(state.messages.first.role, 'user');
    expect(state.messages.last.content, 'Systems nominal.');
    expect(state.thinking, false);
  });

  test('alfred provider records relay failure on client exception', () async {
    final client = MockClient((_) async => throw http.ClientException('offline'));

    final container = _makeContainer(client);
    addTearDown(container.dispose);

    await container.read(alfredProvider.notifier).send('status');
    final state = container.read(alfredProvider);

    expect(state.messages, hasLength(2));
    expect(state.messages.last.content, contains('Relay failure:'));
    expect(state.error, contains('offline'));
    expect(state.thinking, false);
  });

  test('alfred provider ignores blank input and while already thinking', () async {
    var calls = 0;
    final client = MockClient((_) async {
      calls += 1;
      return http.Response('{"reply":"ok"}', 200);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(alfredProvider.notifier);

    await notifier.send('   ');
    notifier.state = notifier.state.copyWith(thinking: true);
    await notifier.send('status');

    expect(calls, 0);
    expect(container.read(alfredProvider).messages, isEmpty);
  });

  test('alfred provider sends prior history and supports response/message fallbacks', () async {
    var call = 0;
    final bodies = <String>[];
    final client = MockClient((request) async {
      call += 1;
      bodies.add(request.body);
      if (call == 1) {
        return http.Response('{"response":"First reply"}', 200);
      }
      return http.Response('{"message":"Second reply"}', 200);
    });

    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(alfredProvider.notifier);

    await notifier.send('status');
    await notifier.send('lights');

    final state = container.read(alfredProvider);
    expect(state.messages, hasLength(4));
    expect(state.messages[1].content, 'First reply');
    expect(state.messages[3].content, 'Second reply');
    expect(bodies.first, contains('"history":[]'));
    expect(bodies.last, contains('"role":"user"'));
    expect(bodies.last, contains('"role":"assistant"'));
  });

  test('alfred provider falls back to dash reply and clear resets conversation', () async {
    final client = MockClient((_) async => http.Response('{"ok":true}', 200));
    final container = _makeContainer(client);
    addTearDown(container.dispose);
    final notifier = container.read(alfredProvider.notifier);

    await notifier.send('status');
    expect(container.read(alfredProvider).messages.last.content, '—');

    notifier.clear();
    final state = container.read(alfredProvider);
    expect(state.messages, isEmpty);
    expect(state.thinking, false);
    expect(state.error, isNull);
  });
}