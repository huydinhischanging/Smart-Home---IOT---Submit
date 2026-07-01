import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_home_mobile/core/auth_provider.dart';

const _storageChannel = MethodChannel('plugins.it_nomads.com/flutter_secure_storage');

Future<void> _flushAuthLoad() async {
  for (var index = 0; index < 6; index += 1) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final storage = <String, String>{};
  var failReads = false;

  setUp(() async {
    storage.clear();
    failReads = false;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_storageChannel, (call) async {
      final arguments = (call.arguments as Map?)?.cast<Object?, Object?>() ?? const {};
      final key = arguments['key']?.toString();

      switch (call.method) {
        case 'read':
          if (failReads) {
            throw PlatformException(code: 'read-failed');
          }
          return key == null ? null : storage[key];
        case 'write':
          if (key != null) {
            storage[key] = arguments['value']?.toString() ?? '';
          }
          return null;
        case 'delete':
          if (key != null) {
            storage.remove(key);
          }
          return null;
        case 'deleteAll':
          storage.clear();
          return null;
        default:
          return null;
      }
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_storageChannel, null);
  });

  test('auth state helpers expose login and bearer information', () {
    const loggedIn = AuthState(token: 'token-123', username: 'demo', isLoading: false);
    const loading = AuthState(token: 'token-123', isLoading: true);
    const loggedOut = AuthState(isLoading: false);

    expect(loggedIn.isLoggedIn, true);
    expect(loggedIn.bearerHeader, {'Authorization': 'Bearer token-123'});
    expect(loading.isLoggedIn, false);
    expect(loggedOut.isLoggedIn, false);
    expect(loggedOut.bearerHeader, isEmpty);
  });

  test('auth provider loads persisted credentials from secure storage', () async {
    storage['auth_token'] = 'token-123';
    storage['auth_username'] = 'demo';
    storage['auth_user_id'] = '7';
    storage['auth_email'] = 'demo@example.com';

    final container = ProviderContainer();
    addTearDown(container.dispose);

    expect(container.read(authProvider).isLoading, true);
    container.read(authProvider.notifier);
    await _flushAuthLoad();

    final state = container.read(authProvider);
    expect(state.token, 'token-123');
    expect(state.username, 'demo');
    expect(state.userId, 7);
    expect(state.email, 'demo@example.com');
    expect(state.isLoading, false);
  });

  test('auth notifier falls back to logged out state when storage read fails', () async {
    failReads = true;
    final notifier = AuthNotifier();
    addTearDown(notifier.dispose);

    await _flushAuthLoad();

    expect(notifier.state.token, isNull);
    expect(notifier.state.username, isNull);
    expect(notifier.state.isLoading, false);
  });

  test('auth notifier login writes all available fields and logout clears them', () async {
    final notifier = AuthNotifier.test(const AuthState(isLoading: false));
    addTearDown(notifier.dispose);

    await notifier.login(
      token: 'token-abc',
      username: 'demo',
      userId: 9,
      email: 'demo@example.com',
    );

    expect(storage['auth_token'], 'token-abc');
    expect(storage['auth_username'], 'demo');
    expect(storage['auth_user_id'], '9');
    expect(storage['auth_email'], 'demo@example.com');
    expect(notifier.state.userId, 9);
    expect(notifier.state.email, 'demo@example.com');
    expect(notifier.state.isLoading, false);

    await notifier.logout();

    expect(storage, isEmpty);
    expect(notifier.state, const AuthState(isLoading: false));
  });

  test('auth notifier login removes optional fields when absent', () async {
    storage['auth_user_id'] = '12';
    storage['auth_email'] = 'old@example.com';
    final notifier = AuthNotifier.test(const AuthState(isLoading: false));
    addTearDown(notifier.dispose);

    await notifier.login(
      token: 'token-xyz',
      username: 'demo',
      email: '',
    );

    expect(storage['auth_token'], 'token-xyz');
    expect(storage['auth_username'], 'demo');
    expect(storage.containsKey('auth_user_id'), false);
    expect(storage.containsKey('auth_email'), false);
    expect(notifier.state.userId, isNull);
    expect(notifier.state.email, '');
  });
}