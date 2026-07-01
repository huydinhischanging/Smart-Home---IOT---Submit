@echo off
echo ========================================
echo  Smart Home Flutter - Auto Setup
echo ========================================

REM Phai chay tu thu muc: IOT-OLDER\mobile\
REM Check dung thu muc chua
if not exist "pubspec.yaml" (
    echo [ERROR] Hay chay script nay tu ben trong thu muc mobile\
    pause
    exit /b 1
)

if exist "lib\main.dart" (
    if /I not "%ALLOW_DESTRUCTIVE_BOOTSTRAP%"=="1" (
        echo [ERROR] Da phat hien ung dung Flutter hien co trong thu muc nay.
        echo [ERROR] Script bootstrap nay se xoa toan bo thu muc lib va ghi de pubspec.yaml.
        echo [ERROR] Neu muon tiep tuc co chu dich, hay chay lai voi ALLOW_DESTRUCTIVE_BOOTSTRAP=1
        pause
        exit /b 1
    )
)

echo [1/7] Xoa lib mac dinh...
rmdir /s /q lib 2>nul

echo [2/7] Tao cau truc thu muc...
mkdir lib\core\api
mkdir lib\core\socket
mkdir lib\core\mqtt
mkdir lib\core\models
mkdir lib\core\utils
mkdir lib\modules\auth
mkdir lib\modules\dashboard
mkdir lib\modules\device
mkdir lib\modules\sensor
mkdir lib\modules\alert
mkdir lib\modules\ai

echo [3/7] Tao core files...

REM ── app_config.dart ──────────────────────────────────────
(
echo // lib/core/utils/app_config.dart
echo class AppConfig {
echo   static const String baseUrl = String.fromEnvironment^(
echo     'APP_BASE_URL',
echo     defaultValue: '',
echo   ^);
echo   static const String socketUrl = String.fromEnvironment^(
echo     'APP_SOCKET_URL',
echo     defaultValue: '',
echo   ^);
echo   static const String mqttBroker = 'YOUR_EMQX_BROKER';
echo   static const int    mqttPort   = 8883;
echo   static const String mqttUser   = 'YOUR_MQTT_USER';
echo   static const String mqttPass   = 'YOUR_MQTT_PASS';
echo   static const String mqttTopicSensor  = 'home/sensors/#';
echo   static const String mqttTopicControl = 'home/control';
echo   static const String mqttTopicStatus  = 'home/status/#';
echo }
) > lib\core\utils\app_config.dart

