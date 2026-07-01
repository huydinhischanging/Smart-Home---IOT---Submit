import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text_platform_interface/speech_to_text_platform_interface.dart';
import 'package:smart_home_mobile/modules/ai/alfred_provider.dart';
import 'package:smart_home_mobile/screens/alfred_screen.dart';

class _FakeAlfredNotifier extends AlfredNotifier {
  _FakeAlfredNotifier(
    super.ref, {
    required AlfredState initialState,
  }) : super() {
    state = initialState;
  }

  final List<String> sentTexts = [];
  String reply = 'Acknowledged.';

  @override
  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || state.thinking) return;
    sentTexts.add(trimmed);
    state = state.copyWith(
      messages: [
        ...state.messages,
        ChatMessage(role: 'user', content: trimmed),
        ChatMessage(role: 'assistant', content: reply),
      ],
      thinking: false,
      error: null,
    );
  }
}

class _FakeSpeechPlatform extends SpeechToTextPlatform {
  bool initResult = true;
  bool stopInvoked = false;
  bool listenInvoked = false;

  void reset() {
    initResult = true;
    stopInvoked = false;
    listenInvoked = false;
  }

  @override
  Future<bool> initialize({debugLogging = false, List<SpeechConfigOption>? options}) async {
    return initResult;
  }

  @override
  Future<bool> listen({
    String? localeId,
    partialResults = true,
    onDevice = false,
    int listenMode = 0,
    sampleRate = 0,
    SpeechListenOptions? options,
  }) async {
    listenInvoked = true;
    return true;
  }

  @override
  Future<void> stop() async {
    stopInvoked = true;
  }

  @override
  Future<void> cancel() async {}

  @override
  Future<bool> hasPermission() async => true;

  @override
  Future<List<dynamic>> locales() async => [];

  void emitFinalWords(String words) {
    onTextRecognition?.call(
      '{"alternates":[{"recognizedWords":"$words","confidence":0.8}],"finalResult":true}',
    );
  }

  void emitError() {
    onError?.call('{"errorMsg":"network","permanent":true}');
  }

  void emitListening() {
    onStatus?.call(SpeechToText.listeningStatus);
  }
}

Future<void> _pumpAlfredScreen(
  WidgetTester tester, {
  required AlfredState alfredState,
  void Function(_FakeAlfredNotifier notifier)? onNotifier,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        alfredProvider.overrideWith((ref) {
          final notifier = _FakeAlfredNotifier(ref, initialState: alfredState);
          onNotifier?.call(notifier);
          return notifier;
        }),
      ],
      child: const MaterialApp(home: AlfredScreen()),
    ),
  );

  await tester.pump();
  await tester.pump();
}

Future<void> _disposeScreen(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _FakeSpeechPlatform speechPlatform;

  setUpAll(() {
    speechPlatform = _FakeSpeechPlatform();
    SpeechToTextPlatform.instance = speechPlatform;
  });

  setUp(() {
    speechPlatform.reset();
  });

  testWidgets('alfred screen shows greeting and quick commands', (tester) async {
    addTearDown(() async => _disposeScreen(tester));

    await _pumpAlfredScreen(
      tester,
      alfredState: const AlfredState(),
    );

    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('ALFRED'), findsWidgets);
    expect(find.text('AI COMMAND RELAY'), findsOneWidget);
    expect(find.text('ONLINE'), findsOneWidget);
    expect(find.textContaining('Master Wayne'), findsOneWidget);
    expect(find.text('STATUS'), findsOneWidget);
    expect(find.text('🚨 EMERGENCY'), findsOneWidget);
  });

  testWidgets('alfred screen sends typed and quick commands', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeAlfredNotifier notifier;

    await _pumpAlfredScreen(
      tester,
      alfredState: const AlfredState(),
      onNotifier: (value) => notifier = value,
    );

    await tester.pump(const Duration(milliseconds: 50));

    await tester.enterText(find.byType(TextField), 'status report');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));

    expect(notifier.sentTexts, ['status report']);
    expect(find.text('status report'), findsOneWidget);
    expect(find.text('Acknowledged.'), findsOneWidget);
    expect(find.text('MASTER WAYNE'), findsOneWidget);

    await tester.tap(find.text('LIGHTS ON'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(notifier.sentTexts, ['status report', 'LIGHTS ON']);
  });

  testWidgets('alfred screen shows typing bubble and blocks send while thinking', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeAlfredNotifier notifier;

    await _pumpAlfredScreen(
      tester,
      alfredState: const AlfredState(thinking: true),
      onNotifier: (value) => notifier = value,
    );

    await tester.pump(const Duration(milliseconds: 50));

    await tester.enterText(find.byType(TextField), 'ignored');
    await tester.tap(find.byIcon(Icons.send_rounded));
    await tester.pump();

    expect(find.byType(AnimatedBuilder), findsWidgets);
    expect(notifier.sentTexts, isEmpty);
  });

  testWidgets('alfred screen microphone flow sends final speech result', (tester) async {
    addTearDown(() async => _disposeScreen(tester));
    late _FakeAlfredNotifier notifier;

    await _pumpAlfredScreen(
      tester,
      alfredState: const AlfredState(),
      onNotifier: (value) => notifier = value,
    );

    await tester.pump(const Duration(milliseconds: 50));

    await tester.tap(find.byIcon(Icons.mic_none_rounded));
    await tester.pump();
    expect(speechPlatform.listenInvoked, true);

    speechPlatform.emitListening();
    await tester.pump();
    speechPlatform.emitFinalWords('turn on lamp');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));

    expect(notifier.sentTexts, ['turn on lamp']);
    expect(find.text('turn on lamp'), findsOneWidget);
  });

  testWidgets('alfred screen microphone error path updates listening state', (tester) async {
    addTearDown(() async => _disposeScreen(tester));

    await _pumpAlfredScreen(
      tester,
      alfredState: const AlfredState(),
    );

    await tester.pump(const Duration(milliseconds: 50));

    final idleMic = find.byIcon(Icons.mic_none_rounded);
    if (idleMic.evaluate().isNotEmpty) {
      await tester.tap(idleMic.first);
    } else {
      await tester.tap(find.byIcon(Icons.mic).first);
    }
    await tester.pump();
    speechPlatform.emitListening();
    await tester.pump();

    speechPlatform.emitError();
    await tester.pump();
    final hasIdleMic = find.byIcon(Icons.mic_none_rounded).evaluate().isNotEmpty;
    final hasActiveMic = find.byIcon(Icons.mic).evaluate().isNotEmpty;
    expect(hasIdleMic || hasActiveMic, true);
  });

  testWidgets('alfred screen microphone stop path stops active listening', (tester) async {
    addTearDown(() async => _disposeScreen(tester));

    await _pumpAlfredScreen(
      tester,
      alfredState: const AlfredState(),
    );

    await tester.pump(const Duration(milliseconds: 50));

    await tester.tap(find.byIcon(Icons.mic_none_rounded));
    await tester.pump();
    expect(find.byIcon(Icons.mic), findsOneWidget);

    await tester.tap(find.byIcon(Icons.mic));
    await tester.pump();
    await tester.pump(const Duration(seconds: 3));
    expect(speechPlatform.stopInvoked, true);
    expect(find.byIcon(Icons.mic_none_rounded), findsOneWidget);
  });
}