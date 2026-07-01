import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/api_context_provider.dart';
import '../../core/api_headers.dart';
import '../../core/http_client_provider.dart';

class ReportEmailException implements Exception {
  final String message;

  const ReportEmailException(this.message);

  @override
  String toString() => message;
}

class ReportEmailResult {
  final String message;
  final String? filename;
  final List<String> recipients;

  const ReportEmailResult({
    required this.message,
    this.filename,
    this.recipients = const [],
  });
}

class ReportEmailState {
  final bool sending;
  final String? error;

  const ReportEmailState({
    this.sending = false,
    this.error,
  });

  ReportEmailState copyWith({
    bool? sending,
    String? error,
  }) {
    return ReportEmailState(
      sending: sending ?? this.sending,
      error: error,
    );
  }
}

class ReportEmailNotifier extends StateNotifier<ReportEmailState> {
  final Ref _ref;

  ReportEmailNotifier(this._ref) : super(const ReportEmailState());

  String get _base => _ref.read(apiBaseUrlProvider);
  http.Client get _client => _ref.read(httpClientProvider);
  Map<String, String> get _headers =>
      apiJsonHeaders(_ref.read(authHeadersProvider));

  Future<ReportEmailResult> sendToAccountEmail() async {
    state = const ReportEmailState(sending: true);
    try {
      final response = await _client
          .post(
            Uri.parse('$_base/api/patient/report/email'),
            headers: _headers,
            body: jsonEncode(const <String, dynamic>{}),
          )
          .timeout(const Duration(seconds: 20));

      final payload = _decodeBody(response.body);
      final message = payload['message']?.toString() ?? 'Request failed.';
      if (response.statusCode != 200) {
        throw ReportEmailException(message);
      }

      final delivery = payload['delivery'];
      final recipients = delivery is Map<String, dynamic>
          ? ((delivery['recipients'] as List?) ?? const [])
              .map((item) => item.toString())
              .toList()
          : const <String>[];

      state = const ReportEmailState(sending: false);
      return ReportEmailResult(
        message: message,
        filename: payload['filename']?.toString(),
        recipients: recipients,
      );
    } catch (error) {
      final message = error is ReportEmailException
          ? error.message
          : 'Cannot send report email right now.';
      state = ReportEmailState(sending: false, error: message);
      throw ReportEmailException(message);
    }
  }

  Map<String, dynamic> _decodeBody(String body) {
    if (body.isEmpty) {
      return const <String, dynamic>{};
    }
    final decoded = jsonDecode(body);
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    return const <String, dynamic>{};
  }
}

final reportEmailProvider =
    StateNotifierProvider<ReportEmailNotifier, ReportEmailState>(
  (ref) => ReportEmailNotifier(ref),
);
