import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:network_info_plus/network_info_plus.dart';
import '../core/bc.dart';
import '../core/cfg_provider.dart';
import '../core/auth_provider.dart';
import '../core/api_context_provider.dart';
import '../core/api_headers.dart';
import '../core/http_client_provider.dart';
import '../modules/auth/auth_service.dart';
import '../modules/report/report_email_provider.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});
  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  static const _notificationEmailKey = ValueKey('settings.notificationEmail');
  static const _sendReportButtonKey = ValueKey('settings.sendReportButton');
  final _urlCtrl = TextEditingController();
  ProviderSubscription<String>? _cfgSubscription;

  void _syncUrlField(String url) {
    if (_urlCtrl.text == url) return;
    _urlCtrl.value = TextEditingValue(
      text: url,
      selection: TextSelection.collapsed(offset: url.length),
    );
  }

  @override
  void initState() {
    super.initState();
    _syncUrlField(ref.read(cfgProvider));
    _cfgSubscription = ref.listenManual<String>(cfgProvider, (_, next) {
      _syncUrlField(next);
      if (mounted) {
        setState(() {});
      }
    });
  }

  @override
  void dispose() {
    _cfgSubscription?.close();
    _urlCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final url = _urlCtrl.text.trim();
    if (url.isEmpty) return;
    try {
      await ref.read(cfgProvider.notifier).setBase(url);
    } on FormatException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(
          e.message,
          style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
        ),
        backgroundColor: BC.red,
        duration: const Duration(seconds: 3),
      ));
      return;
    }
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text(
          'Server URL saved.',
          style: TextStyle(fontFamily: 'monospace', fontSize: 12),
        ),
        backgroundColor: BC.panel,
        duration: Duration(seconds: 2),
      ));
    }
  }

  Future<void> _reset() async {
    await ref.read(cfgProvider.notifier).reset();
  }

  Future<void> _scanLocalServers() async {
    String? wifiIP;
    try {
      wifiIP = await NetworkInfo().getWifiIP();
    } catch (_) {}

    if (!mounted) return;

    if (wifiIP == null || !wifiIP.contains('.')) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('WiFi IP not found. Are you connected to WiFi?',
            style: TextStyle(fontFamily: 'monospace', fontSize: 12)),
        backgroundColor: BC.red,
        duration: Duration(seconds: 3),
      ));
      return;
    }

    final parts = wifiIP.split('.');
    if (parts.length != 4) return;
    final prefix = '${parts[0]}.${parts[1]}.${parts[2]}.';

    final selected = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ScanSheet(prefix: prefix, myIp: wifiIP!),
    );

    if (selected != null && mounted) {
      _urlCtrl.text = selected;
      setState(() {});
    }
  }

  Future<void> _logout() async {
    final auth = ref.read(authProvider);
    if (!auth.isLoggedIn) return;
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: BC.panel,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Sign out?',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 14,
              color: BC.txt,
            )),
        content: Text(
          'Signed in as ${auth.username ?? "user"}. Log out?',
          style: const TextStyle(
              fontFamily: 'monospace', fontSize: 12, color: BC.txtDim),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('CANCEL',
                style: TextStyle(color: BC.txtDim, fontFamily: 'monospace')),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('SIGN OUT',
                style: TextStyle(color: BC.red, fontFamily: 'monospace')),
          ),
        ],
      ),
    );
    if (confirm == true) {
      await ref.read(authProvider.notifier).logout();
      // Navigation back to LoginScreen handled by _App watching authProvider
      if (mounted) Navigator.of(context).popUntil((r) => r.isFirst);
    }
  }

  Future<void> _sendReportEmail() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final result =
          await ref.read(reportEmailProvider.notifier).sendToAccountEmail();
      if (!mounted) return;
      final recipients = result.recipients.isEmpty
          ? (ref.read(authProvider).email ?? 'your account email')
          : result.recipients.join(', ');
      messenger.showSnackBar(SnackBar(
        content: Text(
          'Report sent to $recipients',
          style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
        ),
        backgroundColor: BC.panel,
        duration: const Duration(seconds: 3),
      ));
    } catch (error) {
      if (!mounted) return;
      final message = error is ReportEmailException
          ? error.message
          : 'Cannot send report email right now.';
      messenger.showSnackBar(SnackBar(
        content: Text(
          message,
          style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
        ),
        backgroundColor: BC.red,
        duration: const Duration(seconds: 3),
      ));
    }
  }

  Future<void> _changeUsername() async {
    final auth = ref.read(authProvider);
    final token = auth.token;
    if (token == null || token.isEmpty) return;

    final usernameCtrl = TextEditingController(text: auth.username ?? '');
    final passwordCtrl = TextEditingController();
    String? dialogError;
    bool busy = false;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) {
          Future<void> submit() async {
            final newUsername = usernameCtrl.text.trim();
            final currentPassword = passwordCtrl.text;
            if (newUsername.isEmpty || currentPassword.isEmpty) {
              setDialogState(() =>
                  dialogError = 'Enter the new username and current password.');
              return;
            }
            setDialogState(() {
              busy = true;
              dialogError = null;
            });
            try {
              final messenger = ScaffoldMessenger.of(context);
              final data = await ref.read(authServiceProvider).updateUsername(
                    token,
                    newUsername,
                    currentPassword,
                  );
              final user = data['user'];
              await ref.read(authProvider.notifier).updateProfile(
                    username: user is Map
                        ? user['username']?.toString()
                        : newUsername,
                    email: user is Map ? user['email']?.toString() : auth.email,
                  );
              if (!mounted) return;
              if (dialogContext.mounted) Navigator.of(dialogContext).pop();
              messenger.showSnackBar(SnackBar(
                content: Text(data['message']?.toString() ??
                    'Username updated successfully'),
                backgroundColor: BC.panel,
                duration: const Duration(seconds: 3),
              ));
            } catch (error) {
              setDialogState(() {
                dialogError = error is AuthServiceException
                    ? error.message
                    : 'Cannot update username right now.';
              });
            } finally {
              if (dialogContext.mounted) {
                setDialogState(() => busy = false);
              }
            }
          }

          return AlertDialog(
            backgroundColor: BC.panel,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
            title: const Text(
              'Change Username',
              style: TextStyle(
                  fontFamily: 'monospace', color: BC.txt, fontSize: 14),
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  key: const ValueKey('settings.changeUsername.username'),
                  controller: usernameCtrl,
                  style: const TextStyle(
                      fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                  decoration: const InputDecoration(labelText: 'NEW USERNAME'),
                ),
                const SizedBox(height: 10),
                TextField(
                  key: const ValueKey('settings.changeUsername.password'),
                  controller: passwordCtrl,
                  obscureText: true,
                  style: const TextStyle(
                      fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                  decoration:
                      const InputDecoration(labelText: 'CURRENT PASSWORD'),
                ),
                if (dialogError != null) ...[
                  const SizedBox(height: 10),
                  Text(
                    dialogError!,
                    style: const TextStyle(
                        fontFamily: 'monospace', fontSize: 10, color: BC.red),
                  ),
                ],
              ],
            ),
            actions: [
              TextButton(
                onPressed:
                    busy ? null : () => Navigator.of(dialogContext).pop(),
                child: const Text('CANCEL',
                    style:
                        TextStyle(fontFamily: 'monospace', color: BC.txtDim)),
              ),
              TextButton(
                key: const ValueKey('settings.changeUsername.submit'),
                onPressed: busy ? null : submit,
                child: busy
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: BC.gold),
                      )
                    : const Text('UPDATE',
                        style:
                            TextStyle(fontFamily: 'monospace', color: BC.gold)),
              ),
            ],
          );
        },
      ),
    );

    await WidgetsBinding.instance.endOfFrame;
    usernameCtrl.dispose();
    passwordCtrl.dispose();
  }

  Future<void> _editPatientProfile() async {
    final auth = ref.read(authProvider);
    if (auth.token == null || auth.token!.isEmpty) return;

    final base    = ref.read(apiBaseUrlProvider);
    final client  = ref.read(httpClientProvider);
    final headers = apiJsonHeaders(ref.read(authHeadersProvider));

    final nameCtrl      = TextEditingController();
    final ageCtrl       = TextEditingController();
    final diagnosisCtrl = TextEditingController();
    final medsCtrl      = TextEditingController();
    String? gender;
    bool busy = false;
    String? dialogError;

    // Pre-load existing profile
    try {
      final r = await client
          .get(Uri.parse('$base/api/patient/profile'), headers: headers)
          .timeout(const Duration(seconds: 10));
      if (r.statusCode == 200) {
        final d = jsonDecode(r.body) as Map<String, dynamic>;
        final p = d['profile'] as Map<String, dynamic>? ?? d;
        nameCtrl.text      = p['patient_name']?.toString() ?? '';
        ageCtrl.text       = (p['age'] as num?)?.toString() ?? '';
        gender             = p['gender']?.toString();
        diagnosisCtrl.text = p['diagnosis_notes']?.toString() ?? '';
        medsCtrl.text      = p['medications']?.toString() ?? '';
      }
    } catch (_) {}

    if (!mounted) return;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) {
          Future<void> submit() async {
            setDialogState(() { busy = true; dialogError = null; });
            try {
              final r = await client
                  .put(
                    Uri.parse('$base/api/patient/profile'),
                    headers: headers,
                    body: jsonEncode({
                      'patient_name':    nameCtrl.text.trim(),
                      'age':             int.tryParse(ageCtrl.text.trim()),
                      'gender':          gender,
                      'diagnosis_notes': diagnosisCtrl.text.trim(),
                      'medications':     medsCtrl.text.trim(),
                    }),
                  )
                  .timeout(const Duration(seconds: 10));
              if (r.statusCode == 200) {
                if (dialogContext.mounted) Navigator.of(dialogContext).pop();
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                    content: Text('Patient profile updated.',
                        style: TextStyle(fontFamily: 'monospace', fontSize: 12)),
                    backgroundColor: BC.panel,
                    duration: Duration(seconds: 2),
                  ));
                }
              } else {
                final d = jsonDecode(r.body) as Map<String, dynamic>? ?? {};
                setDialogState(() {
                  dialogError = d['message']?.toString() ?? 'HTTP ${r.statusCode}';
                  busy = false;
                });
              }
            } catch (_) {
              setDialogState(() {
                dialogError = 'Cannot reach server.';
                busy = false;
              });
            }
          }

          return AlertDialog(
            backgroundColor: BC.panel,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
            title: const Text('Patient Profile',
                style: TextStyle(fontFamily: 'monospace', color: BC.txt, fontSize: 14)),
            content: SingleChildScrollView(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                TextField(
                  controller: nameCtrl,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                  decoration: const InputDecoration(labelText: 'PATIENT NAME'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: ageCtrl,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                  decoration: const InputDecoration(labelText: 'AGE'),
                ),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  initialValue: (gender?.isNotEmpty == true) ? gender : null,
                  dropdownColor: BC.panel,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                  decoration: const InputDecoration(labelText: 'GENDER'),
                  items: const [
                    DropdownMenuItem(value: 'male',   child: Text('Male')),
                    DropdownMenuItem(value: 'female', child: Text('Female')),
                    DropdownMenuItem(value: 'other',  child: Text('Other')),
                  ],
                  onChanged: (v) => setDialogState(() => gender = v),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: diagnosisCtrl,
                  maxLines: 2,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                  decoration: const InputDecoration(labelText: 'DIAGNOSIS NOTES'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: medsCtrl,
                  maxLines: 2,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                  decoration: const InputDecoration(labelText: 'MEDICATIONS'),
                ),
                if (dialogError != null) ...[
                  const SizedBox(height: 10),
                  Text(dialogError!, style: const TextStyle(
                      fontFamily: 'monospace', fontSize: 10, color: BC.red)),
                ],
              ]),
            ),
            actions: [
              TextButton(
                onPressed: busy ? null : () => Navigator.of(dialogContext).pop(),
                child: const Text('CANCEL',
                    style: TextStyle(fontFamily: 'monospace', color: BC.txtDim)),
              ),
              TextButton(
                onPressed: busy ? null : submit,
                child: busy
                    ? const SizedBox(width: 16, height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2, color: BC.cyan))
                    : const Text('SAVE',
                        style: TextStyle(fontFamily: 'monospace', color: BC.cyan)),
              ),
            ],
          );
        },
      ),
    );

    await WidgetsBinding.instance.endOfFrame;
    nameCtrl.dispose();
    ageCtrl.dispose();
    diagnosisCtrl.dispose();
    medsCtrl.dispose();
  }

  Future<void> _deleteAccount() async {
    final auth = ref.read(authProvider);
    final token = auth.token;
    if (token == null || token.isEmpty) return;

    final passwordCtrl = TextEditingController();
    String? dialogError;
    bool busy = false;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) {
          Future<void> submit() async {
            final currentPassword = passwordCtrl.text;
            if (currentPassword.isEmpty) {
              setDialogState(() =>
                  dialogError = 'Enter your current password to continue.');
              return;
            }
            setDialogState(() {
              busy = true;
              dialogError = null;
            });
            try {
              final messenger = ScaffoldMessenger.of(context);
              final navigator = Navigator.of(context);
              final data = await ref
                  .read(authServiceProvider)
                  .deleteAccount(token, currentPassword);
              if (!mounted) return;
              if (dialogContext.mounted) Navigator.of(dialogContext).pop();
              await ref.read(authProvider.notifier).logout();
              if (!mounted) return;
              messenger.showSnackBar(SnackBar(
                content: Text(data['message']?.toString() ??
                    'Account cancelled successfully'),
                backgroundColor: BC.panel,
                duration: const Duration(seconds: 3),
              ));
              navigator.popUntil((route) => route.isFirst);
            } catch (error) {
              setDialogState(() {
                dialogError = error is AuthServiceException
                    ? error.message
                    : 'Cannot cancel the account right now.';
              });
            } finally {
              if (dialogContext.mounted) {
                setDialogState(() => busy = false);
              }
            }
          }

          return AlertDialog(
            backgroundColor: BC.panel,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
            title: const Text(
              'Delete Account',
              style: TextStyle(
                  fontFamily: 'monospace', color: BC.txt, fontSize: 14),
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'This deactivates your account and signs you out on this device.',
                  style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 10,
                      color: BC.txtDim,
                      height: 1.5),
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const ValueKey('settings.deleteAccount.password'),
                  controller: passwordCtrl,
                  obscureText: true,
                  style: const TextStyle(
                      fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                  decoration:
                      const InputDecoration(labelText: 'CURRENT PASSWORD'),
                ),
                if (dialogError != null) ...[
                  const SizedBox(height: 10),
                  Text(
                    dialogError!,
                    style: const TextStyle(
                        fontFamily: 'monospace', fontSize: 10, color: BC.red),
                  ),
                ],
              ],
            ),
            actions: [
              TextButton(
                onPressed:
                    busy ? null : () => Navigator.of(dialogContext).pop(),
                child: const Text('CANCEL',
                    style:
                        TextStyle(fontFamily: 'monospace', color: BC.txtDim)),
              ),
              TextButton(
                key: const ValueKey('settings.deleteAccount.submit'),
                onPressed: busy ? null : submit,
                child: busy
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: BC.red),
                      )
                    : const Text('DELETE',
                        style:
                            TextStyle(fontFamily: 'monospace', color: BC.red)),
              ),
            ],
          );
        },
      ),
    );

    await WidgetsBinding.instance.endOfFrame;
    passwordCtrl.dispose();
  }

  @override
  Widget build(BuildContext ctx) {
    final auth = ref.watch(authProvider);
    final current = ref.watch(cfgProvider);
    final reportEmail = ref.watch(reportEmailProvider);

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(children: [
        const Positioned.fill(child: TacticalBackdrop()),
        SafeArea(
          child: Column(children: [
            // header
            Container(
              padding: const EdgeInsets.fromLTRB(8, 10, 16, 10),
              child: Row(children: [
                IconButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  icon: const Icon(Icons.arrow_back_ios_rounded,
                      color: BC.txtDim, size: 18),
                ),
                const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('SETTINGS',
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 15,
                            color: BC.gold,
                            letterSpacing: 3,
                            fontWeight: FontWeight.bold,
                          )),
                      Text('SYSTEM CONFIGURATION',
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 7,
                            color: BC.txtDim,
                            letterSpacing: 2,
                          )),
                    ]),
              ]),
            ),

            Expanded(
                child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              children: [
                // ── Server URL ──────────────────
                const _SectionLabel(label: 'BACKEND SERVER'),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: BC.panel.withValues(alpha: 0.90),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: BC.border),
                  ),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Enter your backend URL. HTTP is only for local development on Android emulator 10.0.2.2, desktop/web 127.0.0.1, or iOS simulator localhost. Use HTTPS for LAN, staging, or production backends.',
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 10,
                            color: BC.txtDim,
                            height: 1.6,
                          ),
                        ),
                        const SizedBox(height: 14),
                        TextField(
                          controller: _urlCtrl,
                          style: const TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 13,
                            color: BC.txt,
                          ),
                          decoration: const InputDecoration(
                            labelText: 'SERVER URL',
                            hintText: 'https://api.example.com',
                            prefixIcon: Icon(Icons.dns_outlined,
                                color: BC.txtDim, size: 18),
                          ),
                          keyboardType: TextInputType.url,
                          autocorrect: false,
                        ),
                        const SizedBox(height: 14),
                        Row(children: [
                          Expanded(
                            child: SizedBox(
                              height: 44,
                              child: ElevatedButton(
                                onPressed: _save,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: BC.gold,
                                  foregroundColor: BC.bg,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  elevation: 0,
                                ),
                                child: const Text('SAVE',
                                    style: TextStyle(
                                      fontFamily: 'monospace',
                                      fontSize: 11,
                                      letterSpacing: 2,
                                      fontWeight: FontWeight.bold,
                                    )),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          SizedBox(
                            height: 44,
                            child: OutlinedButton(
                              onPressed: _reset,
                              style: OutlinedButton.styleFrom(
                                side: const BorderSide(color: BC.border),
                                foregroundColor: BC.txtDim,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                              ),
                              child: const Text('RESET',
                                  style: TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 11,
                                    letterSpacing: 2,
                                  )),
                            ),
                          ),
                        ]),
                        const SizedBox(height: 8),
                        SizedBox(
                          width: double.infinity,
                          height: 44,
                          child: OutlinedButton.icon(
                            onPressed: _scanLocalServers,
                            icon: const Icon(Icons.wifi_find, size: 16),
                            label: const Text('SCAN LOCAL NETWORK',
                                style: TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 10,
                                  letterSpacing: 1.5,
                                )),
                            style: OutlinedButton.styleFrom(
                              side: const BorderSide(color: BC.cyan),
                              foregroundColor: BC.cyan,
                              shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12)),
                            ),
                          ),
                        ),
                        const SizedBox(height: 10),
                        Row(children: [
                          const Icon(Icons.circle, color: BC.green, size: 8),
                          const SizedBox(width: 6),
                          Expanded(
                              child: Text('Current: $current',
                                  style: const TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 9,
                                    color: BC.txtDim,
                                  ))),
                        ]),
                        const SizedBox(height: 8),
                        const Text(
                          'Local HTTP presets are for simulator/emulator use only. Android cleartext is restricted to localhost and 10.0.2.2.',
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 9,
                            color: BC.txtDim,
                            height: 1.5,
                          ),
                        ),
                      ]),
                ),

                const SizedBox(height: 20),

                // ── Quick IP hints ──────────────
                const _SectionLabel(label: 'QUICK SELECT'),
                const SizedBox(height: 10),
                _QuickUrls(onSelect: (url) {
                  _urlCtrl.text = url;
                  setState(() {});
                }),

                const SizedBox(height: 20),

                // ── Appearance ──────────────────
                const _SectionLabel(label: 'APPEARANCE'),
                const SizedBox(height: 10),
                const _MoodSelector(),

                const SizedBox(height: 20),

                // ── Account ─────────────────────
                const _SectionLabel(label: 'ACCOUNT'),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: BC.panel.withValues(alpha: 0.90),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: BC.border),
                  ),
                  child: auth.isLoggedIn
                      ? Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                              Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Container(
                                      width: 42,
                                      height: 42,
                                      decoration: BoxDecoration(
                                        shape: BoxShape.circle,
                                        color: BC.goldDim,
                                        border:
                                            Border.all(color: BC.goldBorder),
                                      ),
                                      child: const Center(
                                          child: Text('🦇',
                                              style: TextStyle(fontSize: 20))),
                                    ),
                                    const SizedBox(width: 14),
                                    Expanded(
                                        child: Column(
                                            crossAxisAlignment:
                                                CrossAxisAlignment.start,
                                            children: [
                                          Text(auth.username ?? 'User',
                                              style: const TextStyle(
                                                fontFamily: 'monospace',
                                                fontSize: 13,
                                                color: BC.txt,
                                                fontWeight: FontWeight.bold,
                                              )),
                                          const Text('AUTHENTICATED',
                                              style: TextStyle(
                                                fontFamily: 'monospace',
                                                fontSize: 8,
                                                color: BC.green,
                                                letterSpacing: 1.5,
                                              )),
                                          const SizedBox(height: 8),
                                          Text('Notification email',
                                              style: TextStyle(
                                                fontFamily: 'monospace',
                                                fontSize: 8,
                                                color: BC.txtDim
                                                    .withValues(alpha: 0.72),
                                                letterSpacing: 1.2,
                                              )),
                                          const SizedBox(height: 4),
                                          Text(
                                            auth.email ??
                                                'Will sync after next sign-in',
                                            key: _notificationEmailKey,
                                            style: TextStyle(
                                              fontFamily: 'monospace',
                                              fontSize: 11,
                                              color: auth.email != null
                                                  ? BC.gold
                                                  : BC.txtDim,
                                              height: 1.4,
                                            ),
                                          ),
                                        ])),
                                    GestureDetector(
                                      onTap: _logout,
                                      child: Container(
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 12, vertical: 8),
                                        decoration: BoxDecoration(
                                          color: BC.red.withValues(alpha: 0.07),
                                          borderRadius:
                                              BorderRadius.circular(10),
                                          border: Border.all(
                                              color: BC.red
                                                  .withValues(alpha: 0.30)),
                                        ),
                                        child: const Text('SIGN OUT',
                                            style: TextStyle(
                                              fontFamily: 'monospace',
                                              fontSize: 9,
                                              color: BC.red,
                                              letterSpacing: 1,
                                            )),
                                      ),
                                    ),
                                  ]),
                              const SizedBox(height: 16),
                              Row(
                                children: [
                                  Expanded(
                                    child: OutlinedButton(
                                      key: const ValueKey(
                                          'settings.changeUsername.button'),
                                      onPressed: _changeUsername,
                                      style: OutlinedButton.styleFrom(
                                        side:
                                            const BorderSide(color: BC.border),
                                        foregroundColor: BC.gold,
                                        shape: RoundedRectangleBorder(
                                          borderRadius:
                                              BorderRadius.circular(12),
                                        ),
                                      ),
                                      child: const Text(
                                        'CHANGE USERNAME',
                                        style: TextStyle(
                                          fontFamily: 'monospace',
                                          fontSize: 9,
                                          letterSpacing: 1.2,
                                        ),
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: OutlinedButton(
                                      key: const ValueKey(
                                          'settings.deleteAccount.button'),
                                      onPressed: _deleteAccount,
                                      style: OutlinedButton.styleFrom(
                                        side: BorderSide(
                                            color:
                                                BC.red.withValues(alpha: 0.45)),
                                        foregroundColor: BC.red,
                                        shape: RoundedRectangleBorder(
                                          borderRadius:
                                              BorderRadius.circular(12),
                                        ),
                                      ),
                                      child: const Text(
                                        'DELETE ACCOUNT',
                                        style: TextStyle(
                                          fontFamily: 'monospace',
                                          fontSize: 9,
                                          letterSpacing: 1.2,
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              Container(
                                width: double.infinity,
                                padding: const EdgeInsets.all(14),
                                decoration: BoxDecoration(
                                  color: BC.elevated,
                                  borderRadius: BorderRadius.circular(14),
                                  border: Border.all(color: BC.border),
                                ),
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      const Text('REPORT DELIVERY',
                                          style: TextStyle(
                                            fontFamily: 'monospace',
                                            fontSize: 9,
                                            color: BC.gold,
                                            letterSpacing: 1.8,
                                          )),
                                      const SizedBox(height: 8),
                                      const Text(
                                        'Alerts and PDF patient reports are sent to your notification email by default.',
                                        style: TextStyle(
                                          fontFamily: 'monospace',
                                          fontSize: 10,
                                          color: BC.txtDim,
                                          height: 1.5,
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                      SizedBox(
                                        width: double.infinity,
                                        height: 42,
                                        child: ElevatedButton(
                                          key: _sendReportButtonKey,
                                          onPressed: reportEmail.sending
                                              ? null
                                              : _sendReportEmail,
                                          style: ElevatedButton.styleFrom(
                                            backgroundColor: BC.gold,
                                            foregroundColor: BC.bg,
                                            disabledBackgroundColor: BC.goldDim,
                                            elevation: 0,
                                            shape: RoundedRectangleBorder(
                                              borderRadius:
                                                  BorderRadius.circular(12),
                                            ),
                                          ),
                                          child: reportEmail.sending
                                              ? const SizedBox(
                                                  width: 18,
                                                  height: 18,
                                                  child:
                                                      CircularProgressIndicator(
                                                    strokeWidth: 2,
                                                    color: BC.bg,
                                                  ),
                                                )
                                              : const Text(
                                                  'EMAIL MY LATEST REPORT',
                                                  style: TextStyle(
                                                    fontFamily: 'monospace',
                                                    fontSize: 10,
                                                    letterSpacing: 1.6,
                                                    fontWeight: FontWeight.bold,
                                                  )),
                                        ),
                                      ),
                                      if (reportEmail.error != null) ...[
                                        const SizedBox(height: 8),
                                        Text(
                                          reportEmail.error!,
                                          style: const TextStyle(
                                            fontFamily: 'monospace',
                                            fontSize: 9,
                                            color: BC.red,
                                            height: 1.4,
                                          ),
                                        ),
                                      ],
                                    ]),
                              ),
                            ])
                      : const Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                              Text('Not logged in.',
                                  style: TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 12,
                                    color: BC.txtDim,
                                  )),
                              SizedBox(height: 6),
                              Text('Log in to access health data.',
                                  style: TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 10,
                                    color: BC.txtDim,
                                  )),
                            ]),
                ),

                const SizedBox(height: 20),

                // ── Patient Profile ─────────────
                const _SectionLabel(label: 'PATIENT PROFILE'),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: BC.panel.withValues(alpha: 0.90),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: BC.border),
                  ),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text(
                      'Patient information used in health reports and AI analysis.',
                      style: TextStyle(
                        fontFamily: 'monospace', fontSize: 10,
                        color: BC.txtDim, height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 14),
                    SizedBox(
                      width: double.infinity,
                      height: 44,
                      child: OutlinedButton.icon(
                        onPressed: _editPatientProfile,
                        icon: const Icon(Icons.person_outline_rounded, size: 16),
                        label: const Text('EDIT PATIENT PROFILE',
                            style: TextStyle(
                              fontFamily: 'monospace', fontSize: 10, letterSpacing: 1.5,
                            )),
                        style: OutlinedButton.styleFrom(
                          side: const BorderSide(color: BC.cyan),
                          foregroundColor: BC.cyan,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12)),
                        ),
                      ),
                    ),
                  ]),
                ),

                const SizedBox(height: 30),

                // ── About ───────────────────────
                Center(
                    child: Column(children: [
                  const Text('ALFRED SMART HOME · ELDER CARE',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 9,
                        color: BC.txtDim,
                        letterSpacing: 2,
                      )),
                  const SizedBox(height: 4),
                  Text(
                      'v1.0 · Flutter ${const String.fromEnvironment('FLUTTER_VERSION', defaultValue: '3.x')}',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 8,
                        color: BC.txtDim.withValues(alpha: 0.5),
                      )),
                ])),
                const SizedBox(height: 20),
              ],
            )),
          ]),
        ),
      ]),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String label;
  const _SectionLabel({required this.label});
  @override
  Widget build(BuildContext ctx) => Row(children: [
        Text(label,
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 9,
              color: BC.txtDim,
              letterSpacing: 2.5,
            )),
        const SizedBox(width: 8),
        Expanded(child: Container(height: 1, color: BC.border)),
      ]);
}

