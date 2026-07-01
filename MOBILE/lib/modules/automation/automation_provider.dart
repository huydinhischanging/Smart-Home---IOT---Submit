import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/api_headers.dart';
import '../../core/api_context_provider.dart';
import '../../core/http_client_provider.dart';

class AutomationState {
  final List<Map<String, dynamic>> reminders;
  final bool loadingReminders;
  final String? reminderError;
  final bool emailEnabled;

  const AutomationState({
    this.reminders = const [],
    this.loadingReminders = false,
    this.reminderError,
    this.emailEnabled = false,
  });

  AutomationState copyWith({
    List<Map<String, dynamic>>? reminders,
    bool? loadingReminders,
    String? reminderError,
    bool? emailEnabled,
  }) =>
      AutomationState(
        reminders: reminders ?? this.reminders,
        loadingReminders: loadingReminders ?? this.loadingReminders,
        reminderError: reminderError,
        emailEnabled: emailEnabled ?? this.emailEnabled,
      );
}

class AutomationNotifier extends StateNotifier<AutomationState> {
  final Ref _ref;

  AutomationNotifier(this._ref) : super(const AutomationState());

  String get _base => _ref.read(apiBaseUrlProvider);
  http.Client get _client => _ref.read(httpClientProvider);
  Map<String, String> get _headers =>
      apiJsonHeaders(_ref.read(authHeadersProvider));

  Future<void> loadAll() => loadReminders();

  Future<void> loadReminders() async {
    state = state.copyWith(loadingReminders: true, reminderError: null);
    try {
      final r = await _client
          .get(Uri.parse('$_base/api/reminders'), headers: _headers)
          .timeout(const Duration(seconds: 10));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body) as Map<String, dynamic>;
        final raw = (d['data'] as List?)?.cast<Map<String, dynamic>>() ?? [];
        state = state.copyWith(
          reminders: raw,
          loadingReminders: false,
          reminderError: null,
          emailEnabled: d['email_enabled'] == true,
        );
      } else {
        state = state.copyWith(
          loadingReminders: false,
          reminderError: 'Error ${r.statusCode}',
        );
      }
    } catch (_) {
      state = state.copyWith(
        loadingReminders: false,
        reminderError: 'Cannot reach server.',
      );
    }
  }

  Future<String?> createReminder({
    required String name,
    required String dose,
    required String time,
    required String days,
  }) async {
    try {
      final r = await _client
          .post(
            Uri.parse('$_base/api/reminders'),
            headers: _headers,
            body: jsonEncode({'name': name, 'dose': dose, 'time': time, 'days': days}),
          )
          .timeout(const Duration(seconds: 10));
      if (r.statusCode == 201) {
        await loadReminders();
        return null;
      }
      final d = jsonDecode(r.body) as Map<String, dynamic>;
      return d['message']?.toString() ?? 'Error ${r.statusCode}';
    } catch (_) {
      return 'Network error.';
    }
  }

  Future<void> markReminderTaken(int id) async {
    final current = state.reminders.firstWhere(
      (r) => r['id'] == id,
      orElse: () => {},
    );
    if (current.isEmpty) return;
    final nowTaken = !(current['taken_today'] == true);
    try {
      final r = await _client
          .patch(
            Uri.parse('$_base/api/reminders/$id/taken'),
            headers: _headers,
            body: jsonEncode({'taken': nowTaken}),
          )
          .timeout(const Duration(seconds: 6));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body) as Map<String, dynamic>;
        state = state.copyWith(
          reminders: state.reminders
              .map((item) =>
                  item['id'] == id ? (d['data'] as Map<String, dynamic>) : item)
              .toList(),
        );
      }
    } catch (_) {}
  }

  Future<void> deleteReminder(int id) async {
    try {
      final r = await _client
          .delete(Uri.parse('$_base/api/reminders/$id'), headers: _headers)
          .timeout(const Duration(seconds: 6));
      if (r.statusCode == 200 || r.statusCode == 204) {
        state = state.copyWith(
          reminders: state.reminders.where((item) => item['id'] != id).toList(),
        );
      }
    } catch (_) {}
  }
}

final automationProvider =
    StateNotifierProvider<AutomationNotifier, AutomationState>(
  (ref) => AutomationNotifier(ref),
);