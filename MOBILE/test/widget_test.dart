// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_home_mobile/core/auth_provider.dart';
import 'package:smart_home_mobile/modules/auth/auth_service.dart';
import 'package:smart_home_mobile/screens/login_screen.dart';
import 'package:smart_home_mobile/screens/settings_screen.dart';

class _FakeAuthNotifier extends AuthNotifier {
  _FakeAuthNotifier(super.state) : super.test();

  Map<String, Object?>? lastLogin;
  Map<String, String?>? lastProfileUpdate;

  @override
  Future<void> login({
    required String token,
    required String username,
    int? userId,
    String? email,
  }) async {
    lastLogin = {
      'token': token,
      'username': username,
      'userId': userId,
      'email': email,
    };
    state = AuthState(
      token: token,
      username: username,
      userId: userId,
      email: email,
      isLoading: false,
    );
  }

  @override
  Future<void> updateProfile({String? username, String? email}) async {
    lastProfileUpdate = {
      'username': username,
      'email': email,
    };
    state = AuthState(
      token: state.token,
      username: username ?? state.username,
      userId: state.userId,
      email: email ?? state.email,
      isLoading: false,
    );
  }
}

class _SuccessAuthService extends AuthService {
  _SuccessAuthService({this.payload}) : super(baseUrl: 'http://example.test');

  String? lastIdentity;
  String? lastPassword;
  String? lastResetEmail;
  String? lastResetToken;
  String? lastResetPassword;
  final Map<String, dynamic>? payload;

  @override
  Future<Map<String, dynamic>> login(String identity, String password) async {
    lastIdentity = identity;
    lastPassword = password;
    return payload ?? {
      'token': 'token-123',
      'user': {
        'id': 7,
        'username': 'Demo User',
        'email': 'demo@example.com',
      },
    };
  }

  @override
  Future<Map<String, dynamic>> requestPasswordReset(String email) async {
    lastResetEmail = email;
    return {
      'status': 'success',
      'message': 'Password reset email is unavailable. Use the returned reset token in a trusted environment.',
      'reset_token': 'reset-123',
    };
  }

  @override
  Future<Map<String, dynamic>> resetPassword(String token, String newPassword) async {
    lastResetToken = token;
    lastResetPassword = newPassword;
    return {
      'status': 'success',
      'message': 'Password reset successfully',
    };
  }
}

class _FailingAuthService extends AuthService {
  _FailingAuthService() : super(baseUrl: 'http://example.test');

  @override
  Future<Map<String, dynamic>> login(String identity, String password) async {
    throw const AuthServiceException('Invalid credentials.');
  }
}

class _GenericFailingAuthService extends AuthService {
  _GenericFailingAuthService() : super(baseUrl: 'http://example.test');

  @override
  Future<Map<String, dynamic>> login(String identity, String password) async {
    throw Exception('socket closed');
  }
}

