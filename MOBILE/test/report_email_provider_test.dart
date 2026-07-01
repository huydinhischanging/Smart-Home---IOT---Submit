import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smart_home_mobile/core/api_context_provider.dart';
import 'package:smart_home_mobile/core/http_client_provider.dart';
import 'package:smart_home_mobile/modules/report/report_email_provider.dart';

void main() {
  test('report email value objects expose helpers', () {
    const exception = ReportEmailException('Email offline');
    const state = ReportEmailState(sending: true, error: 'fail');
    final copied = state.copyWith(sending: false, error: null);
    final preserved = state.copyWith(error: 'still-failing');

    expect(exception.toString(), 'Email offline');
    expect(copied.sending, false);
    expect(copied.error, isNull);
    expect(preserved.sending, true);
    expect(preserved.error, 'still-failing');
  });

  test('report email provider sends to account email successfully', () async {
    final client = MockClient(
      (_) async => http.Response(
        '{"status":"success","message":"Patient report email sent successfully","filename":"alfred_report_demo.pdf","delivery":{"sent":true,"recipients":["demo@example.com"]}}',
        200,
      ),
    );

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider
          .overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    final result =
        await container.read(reportEmailProvider.notifier).sendToAccountEmail();
    final state = container.read(reportEmailProvider);

    expect(result.filename, 'alfred_report_demo.pdf');
    expect(result.recipients, ['demo@example.com']);
    expect(state.sending, false);
    expect(state.error, isNull);
  });

  test('report email provider surfaces backend errors', () async {
    final client = MockClient(
      (_) async => http.Response(
        '{"status":"error","message":"Email delivery unavailable."}',
        503,
      ),
    );

    final container = ProviderContainer(overrides: [
      apiBaseUrlProvider.overrideWithValue('http://example.test'),
      authHeadersProvider
          .overrideWithValue(const {'Authorization': 'Bearer token'}),
      httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(container.dispose);

    await expectLater(
      container.read(reportEmailProvider.notifier).sendToAccountEmail(),
      throwsA(
        isA<ReportEmailException>().having(
          (error) => error.message,
          'message',
          'Email delivery unavailable.',
        ),
      ),
    );

    final state = container.read(reportEmailProvider);
    expect(state.sending, false);
    expect(state.error, 'Email delivery unavailable.');
  });
}