REM ── models/device.dart ───────────────────────────────────
(
echo class Device {
echo   final String id, name, type, roomId;
echo   final bool isOnline, state;
echo   final Map^<String, dynamic^>? metadata;
echo   Device({required this.id, required this.name, required this.type,
echo     required this.roomId, required this.isOnline, required this.state, this.metadata});
echo   factory Device.fromJson^(Map^<String, dynamic^> json^) =^> Device^(
echo     id: json['id'] ?? '', name: json['name'] ?? '',
echo     type: json['type'] ?? '', roomId: json['room_id'] ?? '',
echo     isOnline: json['is_online'] ?? false,
echo     state: json['state'] == 1 ^|^| json['state'] == true,
echo     metadata: json['metadata'],
echo   ^);
echo   Device copyWith^({bool? state, bool? isOnline}^) =^> Device^(
echo     id: id, name: name, type: type, roomId: roomId,
echo     isOnline: isOnline ?? this.isOnline, state: state ?? this.state,
echo   ^);
echo }
echo class SensorReading {
echo   final String deviceId, sensorType, unit;
echo   final double value;
echo   final DateTime timestamp;
echo   SensorReading({required this.deviceId, required this.sensorType,
echo     required this.value, required this.unit, required this.timestamp});
echo   factory SensorReading.fromJson^(Map^<String, dynamic^> json^) =^> SensorReading^(
echo     deviceId: json['device_id'] ?? '', sensorType: json['sensor_type'] ?? '',
echo     value: ^(json['value'] ?? 0^).toDouble^(^), unit: json['unit'] ?? '',
echo     timestamp: DateTime.tryParse^(json['timestamp'] ?? ''^^^) ?? DateTime.now^(^),
echo   ^);
echo }
echo class Room {
echo   final String id, name, icon;
echo   final List^<Device^> devices;
echo   Room({required this.id, required this.name, required this.icon, this.devices = const []});
echo   factory Room.fromJson^(Map^<String, dynamic^> json^) =^> Room^(
echo     id: json['id'] ?? '', name: json['name'] ?? '', icon: json['icon'] ?? 'home',
echo     devices: ^(json['devices'] as List^<dynamic^>? ?? []^).map^(^(d^) =^> Device.fromJson^(d^)^).toList^(^),
echo   ^);
echo }
echo class Alert {
echo   final String id, type, message, severity;
echo   final bool isRead;
echo   final DateTime createdAt;
echo   Alert({required this.id, required this.type, required this.message,
echo     required this.severity, required this.isRead, required this.createdAt});
echo   factory Alert.fromJson^(Map^<String, dynamic^> json^) =^> Alert^(
echo     id: json['id'] ?? '', type: json['type'] ?? '',
echo     message: json['message'] ?? '', severity: json['severity'] ?? 'info',
echo     isRead: json['is_read'] ?? false,
echo     createdAt: DateTime.tryParse^(json['created_at'] ?? ''^^^) ?? DateTime.now^(^),
echo   ^);
echo }
) > lib\core\models\device.dart

echo [4/7] Tao pubspec.yaml...
(
echo name: smart_home_mobile
echo description: Smart Home IoT Mobile App
echo publish_to: 'none'
echo version: 1.0.0+1
echo environment:
echo   sdk: '>=3.0.0 ^<4.0.0'
echo dependencies:
echo   flutter:
echo     sdk: flutter
echo   dio: ^5.4.0
echo   socket_io_client: ^2.0.3+1
echo   mqtt_client: ^10.2.1
echo   flutter_riverpod: ^2.5.1
echo   flutter_secure_storage: ^9.0.0
echo   fl_chart: ^0.68.0
echo   intl: ^0.19.0
echo   logger: ^2.3.0
echo   shared_preferences: ^2.2.3
echo   cupertino_icons: ^1.0.6
echo dev_dependencies:
echo   flutter_test:
echo     sdk: flutter
echo   flutter_lints: ^3.0.0
echo flutter:
echo   uses-material-design: true
) > pubspec.yaml

echo [5/7] Tao main.dart...
(
echo import 'package:flutter/material.dart';
echo import 'package:flutter_riverpod/flutter_riverpod.dart';
echo import 'modules/auth/login_screen.dart';
echo import 'modules/dashboard/dashboard_screen.dart';
echo.
echo void main^(^) {
echo   WidgetsFlutterBinding.ensureInitialized^(^);
echo   runApp^(const ProviderScope^(child: SmartHomeApp^(^)^)^);
echo }
echo.
echo class SmartHomeApp extends StatelessWidget {
echo   const SmartHomeApp^({super.key}^);
echo   ^@override
echo   Widget build^(BuildContext context^) {
echo     return MaterialApp^(
echo       title: 'Smart Home',
echo       debugShowCheckedModeBanner: false,
echo       theme: ThemeData^(
echo         colorScheme: ColorScheme.dark^(
echo           primary: const Color^(0xFF38BDF8^),
echo           surface: const Color^(0xFF1E293B^),
echo         ^),
echo         useMaterial3: true,
echo       ^),
echo       initialRoute: '/login',
echo       routes: {
echo         '/login': ^(_^) =^> const LoginScreen^(^),
echo         '/dashboard': ^(_^) =^> const DashboardScreen^(^),
echo       },
echo     ^);
echo   }
echo }
) > lib\main.dart

echo [6/7] Tao placeholder screens...