class _QuickUrls extends StatelessWidget {
  final void Function(String) onSelect;
  const _QuickUrls({required this.onSelect});

  static const _urls = [
    ('LAN Device (Real Phone)', 'http://192.168.1.3:5000'),
    ('Android Emulator', 'http://10.0.2.2:5000'),
    ('Desktop Localhost', 'http://127.0.0.1:5000'),
    ('iOS Simulator', 'http://localhost:5000'),
    ('HTTPS Staging', 'https://staging.example.com'),
    ('HTTPS Custom Host', 'https://your-domain.example'),
  ];

  @override
  Widget build(BuildContext ctx) => Wrap(
        spacing: 8,
        runSpacing: 8,
        children: _urls.map((item) {
          final (label, url) = item;
          return GestureDetector(
            onTap: () => onSelect(url),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
              decoration: BoxDecoration(
                color: BC.elevated,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: BC.border),
              ),
              child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 8,
                          color: BC.gold,
                          letterSpacing: 0.5,
                        )),
                    Text(url,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 8,
                          color: BC.txtDim,
                        )),
                  ]),
            ),
          );
        }).toList(),
      );
}

// ── Mood Selector ─────────────────────────
class _MoodSelector extends ConsumerWidget {
  const _MoodSelector();

  @override
  Widget build(BuildContext ctx, WidgetRef ref) {
    final current = ref.watch(moodProvider);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: BC.panel.withValues(alpha: 0.90),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: BC.border),
      ),
      child: Column(children: [
        Row(children: [
          const Text('SYSTEM MOOD',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 9,
                color: BC.txtDim,
                letterSpacing: 2,
              )),
          const Spacer(),
          Text(current.emoji, style: const TextStyle(fontSize: 14)),
          const SizedBox(width: 6),
          Text(current.label,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 9,
                color: current.accent,
                letterSpacing: 1.5,
                fontWeight: FontWeight.bold,
              )),
        ]),
        const SizedBox(height: 12),
        Row(
            children: AppMood.values.map((m) {
          final active = m == current;
          return Expanded(
              child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 3),
            child: GestureDetector(
              onTap: () => ref.read(moodProvider.notifier).set(m),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color:
                      active ? m.accent.withValues(alpha: 0.14) : BC.elevated,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color:
                        active ? m.accent.withValues(alpha: 0.55) : BC.border,
                    width: active ? 1.5 : 1,
                  ),
                  boxShadow: active
                      ? [
                          BoxShadow(
                            color: m.accent.withValues(alpha: 0.18),
                            blurRadius: 8,
                            spreadRadius: 1,
                          )
                        ]
                      : null,
                ),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Text(m.emoji, style: const TextStyle(fontSize: 18)),
                  const SizedBox(height: 4),
                  Text(m.label,
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 7,
                        color: active ? m.accent : BC.txtDim,
                        letterSpacing: 1,
                        fontWeight:
                            active ? FontWeight.bold : FontWeight.normal,
                      )),
                ]),
              ),
            ),
          ));
        }).toList()),
      ]),
    );
  }
}

