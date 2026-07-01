import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_home_mobile/core/cfg_provider.dart';

Future<void> _flushMicrotasks() async {
  for (var index = 0; index < 4; index += 1) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
  });

  test('cfg helpers normalize URLs and platform defaults', () {
    expect(isHttpsUrl(' https://example.test/path '), true);
    expect(isHttpsUrl('http://example.test'), false);
    expect(isHttpsUrl('not a url'), false);
    expect(isAllowedLocalDevHost('localhost'), true);
    expect(isAllowedLocalDevHost('127.0.0.1'), true);
    expect(isAllowedLocalDevHost('10.0.2.2'), true);
    expect(isAllowedLocalDevHost('192.168.1.20'), false);
    expect(isAllowedLocalDevHttpUrl('http://127.0.0.1:5000'), true);
    expect(isAllowedLocalDevHttpUrl('http://192.168.1.20:5000'), true);
    expect(sanitizeBaseUrl(' http://example.test/// '), 'http://example.test');
    expect(
        () => validateBaseUrlForEnv('http://127.0.0.1:5000'), returnsNormally);
    expect(
      () => validateBaseUrlForEnv('http://192.168.1.20:5000'),
      returnsNormally,
    );
    expect(
      resolvedSavedBaseUrl(null,
          isProd: false, defaultBaseUrl: 'http://127.0.0.1:5000'),
      isNull,
    );
    expect(
      resolvedSavedBaseUrl(
        ' http://demo.local/// ',
        isProd: false,
        defaultBaseUrl: 'http://127.0.0.1:5000',
      ),
      'http://127.0.0.1:5000',
    );
    expect(
      resolvedSavedBaseUrl(
        'http://insecure.local///',
        isProd: true,
        defaultBaseUrl: 'https://secure.example.test',
      ),
      'https://secure.example.test',
    );

    expect(
      defaultBaseUrlFor(isWeb: false, platform: TargetPlatform.android),
      'http://192.168.1.3:5000',
    );
    expect(
      defaultBaseUrlFor(
        isWeb: false,
        platform: TargetPlatform.windows,
        configuredBaseUrl: ' https://api.example.test/// ',
      ),
      'https://api.example.test',
    );

    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    expect(kDefaultBaseUrl, 'http://localhost:5000');

    debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
    expect(kDefaultBaseUrl, 'http://127.0.0.1:5000');

    debugDefaultTargetPlatformOverride = TargetPlatform.windows;
    expect(kDefaultBaseUrl, 'http://127.0.0.1:5000');

    debugDefaultTargetPlatformOverride = TargetPlatform.linux;
    expect(kDefaultBaseUrl, 'http://127.0.0.1:5000');

    debugDefaultTargetPlatformOverride = TargetPlatform.fuchsia;
    expect(kDefaultBaseUrl, 'http://127.0.0.1:5000');
  });

  test('cfg provider loads and sanitizes saved base URL', () async {
    SharedPreferences.setMockInitialValues({
      'cfg_base_url': ' http://demo.local/// ',
    });

    final container = ProviderContainer();
    addTearDown(container.dispose);

    expect(container.read(cfgProvider), kDefaultBaseUrl);
    container.read(cfgProvider.notifier);
    await _flushMicrotasks();

    expect(container.read(cfgProvider), kDefaultBaseUrl);
  });

  test('cfg notifier persists setBase and clears value on reset', () async {
    SharedPreferences.setMockInitialValues({});

    final notifier = CfgNotifier();
    addTearDown(notifier.dispose);

    await notifier.setBase(' https://api.local/// ');
    final prefsAfterSet = await SharedPreferences.getInstance();
    expect(notifier.state, 'https://api.local');
    expect(prefsAfterSet.getString('cfg_base_url'), 'https://api.local');

    await notifier.reset();
    final prefsAfterReset = await SharedPreferences.getInstance();
    expect(notifier.state, kDefaultBaseUrl);
    expect(prefsAfterReset.getString('cfg_base_url'), isNull);
  });

  test('cfg notifier rejects insecure non-local dev URL', () async {
    SharedPreferences.setMockInitialValues({});

    final notifier = CfgNotifier();
    addTearDown(notifier.dispose);

    await notifier.setBase('http://192.168.1.20:5000');
    expect(notifier.state, 'http://192.168.1.20:5000');
  });

  test(
      'cfg helper loads saved base URL and removes insecure persisted prod value',
      () async {
    SharedPreferences.setMockInitialValues({});
    var prefs = await SharedPreferences.getInstance();

    expect(
      await loadSavedBaseUrl(
        prefs,
        isProd: false,
        defaultBaseUrl: 'http://127.0.0.1:5000',
      ),
      isNull,
    );

    SharedPreferences.setMockInitialValues({
      'cfg_base_url': ' http://demo.local/// ',
    });
    prefs = await SharedPreferences.getInstance();

    expect(
      await loadSavedBaseUrl(
        prefs,
        isProd: false,
        defaultBaseUrl: 'http://127.0.0.1:5000',
      ),
      'http://127.0.0.1:5000',
    );
    expect(prefs.getString('cfg_base_url'), isNull);

    SharedPreferences.setMockInitialValues({
      'cfg_base_url': 'http://insecure.local///',
    });
    prefs = await SharedPreferences.getInstance();

    expect(
      await loadSavedBaseUrl(
        prefs,
        isProd: true,
        defaultBaseUrl: 'https://secure.example.test',
      ),
      'https://secure.example.test',
    );
    expect(prefs.getString('cfg_base_url'), isNull);
  });

  test('cfg provider reset clears persisted value through provider notifier',
      () async {
    SharedPreferences.setMockInitialValues({
      'cfg_base_url': 'https://demo.local',
    });

    final container = ProviderContainer();
    addTearDown(container.dispose);

    container.read(cfgProvider.notifier);
    await _flushMicrotasks();
    expect(container.read(cfgProvider), 'https://demo.local');

    await container.read(cfgProvider.notifier).reset();
    final prefs = await SharedPreferences.getInstance();

    expect(container.read(cfgProvider), kDefaultBaseUrl);
    expect(prefs.getString('cfg_base_url'), isNull);
  });

  test('cfg provider discards insecure persisted non-local dev URL', () async {
    SharedPreferences.setMockInitialValues({
      'cfg_base_url': 'http://192.168.1.20:5000',
    });

    final container = ProviderContainer();
    addTearDown(container.dispose);

    container.read(cfgProvider.notifier);
    await _flushMicrotasks();

    final prefs = await SharedPreferences.getInstance();
    expect(container.read(cfgProvider), 'http://192.168.1.20:5000');
    expect(prefs.getString('cfg_base_url'), 'http://192.168.1.20:5000');
  });
}