REM login_screen.dart
(
echo import 'package:flutter/material.dart';
echo import 'package:flutter_riverpod/flutter_riverpod.dart';
echo.
echo class LoginScreen extends ConsumerStatefulWidget {
echo   const LoginScreen^({super.key}^);
echo   ^@override
echo   ConsumerState^<LoginScreen^> createState^(^) =^> _LoginScreenState^(^);
echo }
echo class _LoginScreenState extends ConsumerState^<LoginScreen^> {
echo   final _userCtrl = TextEditingController^(^);
echo   final _passCtrl = TextEditingController^(^);
echo   ^@override
echo   Widget build^(BuildContext context^) {
echo     return Scaffold^(
echo       backgroundColor: const Color^(0xFF0F172A^),
echo       body: Center^(
echo         child: Padding^(
echo           padding: const EdgeInsets.all^(32^),
echo           child: Column^(
echo             mainAxisAlignment: MainAxisAlignment.center,
echo             children: [
echo               const Icon^(Icons.home_outlined, color: Color^(0xFF38BDF8^), size: 64^),
echo               const SizedBox^(height: 16^),
echo               const Text^('Smart Home', style: TextStyle^(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold^)^),
echo               const SizedBox^(height: 40^),
echo               TextField^(
echo                 controller: _userCtrl,
echo                 style: const TextStyle^(color: Colors.white^),
echo                 decoration: const InputDecoration^(hintText: 'Username', hintStyle: TextStyle^(color: Colors.white38^), filled: true, fillColor: Color^(0xFF1E293B^), border: OutlineInputBorder^(borderSide: BorderSide.none^)^),
echo               ^),
echo               const SizedBox^(height: 12^),
echo               TextField^(
echo                 controller: _passCtrl, obscureText: true,
echo                 style: const TextStyle^(color: Colors.white^),
echo                 decoration: const InputDecoration^(hintText: 'Password', hintStyle: TextStyle^(color: Colors.white38^), filled: true, fillColor: Color^(0xFF1E293B^), border: OutlineInputBorder^(borderSide: BorderSide.none^)^),
echo               ^),
echo               const SizedBox^(height: 24^),
echo               SizedBox^(
echo                 width: double.infinity, height: 48,
echo                 child: ElevatedButton^(
echo                   style: ElevatedButton.styleFrom^(backgroundColor: const Color^(0xFF38BDF8^)^),
echo                   onPressed: ^(^) =^> Navigator.pushReplacementNamed^(context, '/dashboard'^),
echo                   child: const Text^('Login', style: TextStyle^(color: Colors.white, fontWeight: FontWeight.bold^)^),
echo                 ^),
echo               ^),
echo             ],
echo           ^),
echo         ^),
echo       ^),
echo     ^);
echo   }
echo }
) > lib\modules\auth\login_screen.dart

REM dashboard_screen.dart
(
echo import 'package:flutter/material.dart';
echo import 'package:flutter_riverpod/flutter_riverpod.dart';
echo import '../ai/ai_screen.dart';
echo.
echo class DashboardScreen extends ConsumerWidget {
echo   const DashboardScreen^({super.key}^);
echo   ^@override
echo   Widget build^(BuildContext context, WidgetRef ref^) {
echo     return Scaffold^(
echo       backgroundColor: const Color^(0xFF0F172A^),
echo       appBar: AppBar^(
echo         backgroundColor: const Color^(0xFF1E293B^),
echo         title: const Text^('Smart Home', style: TextStyle^(color: Colors.white, fontWeight: FontWeight.bold^)^),
echo         actions: [
echo           IconButton^(
echo             icon: const Icon^(Icons.smart_toy_outlined, color: Color^(0xFF38BDF8^)^),
echo             onPressed: ^(^) =^> Navigator.push^(context, MaterialPageRoute^(builder: ^(_^) =^> const AiScreen^(^)^)^),
echo           ^),
echo         ],
echo       ^),
echo       body: const Center^(
echo         child: Column^(
echo           mainAxisAlignment: MainAxisAlignment.center,
echo           children: [
echo             Icon^(Icons.check_circle_outline, color: Color^(0xFF34D399^), size: 80^),
echo             SizedBox^(height: 16^),
echo             Text^('Flutter App Ready!', style: TextStyle^(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold^)^),
echo             SizedBox^(height: 8^),
echo             Text^('Connect backend in app_config.dart', style: TextStyle^(color: Colors.white54^)^),
echo           ],
echo         ^),
echo       ^),
echo     ^);
echo   }
echo }
) > lib\modules\dashboard\dashboard_screen.dart

