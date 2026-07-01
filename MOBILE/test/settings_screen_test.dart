
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_home_mobile/core/bc.dart';
import 'package:smart_home_mobile/core/auth_provider.dart';
import 'package:smart_home_mobile/core/cfg_provider.dart';
import 'package:smart_home_mobile/modules/report/report_email_provider.dart';
import 'package:smart_home_mobile/modules/auth/auth_service.dart';
import 'package:smart_home_mobile/screens/settings_screen.dart';

class _FakeAuthNotifier extends AuthNotifier {
  _FakeAuthNotifier(super.state, {this.onLogout}) : super.test();

  final VoidCallback? onLogout;
  Map<String, String?>? lastProfileUpdate;

  @override
  Future<void> login({
    required String token,
    required String username,
    int? userId,
    String? email,
  }) async {
    state = AuthState(
      token: token,
      username: username,
      userId: userId,
      email: email,
      isLoading: false,
    );
  }

  @override
  Future<void> logout() async {
    onLogout?.call();
    state = const AuthState(isLoading: false);
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

class _FakeAuthService extends AuthService {
  _FakeAuthService() : super(baseUrl: 'http://example.test');

  @override
  Future<Map<String, dynamic>> updateUsername(
    String token,
    String newUsername,
    String currentPassword,
  ) async {
    return {
      'status': 'success',
      'message': 'Username updated successfully',
      'user': {
        'username': newUsername,
        'email': 'demo@example.com',
      },
    };
  }

  @override
  Future<Map<String, dynamic>> deleteAccount(
      String token, String currentPassword) async {
    return {
      'status': 'success',
      'message': 'Account cancelled successfully',
    };
  }
}

class _FakeReportEmailNotifier extends ReportEmailNotifier {
  _FakeReportEmailNotifier(
    super.ref,
    ReportEmailState initialState, {
    this.onSend,
  }) : super() {
    state = initialState;
  }

  final Future<ReportEmailResult> Function()? onSend;

  @override
  Future<ReportEmailResult> sendToAccountEmail() async {
    if (onSend != null) {
      return onSend!();
    }
    return const ReportEmailResult(
      message: 'Report sent',
      recipients: ['demo@example.com'],
    );
  }
}

class _FakeCfgNotifier extends CfgNotifier {
  _FakeCfgNotifier(
    String initialState, {
    this.onSetBase,
    this.onReset,
  }) : super() {
    state = initialState;
  }

  final Future<void> Function(String url)? onSetBase;
  final Future<void> Function()? onReset;

  void pushState(String url) {
    state = sanitizeBaseUrl(url);
  }

  @override
  Future<void> setBase(String url) async {
    if (onSetBase != null) {
      await onSetBase!(url);
      return;
    }
    state = sanitizeBaseUrl(url);
  }

  @override
  Future<void> reset() async {
    if (onReset != null) {
      await onReset!();
      return;
    }
    state = kDefaultBaseUrl;
  }
}

Future<void> _pumpSettingsScreen(
  WidgetTester tester, {
  AuthState authState = const AuthState(isLoading: false),
  ReportEmailState reportEmailState = const ReportEmailState(),
  Future<ReportEmailResult> Function()? onSendReport,
  VoidCallback? onLogout,
  Map<String, Object> initialPrefs = const {},
  Future<void> Function(String url)? onSetBase,
  Future<void> Function()? onResetBase,
  String? cfgState,
  AuthService? authService,
  _FakeAuthNotifier? authNotifier,
  _FakeCfgNotifier? cfgNotifier,
}) async {
  SharedPreferences.setMockInitialValues(initialPrefs);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authProvider.overrideWith(
          (_) =>
              authNotifier ?? _FakeAuthNotifier(authState, onLogout: onLogout),
        ),
        cfgProvider.overrideWith(
          (_) => cfgNotifier ??
              _FakeCfgNotifier(
                cfgState ?? kDefaultBaseUrl,
                onSetBase: onSetBase,
                onReset: onResetBase,
              ),
        ),
        if (authService != null)
          authServiceProvider.overrideWithValue(authService),
        reportEmailProvider.overrideWith(
          (ref) => _FakeReportEmailNotifier(
            ref,
            reportEmailState,
            onSend: onSendReport,
          ),
        ),
      ],
      child: const MaterialApp(home: SettingsScreen()),
    ),
  );

  await tester.pump();
}

