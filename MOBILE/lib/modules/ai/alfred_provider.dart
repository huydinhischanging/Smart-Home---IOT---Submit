// lib/modules/ai/alfred_provider.dart
// Riverpod StateNotifier for the Alfred AI chat session.
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/api_headers.dart';
import '../../core/api_context_provider.dart';
import '../../core/http_client_provider.dart';
import '../map/map_provider.dart';

// ── Model ─────────────────────────────────────────────────────
class ChatMessage {
  final String role;     // 'user' | 'assistant'
  final String content;

  const ChatMessage({required this.role, required this.content});

  Map<String, String> toJson() => {'role': role, 'content': content};
}

// ── State ─────────────────────────────────────────────────────
class AlfredState {
  final List<ChatMessage> messages;
  final bool thinking;
  final String? error;

  const AlfredState({
    this.messages = const [],
    this.thinking = false,
    this.error,
  });

  AlfredState copyWith({
    List<ChatMessage>? messages,
    bool? thinking,
    String? error,
  }) =>
      AlfredState(
        messages: messages ?? this.messages,
        thinking: thinking ?? this.thinking,
        error: error,
      );
}

// ── Notifier ──────────────────────────────────────────────────
class AlfredNotifier extends StateNotifier<AlfredState> {
  final Ref _ref;

  AlfredNotifier(this._ref) : super(const AlfredState());

    String get _base => _ref.read(apiBaseUrlProvider);
    http.Client get _client => _ref.read(httpClientProvider);
  Map<String, String> get _headers =>
      apiJsonHeaders(_ref.read(authHeadersProvider));

  /// Send a message to Alfred and append the reply.
  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || state.thinking) return;

    // Append user message immediately
    final withUser = [
      ...state.messages,
      ChatMessage(role: 'user', content: trimmed),
    ];
    state = state.copyWith(messages: withUser, thinking: true, error: null);

    try {
      // Send history excluding the just-appended user message as history
      final history = state.messages
          .take(state.messages.length - 1)
          .map((m) => m.toJson())
          .toList();

      // Get current room from map state if available
      final mapState = _ref.read(mapProvider);
      final requestBody = {
        'message': trimmed,
        'history': history,
        'mode': 'llm',
      };
      
      // Add context if room is selected
      if (mapState.currentRoomId != null || mapState.currentRoomName != null) {
        requestBody['context'] = {
          'owner_room': {
            'id': mapState.currentRoomId,
            'name': mapState.currentRoomName,
          }
        };
      }

      final r = await _client
          .post(
            Uri.parse('$_base/api/ai/chat'),
            headers: _headers,
            body: jsonEncode(requestBody),
          )
          .timeout(const Duration(seconds: 90));

      final d = jsonDecode(r.body) as Map<String, dynamic>;
      final reply =
          d['reply'] ?? d['response'] ?? d['message'] ?? '—';

      state = state.copyWith(
        messages: [
          ...state.messages,
          ChatMessage(role: 'assistant', content: reply.toString()),
        ],
        thinking: false,
      );
    } catch (e) {
      state = state.copyWith(
        messages: [
          ...state.messages,
          ChatMessage(
              role: 'assistant', content: 'Relay failure: ${e.toString()}'),
        ],
        thinking: false,
        error: e.toString(),
      );
    }
  }

  /// Clear conversation history.
  void clear() => state = const AlfredState();
}

// ── Provider ──────────────────────────────────────────────────
final alfredProvider =
    StateNotifierProvider<AlfredNotifier, AlfredState>(
  (ref) => AlfredNotifier(ref),
);