// ══════════════════════════════════════════════════════════════
// LAN SCAN SHEET
// ══════════════════════════════════════════════════════════════
class _ScanSheet extends StatefulWidget {
  final String prefix; // e.g. "192.168.1."
  final String myIp;

  const _ScanSheet({required this.prefix, required this.myIp});

  @override
  State<_ScanSheet> createState() => _ScanSheetState();
}

class _ScanSheetState extends State<_ScanSheet> {
  final List<String> _found = [];
  int _done = 0;
  bool _scanning = true;

  static const _total = 254;
  static const _batchSize = 25;
  static const _port = 5000;
  static const _timeout = Duration(milliseconds: 700);

  @override
  void initState() {
    super.initState();
    _runScan();
  }

  Future<void> _runScan() async {
    for (int start = 1; start <= _total; start += _batchSize) {
      if (!mounted) return;
      final end = (start + _batchSize - 1).clamp(1, _total);
      final futures = <Future<String?>>[];
      for (int i = start; i <= end; i++) {
        futures.add(_probe('${widget.prefix}$i'));
      }
      final results = await Future.wait(futures);
      if (!mounted) return;
      setState(() {
        _done = end;
        for (final r in results) {
          if (r != null && !_found.contains(r)) _found.add(r);
        }
      });
    }
    if (mounted) setState(() => _scanning = false);
  }

