# Smart Home Mobile

Flutter mobile client for the IoT Elderly Smart Home system.

## Prerequisites

- Flutter 3.41+
- Dart 3.11+
- Android Studio or Xcode toolchain

## Install

```bash
flutter pub get
```

## Run (recommended)

Use compile-time variables instead of hardcoding endpoints or secrets.

If `APP_BASE_URL` is omitted, the app now falls back to a platform-aware default:

- Android emulator: `http://10.0.2.2:5000`
- Windows/Linux/macOS/Web on the same machine: `http://127.0.0.1:5000`
- iOS simulator: `http://localhost:5000`

In dev flavor, HTTP is allowed for emulator/local targets and private LAN addresses. Public, staging, or production backends should use `https://`.

```bash
flutter run --flavor dev \
	--dart-define=APP_ENV=dev \
	--dart-define=APP_BASE_URL=http://10.0.2.2:5000 \
	--dart-define=MQTT_BROKER=your-broker \
	--dart-define=MQTT_PORT=8883 \
	--dart-define=MQTT_USER=your-user \
	--dart-define=MQTT_PASS=your-pass
```

Common development targets:

- Android emulator: `http://10.0.2.2:5000`
- Windows desktop on the same machine: `http://127.0.0.1:5000`
- Real phone on the current LAN (dev): `http://<your-pc-lan-ip>:5000` or `http://your-pc.local:5000`
- Real phone on public/staging/prod: `https://your-lan-host-or-domain`

You can also change the backend URL at runtime from the mobile Settings screen.

## Driver Mode

To enable Copilot or Flutter Driver interaction for runtime validation, launch the app with the driver entrypoint:

```bash
flutter run --flavor dev -t lib/driver_main.dart \
	--dart-define=APP_ENV=dev \
	--dart-define=APP_BASE_URL=http://127.0.0.1:5000
```

The login form exposes stable driver keys:

- `login.identity`
- `login.password`
- `login.submit`

## Production Run

Production mode blocks non-HTTPS backend URLs.

```bash
flutter run --flavor prod --release \
	--dart-define=APP_ENV=prod \
	--dart-define=APP_BASE_URL=https://api.your-domain.com
```

## iOS Environment Behavior

- Debug build uses `Runner/Info-Debug.plist` and allows HTTP for local development.
- Profile/Release builds use `Runner/Info-Release.plist` and keep ATS strict.
- Always pass `--dart-define=APP_ENV=prod` together with an HTTPS `APP_BASE_URL` for production.

## Quality Checks

```bash
flutter analyze
flutter test
```

## Test Matrix

Verified on Windows with Flutter 3.41.4 / Dart 3.11.1.

Standard mobile suite:

```bash
flutter test test/widget_test.dart \
	test/settings_screen_test.dart \
	test/sensor_provider_test.dart \
	test/routine_screen_test.dart \
	test/report_email_provider_test.dart \
	test/notifications_screen_test.dart \
	test/map_provider_test.dart \
	test/health_screen_test.dart \
	test/dashboard_screen_test.dart \
	test/dashboard_provider_test.dart \
	test/cfg_provider_test.dart \
	test/cfg_provider_web_test.dart \
	test/automation_provider_test.dart \
	test/auth_service_test.dart \
	test/auth_provider_test.dart \
	test/alfred_screen_test.dart \
	test/alfred_provider_test.dart \
	test/alert_provider_test.dart \
	test/socket_service_test.dart \
	test/common_widgets_test.dart
	test/bc_test.dart
```

Current verified result: `148 passed, 0 failed`

Environment-specific config checks:

```bash
flutter test test/cfg_provider_env_test.dart \
	--dart-define=APP_BASE_URL=https://api.example.com \
	--dart-define=APP_ENV=prod
```

Current verified result: `2 passed, 0 failed`

Web-default config check:

```bash
flutter test test/cfg_provider_web_test.dart
```

Note: the web default branch is now covered through a pure helper in `cfg_provider`, so this test no longer depends on Chrome/web runner bootstrap.

## Coverage Highlights

The following files were verified with focused coverage runs and reached `100%` statement coverage during this test pass:

- `lib/screens/alfred_screen.dart`
- `lib/screens/dashboard_screen.dart`
- `lib/screens/health_screen.dart`
- `lib/screens/login_screen.dart`
- `lib/screens/notifications_screen.dart`
- `lib/screens/routine_screen.dart`
- `lib/screens/settings_screen.dart`
- `lib/core/bc.dart`
- `lib/core/socket_service.dart`
- `lib/core/auth_provider.dart`
- `lib/core/cfg_provider.dart`
- `lib/modules/alert/alert_provider.dart`
- `lib/modules/ai/alfred_provider.dart`
- `lib/modules/automation/automation_provider.dart`
- `lib/modules/auth/auth_service.dart`
- `lib/modules/dashboard/dashboard_provider.dart`
- `lib/modules/map/map_provider.dart`
- `lib/modules/sensor/sensor_provider.dart`
- `lib/modules/report/report_email_provider.dart`
- `lib/widgets/common_widgets.dart`

These coverage values came from focused runs on the files above, not from a single monolithic coverage job across the entire app.

Aggregate coverage snapshot from the latest full standard-suite coverage run:

- `lib/core/bc.dart`: `99.0%`
- `lib/widgets/common_widgets.dart`: `99.2%`

The latest aggregate run for the standard suite completed with `148 passed, 0 failed`. The remaining aggregate gaps are all near-100 files, with no major low-coverage logic hotspots left in the tracked mobile suite.

## Notes

- Android manifest includes internet permission in main manifest for release builds.
- `dev` flavor allows HTTP for emulator/local hosts, private LAN IPv4 ranges, and local hostnames (for example `.local`, `.lan`).
- `prod` flavor disables cleartext traffic on Android and enforces HTTPS app-side.
- CI builds both Android flavors (`dev` debug and `prod` release) in `.github/workflows/ci.yml`.
