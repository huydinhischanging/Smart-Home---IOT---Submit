import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_home_mobile/core/cfg_provider.dart';

const _configuredBaseUrl = String.fromEnvironment('APP_BASE_URL', defaultValue: '');
const _appEnv = String.fromEnvironment('APP_ENV', defaultValue: 'dev');

Future<void> _flushMicrotasks() async {
  for (var index = 0; index < 4; index += 1) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('cfg provider respects APP_BASE_URL override when provided', () {
    if (_configuredBaseUrl.isEmpty) {
      expect(kDefaultBaseUrl, isNotEmpty);
      return;
    }

    expect(kDefaultBaseUrl, sanitizeBaseUrl(_configuredBaseUrl));
  });

  test('cfg provider rejects insecure saved URL in prod mode', () async {
    if (_appEnv != 'prod') {
      expect(
        () => validateBaseUrlForEnv('http://127.0.0.1:5000'),
        returnsNormally,
      );
      return;
    }

    expect(
      () => validateBaseUrlForEnv('http://insecure.local'),
      throwsFormatException,
    );

    SharedPreferences.setMockInitialValues({
      'cfg_base_url': 'http://insecure.local///',
    });

    final notifier = CfgNotifier();
    addTearDown(notifier.dispose);

    await _flushMicrotasks();
    final prefs = await SharedPreferences.getInstance();

    expect(notifier.state, kDefaultBaseUrl);
    expect(prefs.getString('cfg_base_url'), isNull);
  });
}