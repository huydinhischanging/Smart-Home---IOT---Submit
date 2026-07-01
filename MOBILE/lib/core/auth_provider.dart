import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _kToken = 'auth_token';
const _kUsername = 'auth_username';
const _kUserId = 'auth_user_id';
const _kEmail = 'auth_email';

class AuthState {
  final String? token;
  final String? username;
  final int? userId;
  final String? email;
  final String? role;
  final DateTime? tokenExpiry;
  final bool isLoading;

  const AuthState({
    this.token,
    this.username,
    this.userId,
    this.email,
    this.role,
    this.tokenExpiry,
    this.isLoading = true,
  });

  bool get isTokenExpired {
    final exp = tokenExpiry;
    if (exp == null) return false;
    return DateTime.now().isAfter(exp);
  }

  bool get isLoggedIn =>
      token != null && token!.isNotEmpty && !isLoading && !isTokenExpired;

  Map<String, String> get bearerHeader =>
      isLoggedIn ? {'Authorization': 'Bearer $token'} : {};
}

class AuthNotifier extends StateNotifier<AuthState> {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  AuthNotifier() : super(const AuthState()) {
    _load();
  }

  AuthNotifier.test(super.initialState);

  static Map<String, dynamic>? _decodeJwtPayload(String token) {
    final parts = token.split('.');
    if (parts.length < 2) return null;
    try {
      final normalized = base64Url.normalize(parts[1]);
      final decoded = utf8.decode(base64Url.decode(normalized));
      final parsed = jsonDecode(decoded);
      return parsed is Map<String, dynamic> ? parsed : null;
    } catch (_) {
      return null;
    }
  }

  static DateTime? _extractTokenExpiry(Map<String, dynamic>? payload) {
    final exp = payload?['exp'];
    final seconds = exp is num ? exp.toInt() : int.tryParse('${exp ?? ''}');
    if (seconds == null) return null;
    return DateTime.fromMillisecondsSinceEpoch(seconds * 1000, isUtc: true)
        .toLocal();
  }

  static String? _extractRole(Map<String, dynamic>? payload) {
    if (payload == null) return null;
    final role = payload['role'] ?? payload['user_role'] ?? payload['scope'];
    final roleStr = role?.toString().trim();
    return (roleStr == null || roleStr.isEmpty) ? null : roleStr;
  }

  Future<void> _load() async {
    try {
      final token = await _storage.read(key: _kToken);
      final username = await _storage.read(key: _kUsername);
      final uidStr = await _storage.read(key: _kUserId);
      final email = await _storage.read(key: _kEmail);
      final payload = token != null ? _decodeJwtPayload(token) : null;
      final tokenExpiry = _extractTokenExpiry(payload);
      final role = _extractRole(payload);

      if (token != null && tokenExpiry != null && DateTime.now().isAfter(tokenExpiry)) {
        await logout();
        return;
      }

      state = AuthState(
        token: token,
        username: username,
        userId: uidStr != null ? int.tryParse(uidStr) : null,
        email: email,
        role: role,
        tokenExpiry: tokenExpiry,
        isLoading: false,
      );
    } catch (_) {
      state = const AuthState(isLoading: false);
    }
  }

  Future<void> login({
    required String token,
    required String username,
    int? userId,
    String? email,
  }) async {
    await _storage.write(key: _kToken, value: token);
    await _storage.write(key: _kUsername, value: username);
    if (userId != null) {
      await _storage.write(key: _kUserId, value: userId.toString());
    } else {
      await _storage.delete(key: _kUserId);
    }
    if (email != null && email.isNotEmpty) {
      await _storage.write(key: _kEmail, value: email);
    } else {
      await _storage.delete(key: _kEmail);
    }
    final payload = _decodeJwtPayload(token);
    state = AuthState(
      token: token,
      username: username,
      userId: userId,
      email: email,
      role: _extractRole(payload),
      tokenExpiry: _extractTokenExpiry(payload),
      isLoading: false,
    );
  }

  Future<void> updateProfile({String? username, String? email}) async {
    final nextUsername = username ?? state.username;
    final nextEmail = email ?? state.email;
    if (username != null) {
      await _storage.write(key: _kUsername, value: username);
    }
    if (email != null && email.isNotEmpty) {
      await _storage.write(key: _kEmail, value: email);
    }
    state = AuthState(
      token: state.token,
      username: nextUsername,
      userId: state.userId,
      email: nextEmail,
      role: state.role,
      tokenExpiry: state.tokenExpiry,
      isLoading: false,
    );
  }

  Future<void> logout() async {
    await _storage.deleteAll();
    state = const AuthState(isLoading: false);
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (_) => AuthNotifier(),
);