void main() {
  Future<void> pumpLoginScreen(
    WidgetTester tester, {
    AuthService? authService,
    _FakeAuthNotifier? authNotifier,
  }) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          if (authService != null)
            authServiceProvider.overrideWithValue(authService),
          if (authNotifier != null)
            authProvider.overrideWith((_) => authNotifier),
        ],
        child: MaterialApp(
          routes: {
            '/settings': (_) => const SettingsScreen(),
          },
          home: const LoginScreen(),
        ),
      ),
    );
  }

  testWidgets('shows validation error when credentials are empty', (tester) async {
    await pumpLoginScreen(tester);

    await tester.tap(find.byKey(const ValueKey('login.submit')));
    await tester.pump();

    expect(find.text('Please enter username/email and password.'), findsOneWidget);
  });

  testWidgets('shows auth service error message', (tester) async {
    await pumpLoginScreen(tester, authService: _FailingAuthService());

    await tester.enterText(
      find.byKey(const ValueKey('login.identity')),
      'demo@smarthome.local',
    );
    await tester.enterText(
      find.byKey(const ValueKey('login.password')),
      'wrong-password',
    );
    await tester.tap(find.byKey(const ValueKey('login.submit')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Invalid credentials.'), findsOneWidget);
  });

  testWidgets('logs in successfully and stores mapped user fields',
      (tester) async {
    final authService = _SuccessAuthService();
    final authNotifier = _FakeAuthNotifier(const AuthState(isLoading: false));

    await pumpLoginScreen(
      tester,
      authService: authService,
      authNotifier: authNotifier,
    );

    await tester.enterText(
      find.byKey(const ValueKey('login.identity')),
      'demo@smarthome.local',
    );
    await tester.enterText(
      find.byKey(const ValueKey('login.password')),
      'correct-password',
    );
    await tester.tap(find.byKey(const ValueKey('login.submit')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(authService.lastIdentity, 'demo@smarthome.local');
    expect(authService.lastPassword, 'correct-password');
    expect(authNotifier.lastLogin, {
      'token': 'token-123',
      'username': 'Demo User',
      'userId': 7,
      'email': 'demo@example.com',
    });
    expect(find.text('Invalid credentials.'), findsNothing);
  });

  testWidgets('shows fallback network error for unexpected login failures',
      (tester) async {
    await pumpLoginScreen(tester, authService: _GenericFailingAuthService());

    await tester.enterText(
      find.byKey(const ValueKey('login.identity')),
      'demo@smarthome.local',
    );
    await tester.enterText(
      find.byKey(const ValueKey('login.password')),
      'secret',
    );
    await tester.tap(find.byKey(const ValueKey('login.submit')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(
      find.text('Cannot reach server. Check backend URL in Settings.'),
      findsOneWidget,
    );
  });

  testWidgets('toggles password visibility from hidden to visible',
      (tester) async {
    await pumpLoginScreen(tester);

    expect(
      tester.widget<TextField>(find.byKey(const ValueKey('login.password'))).obscureText,
      isTrue,
    );

    await tester.tap(find.byIcon(Icons.visibility_off));
    await tester.pump();

    expect(
      tester.widget<TextField>(find.byKey(const ValueKey('login.password'))).obscureText,
      isFalse,
    );
  });

  testWidgets('shows registration snackbar when register is tapped',
      (tester) async {
    await pumpLoginScreen(tester);

    await tester.tap(find.text('REGISTER'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(
      find.text('Registration is managed by your administrator.'),
      findsOneWidget,
    );
  });

  testWidgets('forgot password dialog can request and submit a reset code',
      (tester) async {
    final authService = _SuccessAuthService();
    await pumpLoginScreen(tester, authService: authService);

    await tester.tap(find.byKey(const ValueKey('login.forgotPassword')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    await tester.enterText(
      find.byKey(const ValueKey('login.forgot.email')),
      'demo@example.com',
    );
    await tester.tap(find.byKey(const ValueKey('login.forgot.sendCode')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(authService.lastResetEmail, 'demo@example.com');
    expect(
      find.text('Email is unavailable in this environment, so the reset code was filled automatically.'),
      findsOneWidget,
    );

    await tester.enterText(
      find.byKey(const ValueKey('login.forgot.newPassword')),
      'NewPassword456',
    );
    await tester.tap(find.byKey(const ValueKey('login.forgot.resetPassword')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(authService.lastResetToken, 'reset-123');
    expect(authService.lastResetPassword, 'NewPassword456');
    expect(find.text('Password reset successfully'), findsOneWidget);
  });

  testWidgets('opens settings screen from configure server url link',
      (tester) async {
    await pumpLoginScreen(tester);

    final settingsLink = find.text('Configure server URL');
    await tester.ensureVisible(settingsLink);
    await tester.tap(settingsLink, warnIfMissed: false);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('SETTINGS'), findsOneWidget);
  });

  testWidgets('falls back to identity email when login response omits email',
      (tester) async {
    final authService = _SuccessAuthService(
      payload: {
        'token': 'token-456',
        'user': {
          'id': 9,
          'username': 'Ops User',
        },
      },
    );
    final authNotifier = _FakeAuthNotifier(const AuthState(isLoading: false));

    await pumpLoginScreen(
      tester,
      authService: authService,
      authNotifier: authNotifier,
    );

    await tester.enterText(
      find.byKey(const ValueKey('login.identity')),
      'ops@example.com',
    );
    await tester.enterText(
      find.byKey(const ValueKey('login.password')),
      'correct-password',
    );
    await tester.tap(find.byKey(const ValueKey('login.submit')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(authNotifier.lastLogin?['email'], 'ops@example.com');
    expect(authNotifier.lastLogin?['username'], 'Ops User');
  });

  testWidgets('falls back to identity when login response user is not an object',
      (tester) async {
    final authService = _SuccessAuthService(
      payload: {
        'token': 'token-789',
        'user': 'unexpected-user-shape',
      },
    );
    final authNotifier = _FakeAuthNotifier(const AuthState(isLoading: false));

    await pumpLoginScreen(
      tester,
      authService: authService,
      authNotifier: authNotifier,
    );

    await tester.enterText(
      find.byKey(const ValueKey('login.identity')),
      'fallback@example.com',
    );
    await tester.enterText(
      find.byKey(const ValueKey('login.password')),
      'correct-password',
    );
    await tester.tap(find.byKey(const ValueKey('login.submit')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(authNotifier.lastLogin?['username'], 'fallback@example.com');
    expect(authNotifier.lastLogin?['email'], 'fallback@example.com');
    expect(authNotifier.lastLogin?['userId'], isNull);
  });

  testWidgets('accepts next action from identity field without validation error',
      (tester) async {
    await pumpLoginScreen(tester);

    await tester.showKeyboard(find.byKey(const ValueKey('login.identity')));
    await tester.pump();
    await tester.testTextInput.receiveAction(TextInputAction.next);
    await tester.pump();

    expect(find.byKey(const ValueKey('login.identity')), findsOneWidget);
    expect(find.byKey(const ValueKey('login.password')), findsOneWidget);
    expect(find.text('Please enter username/email and password.'), findsNothing);
  });

  testWidgets('submits login from password field done action', (tester) async {
    final authService = _SuccessAuthService();
    final authNotifier = _FakeAuthNotifier(const AuthState(isLoading: false));

    await pumpLoginScreen(
      tester,
      authService: authService,
      authNotifier: authNotifier,
    );

    await tester.enterText(
      find.byKey(const ValueKey('login.identity')),
      'demo@smarthome.local',
    );
    await tester.enterText(
      find.byKey(const ValueKey('login.password')),
      'keyboard-submit',
    );
    await tester.showKeyboard(find.byKey(const ValueKey('login.password')));
    await tester.pump();
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(authService.lastPassword, 'keyboard-submit');
    expect(authNotifier.lastLogin?['token'], 'token-123');
  });
}
