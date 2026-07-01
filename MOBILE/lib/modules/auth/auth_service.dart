import 'dart:convert';
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/cfg_provider.dart';

class AuthServiceException implements Exception {
  final String message;

  const AuthServiceException(this.message);

  @override
  String toString() => message;
}

class AuthService {
  final String baseUrl;
  final http.Client _client;

  AuthService({
    required this.baseUrl,
    http.Client? client,
  }) : _client = client ?? http.Client();

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, dynamic> body, {
    Map<String, String>? headers,
    String fallbackMessage = 'Request failed',
    String method = 'POST',
  }) async {
    try {
      final uri = Uri.parse('$baseUrl$path');
      final requestHeaders = {
        'Content-Type': 'application/json',
        ...?headers,
      };
      late final http.Response response;
      if (method == 'PATCH') {
        response = await _client
            .patch(
              uri,
              headers: requestHeaders,
              body: jsonEncode(body),
            )
            .timeout(const Duration(seconds: 12));
      } else {
        response = await _client
            .post(
              uri,
              headers: requestHeaders,
              body: jsonEncode(body),
            )
            .timeout(const Duration(seconds: 12));
      }

      final data = _decodeBody(response.body);
      if ((response.statusCode >= 200 && response.statusCode < 300) &&
          (data['status'] == 'success' || !data.containsKey('status'))) {
        return data;
      }
      throw AuthServiceException(
        data['message']?.toString() ?? '$fallbackMessage (${response.statusCode})',
      );
    } on TimeoutException {
      throw const AuthServiceException(
        'Cannot reach server. Check backend URL in Settings.',
      );
    } on http.ClientException {
      throw const AuthServiceException(
        'Cannot reach server. Check backend URL in Settings.',
      );
    } on FormatException {
      throw const AuthServiceException('Server returned an invalid response.');
    }
  }

  Future<Map<String, dynamic>> _deleteJson(
    String path,
    Map<String, dynamic> body, {
    Map<String, String>? headers,
    String fallbackMessage = 'Request failed',
  }) async {
    try {
      final response = await _client
          .delete(
            Uri.parse('$baseUrl$path'),
            headers: {
              'Content-Type': 'application/json',
              ...?headers,
            },
            body: jsonEncode(body),
          )
          .timeout(const Duration(seconds: 12));

      final data = _decodeBody(response.body);
      if ((response.statusCode >= 200 && response.statusCode < 300) &&
          (data['status'] == 'success' || !data.containsKey('status'))) {
        return data;
      }
      throw AuthServiceException(
        data['message']?.toString() ?? '$fallbackMessage (${response.statusCode})',
      );
    } on TimeoutException {
      throw const AuthServiceException(
        'Cannot reach server. Check backend URL in Settings.',
      );
    } on http.ClientException {
      throw const AuthServiceException(
        'Cannot reach server. Check backend URL in Settings.',
      );
    } on FormatException {
      throw const AuthServiceException('Server returned an invalid response.');
    }
  }

  Future<Map<String, dynamic>> login(String identity, String password) async {
    return _postJson(
      '/api/auth/login',
      {'identity': identity, 'password': password},
      fallbackMessage: 'Login failed',
    );
  }

  Future<Map<String, dynamic>> register(
    String username,
    String email,
    String password,
  ) async {
    if (password.length < 8) {
      throw const AuthServiceException('Password must be at least 8 characters.');
    }

    return _postJson(
      '/api/auth/register',
      {
        'username': username,
        'email': email,
        'password': password,
      },
      fallbackMessage: 'Registration failed',
    );
  }

  Future<Map<String, dynamic>> updateUsername(
    String token,
    String newUsername,
    String currentPassword,
  ) {
    return _postJson(
      '/api/auth/profile',
      {
        'new_username': newUsername,
        'current_password': currentPassword,
      },
      headers: {'Authorization': 'Bearer $token'},
      fallbackMessage: 'Username update failed',
      method: 'PATCH',
    );
  }

  Future<Map<String, dynamic>> requestPasswordReset(String email) {
    return _postJson(
      '/api/auth/forgot-password',
      {'email': email},
      fallbackMessage: 'Password reset request failed',
    );
  }

  Future<Map<String, dynamic>> resetPassword(String token, String newPassword) {
    if (newPassword.length < 8) {
      throw const AuthServiceException('Password must be at least 8 characters.');
    }
    return _postJson(
      '/api/auth/reset-password',
      {
        'token': token,
        'new_password': newPassword,
      },
      fallbackMessage: 'Password reset failed',
    );
  }

  Future<Map<String, dynamic>> deleteAccount(String token, String currentPassword) {
    return _deleteJson(
      '/api/auth/account',
      {'current_password': currentPassword},
      headers: {'Authorization': 'Bearer $token'},
      fallbackMessage: 'Account cancellation failed',
    );
  }

  Map<String, dynamic> _decodeBody(String body) {
    final decoded = jsonDecode(body);
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    throw const FormatException('Expected a JSON object response.');
  }
}

final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(baseUrl: ref.watch(cfgProvider));
});
