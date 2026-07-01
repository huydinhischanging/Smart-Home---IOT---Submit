import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_home_mobile/core/cfg_provider.dart';
import 'package:smart_home_mobile/modules/auth/auth_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('auth service exception toString returns message', () {
    const error = AuthServiceException('Login exploded');

    expect(error.toString(), 'Login exploded');
  });

  test('login returns parsed payload on success', () async {
    final service = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((request) async {
        expect(request.url.toString(), 'http://example.test/api/auth/login');
        expect(request.headers['Content-Type'], 'application/json');
        expect(request.body, '{"identity":"demo","password":"secret"}');
        return http.Response(
          '{"status":"success","token":"abc","user":{"id":7,"username":"demo"}}',
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );

    final result = await service.login('demo', 'secret');

    expect(result['token'], 'abc');
    expect((result['user'] as Map<String, dynamic>)['username'], 'demo');
  });

  test('login surfaces backend message on failure', () async {
    final service = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient(
        (_) async => http.Response('{"message":"Invalid credentials."}', 401),
      ),
    );

    expect(
      () => service.login('demo', 'bad-pass'),
      throwsA(
        isA<AuthServiceException>().having(
          (error) => error.message,
          'message',
          'Invalid credentials.',
        ),
      ),
    );
  });

  test('login uses fallback message when backend omits message', () async {
    final service = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((_) async => http.Response('{"status":"error"}', 500)),
    );

    await expectLater(
      service.login('demo', 'bad-pass'),
      throwsA(
        isA<AuthServiceException>().having(
          (error) => error.message,
          'message',
          'Login failed (500)',
        ),
      ),
    );
  });

  test('login maps timeout and client errors to server unreachable message', () async {
    final timeoutService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((_) => Future<http.Response>.error(TimeoutException('late'))),
    );
    final offlineService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((_) async => throw http.ClientException('offline')),
    );

    for (final future in [
      timeoutService.login('demo', 'secret'),
      offlineService.login('demo', 'secret'),
    ]) {
      await expectLater(
        future,
        throwsA(
          isA<AuthServiceException>().having(
            (error) => error.message,
            'message',
            'Cannot reach server. Check backend URL in Settings.',
          ),
        ),
      );
    }
  });

  test('login maps invalid JSON responses to invalid response message', () async {
    final invalidJsonService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((_) async => http.Response('not-json', 200)),
    );
    final listJsonService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((_) async => http.Response('[]', 200)),
    );

    for (final future in [
      invalidJsonService.login('demo', 'secret'),
      listJsonService.login('demo', 'secret'),
    ]) {
      await expectLater(
        future,
        throwsA(
          isA<AuthServiceException>().having(
            (error) => error.message,
            'message',
            'Server returned an invalid response.',
          ),
        ),
      );
    }
  });

  test('register rejects short passwords before network', () async {
    final service = AuthService(baseUrl: 'http://example.test');

    expect(
      () => service.register('demo', 'demo@example.test', 'short'),
      throwsA(
        isA<AuthServiceException>().having(
          (error) => error.message,
          'message',
          'Password must be at least 8 characters.',
        ),
      ),
    );
  });

  test('register returns parsed payload on success for 201', () async {
    final service = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((request) async {
        expect(request.url.toString(), 'http://example.test/api/auth/register');
        expect(request.headers['Content-Type'], 'application/json');
        expect(
          request.body,
          '{"username":"demo","email":"demo@example.test","password":"long-secret"}',
        );
        return http.Response(
          '{"status":"success","message":"Registered","user":{"id":8}}',
          201,
        );
      }),
    );

    final result = await service.register('demo', 'demo@example.test', 'long-secret');

    expect(result['message'], 'Registered');
    expect((result['user'] as Map<String, dynamic>)['id'], 8);
  });

  test('register surfaces backend message and fallback message on failure', () async {
    final messageService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient(
        (_) async => http.Response('{"message":"Email already used."}', 409),
      ),
    );
    final fallbackService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((_) async => http.Response('{"status":"error"}', 500)),
    );

    await expectLater(
      messageService.register('demo', 'demo@example.test', 'long-secret'),
      throwsA(
        isA<AuthServiceException>().having(
          (error) => error.message,
          'message',
          'Email already used.',
        ),
      ),
    );

    await expectLater(
      fallbackService.register('demo', 'demo@example.test', 'long-secret'),
      throwsA(
        isA<AuthServiceException>().having(
          (error) => error.message,
          'message',
          'Registration failed (500)',
        ),
      ),
    );
  });

  test('register maps timeout client and invalid format errors', () async {
    final timeoutService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((_) => Future<http.Response>.error(TimeoutException('late'))),
    );
    final offlineService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((_) async => throw http.ClientException('offline')),
    );
    final invalidJsonService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((_) async => http.Response('oops', 200)),
    );

    for (final future in [
      timeoutService.register('demo', 'demo@example.test', 'long-secret'),
      offlineService.register('demo', 'demo@example.test', 'long-secret'),
    ]) {
      await expectLater(
        future,
        throwsA(
          isA<AuthServiceException>().having(
            (error) => error.message,
            'message',
            'Cannot reach server. Check backend URL in Settings.',
          ),
        ),
      );
    }

    await expectLater(
      invalidJsonService.register('demo', 'demo@example.test', 'long-secret'),
      throwsA(
        isA<AuthServiceException>().having(
          (error) => error.message,
          'message',
          'Server returned an invalid response.',
        ),
      ),
    );
  });

  test('update username uses patch and returns parsed payload', () async {
    final service = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((request) async {
        expect(request.method, 'PATCH');
        expect(request.url.toString(), 'http://example.test/api/auth/profile');
        expect(request.headers['Authorization'], 'Bearer token-123');
        expect(
          request.body,
          '{"new_username":"batman-user","current_password":"Password123"}',
        );
        return http.Response(
          '{"status":"success","user":{"username":"batman-user","email":"demo@example.test"}}',
          200,
        );
      }),
    );

    final result = await service.updateUsername(
      'token-123',
      'batman-user',
      'Password123',
    );

    expect((result['user'] as Map<String, dynamic>)['username'], 'batman-user');
  });

  test('request password reset returns fallback token payload on success', () async {
    final service = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.toString(), 'http://example.test/api/auth/forgot-password');
        expect(request.body, '{"email":"demo@example.test"}');
        return http.Response(
          '{"status":"success","message":"Password reset email is unavailable.","reset_token":"reset-123"}',
          200,
        );
      }),
    );

    final result = await service.requestPasswordReset('demo@example.test');

    expect(result['reset_token'], 'reset-123');
  });

  test('reset password validates minimum length before network', () async {
    final service = AuthService(baseUrl: 'http://example.test');

    expect(
      () => service.resetPassword('reset-123', 'short'),
      throwsA(
        isA<AuthServiceException>().having(
          (error) => error.message,
          'message',
          'Password must be at least 8 characters.',
        ),
      ),
    );
  });

  test('reset password and delete account surface backend messages', () async {
    final resetService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((request) async {
        expect(request.url.toString(), 'http://example.test/api/auth/reset-password');
        return http.Response('{"message":"Reset token expired"}', 401);
      }),
    );
    final deleteService = AuthService(
      baseUrl: 'http://example.test',
      client: MockClient((request) async {
        expect(request.method, 'DELETE');
        expect(request.url.toString(), 'http://example.test/api/auth/account');
        return http.Response('{"status":"success","message":"Account cancelled successfully"}', 200);
      }),
    );

    await expectLater(
      resetService.resetPassword('reset-123', 'long-secret'),
      throwsA(
        isA<AuthServiceException>().having(
          (error) => error.message,
          'message',
          'Reset token expired',
        ),
      ),
    );

    final deleteResult = await deleteService.deleteAccount('token-123', 'Password123');
    expect(deleteResult['message'], 'Account cancelled successfully');
  });

  test('auth service provider uses cfgProvider base url', () {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer(
      overrides: [cfgProvider.overrideWith((_) => _FakeCfgNotifier('http://demo.local'))],
    );
    addTearDown(container.dispose);

    final service = container.read(authServiceProvider);

    expect(service.baseUrl, 'http://demo.local');
  });
}

class _FakeCfgNotifier extends CfgNotifier {
  _FakeCfgNotifier(String initialState) : super() {
    state = initialState;
  }
}