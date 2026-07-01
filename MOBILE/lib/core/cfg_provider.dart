import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kBaseUrl = 'cfg_base_url';
const kAppEnv = String.fromEnvironment('APP_ENV', defaultValue: 'dev');

bool get isProdEnv => kAppEnv.toLowerCase() == 'prod';

bool isHttpsUrl(String url) {
  final uri = Uri.tryParse(url.trim());
  return uri != null && uri.scheme.toLowerCase() == 'https';
}

bool isAllowedLocalDevHost(String host) {
  final normalized = host.trim().toLowerCase();
  return normalized == 'localhost' ||
      normalized == '127.0.0.1' ||
      normalized == '10.0.2.2';
}

bool isAllowedLocalDevHttpUrl(String url) {
  final uri = Uri.tryParse(url.trim());
  if (uri == null || uri.scheme.toLowerCase() != 'http') {
    return false;
  }
  // Cho phép HTTP với các host local dev và IP LAN 192.168.x.x
  return isAllowedLocalDevHost(uri.host) || uri.host.startsWith('192.168.');
}

String sanitizeBaseUrl(String url) => url.trim().replaceAll(RegExp(r'/+$'), '');

void validateBaseUrlForEnv(String url) {
  if (isHttpsUrl(url) || isAllowedLocalDevHttpUrl(url)) {
    return;
  }

  if (isProdEnv) {
    throw const FormatException(
        'Production mode requires an HTTPS backend URL.');
  }

  throw const FormatException(
    'Use HTTPS for non-local backends. HTTP is only allowed for localhost, 127.0.0.1, or 10.0.2.2 during development.',
  );
}

const _kConfiguredBaseUrl = String.fromEnvironment(
  'APP_BASE_URL',
  defaultValue: '',
);

String defaultBaseUrlFor({
  required bool isWeb,
  required TargetPlatform platform,
  String configuredBaseUrl = _kConfiguredBaseUrl,
}) {
  if (configuredBaseUrl.isNotEmpty) {
    return sanitizeBaseUrl(configuredBaseUrl);
  }

  if (isWeb) {
    return 'http://127.0.0.1:5000';
  }

  switch (platform) {
    case TargetPlatform.android:
      return 'http://192.168.1.3:5000';
    case TargetPlatform.iOS:
      return 'http://localhost:5000';
    case TargetPlatform.macOS:
    case TargetPlatform.windows:
    case TargetPlatform.linux:
      return 'http://127.0.0.1:5000';
    case TargetPlatform.fuchsia:
      return 'http://127.0.0.1:5000';
  }
}

String get kDefaultBaseUrl {
  return defaultBaseUrlFor(
    isWeb: kIsWeb,
    platform: defaultTargetPlatform,
  );
}

String? resolvedSavedBaseUrl(
  String? saved, {
  required bool isProd,
  required String defaultBaseUrl,
}) {
  if (saved == null || saved.isEmpty) {
    return null;
  }

  final clean = sanitizeBaseUrl(saved);
  final isAllowedLocalHttp = isAllowedLocalDevHttpUrl(clean);
  if ((isProd && !isHttpsUrl(clean)) ||
      (!isProd && !isHttpsUrl(clean) && !isAllowedLocalHttp)) {
    return defaultBaseUrl;
  }

  return clean;
}

Future<String?> loadSavedBaseUrl(
  SharedPreferences prefs, {
  required bool isProd,
  required String defaultBaseUrl,
}) async {
  final saved = prefs.getString(_kBaseUrl);
  final resolved = resolvedSavedBaseUrl(
    saved,
    isProd: isProd,
    defaultBaseUrl: defaultBaseUrl,
  );
  if (resolved == null) {
    return null;
  }

  if (resolved == defaultBaseUrl && saved != sanitizeBaseUrl(defaultBaseUrl)) {
    await prefs.remove(_kBaseUrl);
  }

  return resolved;
}

class CfgNotifier extends StateNotifier<String> {
  CfgNotifier() : super(kDefaultBaseUrl) {
    validateBaseUrlForEnv(state);
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final resolved = await loadSavedBaseUrl(
      prefs,
      isProd: isProdEnv,
      defaultBaseUrl: kDefaultBaseUrl,
    );
    if (resolved != null) {
      state = resolved;
    }
  }

  Future<void> setBase(String url) async {
    final clean = sanitizeBaseUrl(url);
    validateBaseUrlForEnv(clean);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kBaseUrl, clean);
    state = clean;
  }

  Future<void> reset() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kBaseUrl);
    state = kDefaultBaseUrl;
  }
}

final cfgProvider = StateNotifierProvider<CfgNotifier, String>(
  (_) => CfgNotifier(),
);