REM ai_screen.dart
(
echo import 'package:flutter/material.dart';
echo import 'package:flutter_riverpod/flutter_riverpod.dart';
echo.
echo class AiScreen extends ConsumerStatefulWidget {
echo   const AiScreen^({super.key}^);
echo   ^@override
echo   ConsumerState^<AiScreen^> createState^(^) =^> _AiScreenState^(^);
echo }
echo class _AiScreenState extends ConsumerState^<AiScreen^> {
echo   final _ctrl = TextEditingController^(^);
echo   final List^<Map^<String,String^>^> _msgs = [
echo     {'role':'assistant','content':'Hi! I am Alfred, your smart home AI.'}
echo   ];
echo   ^@override
echo   Widget build^(BuildContext context^) {
echo     return Scaffold^(
echo       backgroundColor: const Color^(0xFF0F172A^),
echo       appBar: AppBar^(backgroundColor: const Color^(0xFF1E293B^), title: const Text^('Alfred AI', style: TextStyle^(color: Colors.white^)^), leading: const BackButton^(color: Colors.white^)^),
echo       body: Column^(children: [
echo         Expanded^(child: ListView^(padding: const EdgeInsets.all^(16^), children: _msgs.map^(^(m^) =^> Align^(
echo           alignment: m['role']=='user' ? Alignment.centerRight : Alignment.centerLeft,
echo           child: Container^(
echo             margin: const EdgeInsets.only^(bottom:8^),
echo             padding: const EdgeInsets.symmetric^(horizontal:14, vertical:10^),
echo             decoration: BoxDecoration^(color: m['role']=='user' ? const Color^(0xFF38BDF8^) : const Color^(0xFF1E293B^), borderRadius: BorderRadius.circular^(16^)^),
echo             child: Text^(m['content']!, style: const TextStyle^(color: Colors.white^)^),
echo           ^),
echo         ^)^).toList^(^)^)^),
echo         Container^(
echo           color: const Color^(0xFF1E293B^), padding: const EdgeInsets.all^(8^),
echo           child: Row^(children: [
echo             Expanded^(child: TextField^(controller: _ctrl, style: const TextStyle^(color: Colors.white^), decoration: const InputDecoration^(hintText: 'Ask Alfred...', hintStyle: TextStyle^(color: Colors.white38^), filled: true, fillColor: Color^(0xFF0F172A^), border: OutlineInputBorder^(borderSide: BorderSide.none, borderRadius: BorderRadius.all^(Radius.circular^(24^)^)^)^)^)^),
echo             const SizedBox^(width:8^),
echo             CircleAvatar^(backgroundColor: const Color^(0xFF38BDF8^), child: IconButton^(icon: const Icon^(Icons.send, color: Colors.white, size:18^), onPressed: ^(^) { if^(_ctrl.text.isEmpty^) return; setState^(^(^) { _msgs.add^({'role':'user','content':_ctrl.text}^); _msgs.add^({'role':'assistant','content':'[Connect backend to get real response]'}^); _ctrl.clear^(^); }^); }^)^),
echo           ]^),
echo         ^),
echo       ]^),
echo     ^);
echo   }
echo }
) > lib\modules\ai\ai_screen.dart

echo [7/7] Cai dependencies...
call flutter pub get

echo.
echo ========================================
echo  XONG! Chay app bang lenh:
echo  flutter run -d chrome
echo ========================================
pause