Future<void> _scrollToReportSection(WidgetTester tester) async {
  await tester.scrollUntilVisible(
    find.byKey(const ValueKey('settings.sendReportButton')),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump();
}

Future<void> _scrollToQuickSelectSection(WidgetTester tester) async {
  await tester.scrollUntilVisible(
    find.text('Desktop Localhost'),
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump();
}

Future<void> _scrollToServerUrlField(WidgetTester tester) async {
  await tester.scrollUntilVisible(
    find.text('SERVER URL'),
    -200,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump();
}

Future<void> _scrollToAppearanceSection(WidgetTester tester) async {
  await tester.scrollUntilVisible(
    find.text('SYSTEM MOOD'),
    250,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump();
}

Future<void> _scrollToLoggedOutState(WidgetTester tester) async {
  await tester.scrollUntilVisible(
    find.text('Not logged in.'),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump();
}

Future<void> _scrollToSignOutAction(WidgetTester tester) async {
  await tester.scrollUntilVisible(
    find.byKey(const ValueKey('settings.notificationEmail')),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump();
}

void main() {
  testWidgets('settings screen shows current notification email',
      (tester) async {
    await _pumpSettingsScreen(
      tester,
      authState: const AuthState(
        token: 'token',
        username: 'Demo User',
        email: 'demo@example.com',
        isLoading: false,
      ),
    );

    await _scrollToReportSection(tester);
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey('settings.notificationEmail')),
      findsOneWidget,
    );
    expect(find.text('demo@example.com'), findsOneWidget);
    expect(
      find.byKey(const ValueKey('settings.sendReportButton')),
      findsOneWidget,
    );
    expect(find.text('EMAIL MY LATEST REPORT'), findsOneWidget);
  });

  testWidgets('settings screen shows logged out state without report actions',
      (tester) async {
    await _pumpSettingsScreen(tester);

    await _scrollToLoggedOutState(tester);

    expect(find.text('Not logged in.'), findsOneWidget);
    expect(find.text('Log in to access health data.'), findsOneWidget);
    expect(
      find.byKey(const ValueKey('settings.sendReportButton')),
      findsNothing,
    );
  });

  testWidgets('settings screen disables report button while sending',
      (tester) async {
    await _pumpSettingsScreen(
      tester,
      authState: const AuthState(
        token: 'token',
        username: 'Demo User',
        email: 'demo@example.com',
        isLoading: false,
      ),
      reportEmailState: const ReportEmailState(sending: true),
    );

    await _scrollToReportSection(tester);

    final button = tester.widget<ElevatedButton>(
      find.byKey(const ValueKey('settings.sendReportButton')),
    );
    expect(button.onPressed, isNull);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('settings screen shows snackbar after sending report email',
      (tester) async {
    await _pumpSettingsScreen(
      tester,
      authState: const AuthState(
        token: 'token',
        username: 'Demo User',
        email: 'demo@example.com',
        isLoading: false,
      ),
      onSendReport: () async => const ReportEmailResult(
        message: 'Report queued',
        recipients: ['demo@example.com'],
      ),
    );

    await _scrollToReportSection(tester);
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('settings.sendReportButton')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Report sent to demo@example.com'), findsOneWidget);
  });

  testWidgets('settings screen updates username from account dialog',
      (tester) async {
    final authNotifier = _FakeAuthNotifier(
      const AuthState(
        token: 'token',
        username: 'Demo User',
        email: 'demo@example.com',
        isLoading: false,
      ),
    );
    await _pumpSettingsScreen(
      tester,
      authState: authNotifier.state,
      authNotifier: authNotifier,
      authService: _FakeAuthService(),
    );

    await _scrollToSignOutAction(tester);
    await tester
        .tap(find.byKey(const ValueKey('settings.changeUsername.button')));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const ValueKey('settings.changeUsername.username')),
      'NightWatch',
    );
    await tester.enterText(
      find.byKey(const ValueKey('settings.changeUsername.password')),
      'Password123',
    );
    await tester
        .tap(find.byKey(const ValueKey('settings.changeUsername.submit')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(authNotifier.lastProfileUpdate?['username'], 'NightWatch');
    expect(find.text('Username updated successfully'), findsOneWidget);
    expect(authNotifier.state.username, 'NightWatch');
  });

  testWidgets('settings screen cancels account and logs the user out',
      (tester) async {
    var didLogout = false;
    await _pumpSettingsScreen(
      tester,
      authState: const AuthState(
        token: 'token',
        username: 'Demo User',
        email: 'demo@example.com',
        isLoading: false,
      ),
      onLogout: () => didLogout = true,
      authService: _FakeAuthService(),
    );

    await _scrollToSignOutAction(tester);
    await tester
        .tap(find.byKey(const ValueKey('settings.deleteAccount.button')));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const ValueKey('settings.deleteAccount.password')),
      'Password123',
    );
    await tester
        .tap(find.byKey(const ValueKey('settings.deleteAccount.submit')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(didLogout, isTrue);
    expect(find.text('Account cancelled successfully'), findsOneWidget);
  });

  testWidgets(
      'settings screen saves server url and shows updated current value',
      (tester) async {
    await _pumpSettingsScreen(tester);

    await tester.enterText(
      find.byType(TextField),
      'https://192.168.1.20:5000/',
    );
    await tester.tap(find.text('SAVE'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Server URL saved.'), findsOneWidget);
    expect(find.text('Current: https://192.168.1.20:5000'), findsOneWidget);
  });

  testWidgets('settings screen reset restores default backend url',
      (tester) async {
    await _pumpSettingsScreen(
      tester,
      cfgState: 'https://192.168.1.20:5000',
    );

    await tester.pump();
    await tester.tap(find.text('RESET'));
    await tester.pumpAndSettle();

    expect(find.text('Current: http://192.168.1.3:5000'), findsOneWidget);
  });

  testWidgets('settings screen shows snackbar when server url validation fails',
      (tester) async {
    await _pumpSettingsScreen(
      tester,
      onSetBase: (_) async {
        throw const FormatException(
          'Use HTTPS for public backends. In dev, HTTP is allowed for localhost, emulator hosts, private LAN IPs (10.x, 172.16-31.x, 192.168.x), and local hostnames (.local/.lan).',
        );
      },
    );

    await tester.enterText(find.byType(TextField), 'http://bad-host:5000');
    await tester.tap(find.text('SAVE'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(
      find.text(
        'Use HTTPS for public backends. In dev, HTTP is allowed for localhost, emulator hosts, private LAN IPs (10.x, 172.16-31.x, 192.168.x), and local hostnames (.local/.lan).',
      ),
      findsOneWidget,
    );
  });

  testWidgets('settings screen quick select fills server url field',
      (tester) async {
    await _pumpSettingsScreen(tester);

    await _scrollToQuickSelectSection(tester);
    await tester.tap(find.text('Desktop Localhost'));
    await tester.pump();
    await _scrollToServerUrlField(tester);

    final textField = tester.widget<TextField>(find.byType(TextField).first);
    expect(textField.controller?.text, 'http://127.0.0.1:5000');
  });

  testWidgets('settings screen keeps URL field synced with cfg provider state',
      (tester) async {
    final cfgNotifier = _FakeCfgNotifier('http://10.0.2.2:5000');

    await _pumpSettingsScreen(
      tester,
      cfgNotifier: cfgNotifier,
    );

    cfgNotifier.pushState('https://staging.example.com');
    await tester.pump();

    final textField = tester.widget<TextField>(find.byType(TextField).first);
    expect(textField.controller?.text, 'https://staging.example.com');
    expect(find.text('Current: https://staging.example.com'), findsOneWidget);
  });

  testWidgets('settings screen quick select exposes https staging preset',
      (tester) async {
    await _pumpSettingsScreen(tester);

    await _scrollToQuickSelectSection(tester);
    await tester.tap(find.text('HTTPS Staging'));
    await tester.pump();
    await _scrollToServerUrlField(tester);

    final textField = tester.widget<TextField>(find.byType(TextField).first);
    expect(textField.controller?.text, 'https://staging.example.com');
  });

  testWidgets('settings screen changes system mood when a mood chip is tapped',
      (tester) async {
    await _pumpSettingsScreen(tester);

    await _scrollToAppearanceSection(tester);
    expect(find.text(AppMood.normal.label), findsWidgets);

    await tester.tap(find.text(AppMood.emergency.label));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));

    expect(find.text(AppMood.emergency.label), findsWidgets);
    expect(find.text(AppMood.emergency.emoji), findsWidgets);
  });

  testWidgets('settings screen shows inline report error from provider state',
      (tester) async {
    await _pumpSettingsScreen(
      tester,
      authState: const AuthState(
        token: 'token',
        username: 'Demo User',
        email: 'demo@example.com',
        isLoading: false,
      ),
      reportEmailState: const ReportEmailState(error: 'Queued delivery failed'),
    );

    await _scrollToReportSection(tester);

    expect(find.text('Queued delivery failed'), findsOneWidget);
  });

  testWidgets('settings screen shows snackbar when report email fails',
      (tester) async {
    await _pumpSettingsScreen(
      tester,
      authState: const AuthState(
        token: 'token',
        username: 'Demo User',
        email: 'demo@example.com',
        isLoading: false,
      ),
      onSendReport: () async {
        throw const ReportEmailException('Mailer offline');
      },
    );

    await _scrollToReportSection(tester);

    await tester.tap(find.byKey(const ValueKey('settings.sendReportButton')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Mailer offline'), findsOneWidget);
  });

  testWidgets('settings screen falls back to generic recipient label',
      (tester) async {
    await _pumpSettingsScreen(
      tester,
      authState: const AuthState(
        token: 'token',
        username: 'Demo User',
        isLoading: false,
      ),
      onSendReport: () async => const ReportEmailResult(
        message: 'Report queued',
        recipients: [],
      ),
    );

    await _scrollToReportSection(tester);

    await tester.tap(find.byKey(const ValueKey('settings.sendReportButton')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Report sent to your account email'), findsOneWidget);
  });

  testWidgets('settings screen keeps session when sign out is cancelled',
      (tester) async {
    await _pumpSettingsScreen(
      tester,
      authState: const AuthState(
        token: 'token',
        username: 'Demo User',
        email: 'demo@example.com',
        isLoading: false,
      ),
    );

    await _scrollToSignOutAction(tester);

    await tester.tap(find.text('SIGN OUT').first);
    await tester.pumpAndSettle();

    expect(find.text('Sign out?'), findsOneWidget);
    await tester.tap(find.text('CANCEL'));
    await tester.pumpAndSettle();

    expect(find.text('Sign out?'), findsNothing);
    expect(find.text('demo@example.com'), findsOneWidget);
    expect(find.byKey(const ValueKey('settings.sendReportButton')),
        findsOneWidget);
  });

  testWidgets('settings screen logs out after confirming sign out',
      (tester) async {
    var logoutCalls = 0;

    await _pumpSettingsScreen(
      tester,
      authState: const AuthState(
        token: 'token',
        username: 'Demo User',
        email: 'demo@example.com',
        isLoading: false,
      ),
      onLogout: () => logoutCalls += 1,
    );

    await _scrollToSignOutAction(tester);

    await tester.tap(find.text('SIGN OUT').first);
    await tester.pumpAndSettle();

    await tester.tap(find.text('SIGN OUT').last);
    await tester.pumpAndSettle();

    expect(logoutCalls, 1);
    await _scrollToLoggedOutState(tester);
    expect(find.text('Not logged in.'), findsOneWidget);
    expect(
        find.byKey(const ValueKey('settings.sendReportButton')), findsNothing);
  });

  testWidgets('settings screen back button pops current route', (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authProvider.overrideWith(
            (_) => _FakeAuthNotifier(const AuthState(isLoading: false)),
          ),
          cfgProvider.overrideWith(
            (_) => _FakeCfgNotifier(kDefaultBaseUrl),
          ),
          reportEmailProvider.overrideWith(
            (ref) => _FakeReportEmailNotifier(ref, const ReportEmailState()),
          ),
        ],
        child: MaterialApp(
          initialRoute: '/settings',
          routes: {
            '/': (_) => const Scaffold(body: Text('HOME SCREEN')),
            '/settings': (_) => const SettingsScreen(),
          },
        ),
      ),
    );

    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.arrow_back_ios_rounded));
    await tester.pumpAndSettle();

    expect(find.text('HOME SCREEN'), findsOneWidget);
  });
}
