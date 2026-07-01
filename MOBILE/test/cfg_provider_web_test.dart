import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/foundation.dart';
import 'package:smart_home_mobile/core/cfg_provider.dart';

void main() {
  test('cfg provider uses localhost default for web in helper', () {
    expect(
      defaultBaseUrlFor(
        isWeb: true,
        platform: TargetPlatform.android,
      ),
      'http://127.0.0.1:5000',
    );
  });
}