  Future<String?> _probe(String host) async {
    try {
      final socket = await Socket.connect(host, _port, timeout: _timeout);
      socket.destroy();
      return 'http://$host:$_port';
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final progress = _total > 0 ? _done / _total : 0.0;

    return Container(
      margin: const EdgeInsets.fromLTRB(10, 0, 10, 10),
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      decoration: BoxDecoration(
        color: BC.panel,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: BC.border),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Handle
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                  color: BC.border, borderRadius: BorderRadius.circular(2)),
            ),
          ),
          const SizedBox(height: 16),

          // Title row
          Row(children: [
            const Text('⚡',style: TextStyle(fontSize: 18)),
            const SizedBox(width: 10),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('LAN SCAN',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 14,
                        color: BC.cyan,
                        letterSpacing: 3,
                        fontWeight: FontWeight.bold,
                      )),
                  Text('Looking for backend on port 5000',
                      style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 9,
                          color: BC.txtDim,
                          letterSpacing: 1)),
                ],
              ),
            ),
            Text(
              _scanning ? '$_done/$_total' : 'Done',
              style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 10,
                  color: _scanning ? BC.gold : BC.green,
                  letterSpacing: 1),
            ),
          ]),
          const SizedBox(height: 12),

          // Progress bar
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: _scanning ? progress : 1.0,
              backgroundColor: BC.elevated,
              color: _scanning ? BC.gold : BC.green,
              minHeight: 4,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            _scanning
                ? 'Scanning ${widget.prefix}1 … ${widget.prefix}$_total'
                : '${_found.length} server${_found.length == 1 ? '' : 's'} found',
            style: const TextStyle(
                fontFamily: 'monospace', fontSize: 9, color: BC.txtDim),
          ),
          const SizedBox(height: 14),

          // Results list
          if (_found.isEmpty && !_scanning)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 20),
              alignment: Alignment.center,
              child: const Text(
                'No servers found on this subnet.\nCheck that the backend is running.',
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontFamily: 'monospace', fontSize: 10, color: BC.txtDim, height: 1.6),
              ),
            )
          else
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 220),
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: _found.length,
                itemBuilder: (_, i) {
                  final url = _found[i];
                  final isMyDevice = url.contains(widget.myIp);
                  return Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    decoration: BoxDecoration(
                      color: BC.card,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: BC.cyan.withValues(alpha: 0.35)),
                    ),
                    child: Row(children: [
                      const Text('🖥', style: TextStyle(fontSize: 18)),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(url,
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 11,
                                  color: BC.txt,
                                  letterSpacing: 0.5,
                                )),
                            if (isMyDevice)
                              const Text('this device',
                                  style: TextStyle(
                                      fontFamily: 'monospace',
                                      fontSize: 8,
                                      color: BC.gold)),
                          ],
                        ),
                      ),
                      GestureDetector(
                        onTap: () => Navigator.of(context).pop(url),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: BC.cyan.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                                color: BC.cyan.withValues(alpha: 0.4)),
                          ),
                          child: const Text('USE',
                              style: TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 10,
                                color: BC.cyan,
                                letterSpacing: 1,
                                fontWeight: FontWeight.bold,
                              )),
                        ),
                      ),
                    ]),
                  );
                },
              ),
            ),

          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(
                _scanning ? 'CANCEL' : 'CLOSE',
                style: const TextStyle(
                    fontFamily: 'monospace', fontSize: 11, color: BC.txtDim),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
