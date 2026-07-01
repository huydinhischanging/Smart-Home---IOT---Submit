import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/bc.dart';
import '../core/auth_provider.dart';
import '../modules/auth/auth_service.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});
  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen>
    with SingleTickerProviderStateMixin {
  static const _identityFieldKey = ValueKey('login.identity');
  static const _passwordFieldKey = ValueKey('login.password');
  static const _submitButtonKey = ValueKey('login.submit');

  final _identity = TextEditingController();
  final _password = TextEditingController();
  bool _loading = false;
  bool _obscure = true;
  String? _err;
  late AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulse.dispose();
    _identity.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _showForgotPasswordDialog() async {
    final emailCtrl = TextEditingController(text: _identity.text.contains('@') ? _identity.text.trim() : '');
    final tokenCtrl = TextEditingController();
    final newPasswordCtrl = TextEditingController();
    String? dialogError;
    String? dialogInfo;
    bool busy = false;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (dialogContext, setDialogState) {
            Future<void> sendCode() async {
              final email = emailCtrl.text.trim();
              if (email.isEmpty) {
                setDialogState(() => dialogError = 'Enter your account email first.');
                return;
              }
              setDialogState(() {
                busy = true;
                dialogError = null;
                dialogInfo = null;
              });
              try {
                final data = await ref.read(authServiceProvider).requestPasswordReset(email);
                final resetToken = data['reset_token']?.toString();
                setDialogState(() {
                  dialogInfo = data['message']?.toString() ?? 'Reset code requested.';
                  if (resetToken != null && resetToken.isNotEmpty) {
                    tokenCtrl.text = resetToken;
                    dialogInfo = 'Email is unavailable in this environment, so the reset code was filled automatically.';
                  } else if (dialogInfo == 'If the account exists, a password reset code has been sent.') {
                    dialogInfo = 'If the account exists, check the registered email for the reset code.';
                  }
                });
              } catch (error) {
                setDialogState(() {
                  dialogError = error is AuthServiceException
                      ? error.message
                      : 'Cannot request a password reset right now.';
                });
              } finally {
                setDialogState(() => busy = false);
              }
            }

            Future<void> resetPassword() async {
              final resetToken = tokenCtrl.text.trim();
              final newPassword = newPasswordCtrl.text;
              if (resetToken.isEmpty || newPassword.isEmpty) {
                setDialogState(() => dialogError = 'Enter the reset code and your new password.');
                return;
              }
              setDialogState(() {
                busy = true;
                dialogError = null;
                dialogInfo = null;
              });
              try {
                final messenger = ScaffoldMessenger.of(context);
                final data = await ref.read(authServiceProvider).resetPassword(resetToken, newPassword);
                if (!mounted) return;
                if (dialogContext.mounted) Navigator.of(dialogContext).pop();
                messenger.showSnackBar(SnackBar(
                  content: Text(
                    data['message']?.toString() ?? 'Password reset successfully. Please sign in again.',
                  ),
                  backgroundColor: BC.panel,
                  duration: const Duration(seconds: 3),
                ));
              } catch (error) {
                setDialogState(() {
                  dialogError = error is AuthServiceException
                      ? error.message
                      : 'Cannot reset password right now.';
                });
              } finally {
                if (dialogContext.mounted) {
                  setDialogState(() => busy = false);
                }
              }
            }

            return AlertDialog(
              backgroundColor: BC.panel,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              title: const Text(
                'Forgot Password',
                style: TextStyle(fontFamily: 'monospace', color: BC.txt, fontSize: 14),
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Request a reset code by email, then enter that code here with your new password. In trusted demo environments, the code may be filled automatically.',
                      style: TextStyle(fontFamily: 'monospace', fontSize: 10, color: BC.txtDim, height: 1.5),
                    ),
                    const SizedBox(height: 14),
                    TextField(
                      key: const ValueKey('login.forgot.email'),
                      controller: emailCtrl,
                      keyboardType: TextInputType.emailAddress,
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                      decoration: const InputDecoration(labelText: 'ACCOUNT EMAIL'),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      key: const ValueKey('login.forgot.token'),
                      controller: tokenCtrl,
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                      decoration: const InputDecoration(labelText: 'RESET CODE'),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      key: const ValueKey('login.forgot.newPassword'),
                      controller: newPasswordCtrl,
                      obscureText: true,
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: BC.txt),
                      decoration: const InputDecoration(labelText: 'NEW PASSWORD'),
                    ),
                    if (dialogInfo != null) ...[
                      const SizedBox(height: 10),
                      Text(
                        dialogInfo!,
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 10, color: BC.gold, height: 1.4),
                      ),
                    ],
                    if (dialogError != null) ...[
                      const SizedBox(height: 10),
                      Text(
                        dialogError!,
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 10, color: BC.red, height: 1.4),
                      ),
                    ],
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: busy ? null : () => Navigator.of(dialogContext).pop(),
                  child: const Text('CLOSE', style: TextStyle(fontFamily: 'monospace', color: BC.txtDim)),
                ),
                TextButton(
                  key: const ValueKey('login.forgot.sendCode'),
                  onPressed: busy ? null : sendCode,
                  child: const Text('SEND CODE', style: TextStyle(fontFamily: 'monospace', color: BC.gold)),
                ),
                TextButton(
                  key: const ValueKey('login.forgot.resetPassword'),
                  onPressed: busy ? null : resetPassword,
                  child: busy
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: BC.gold),
                        )
                      : const Text('RESET', style: TextStyle(fontFamily: 'monospace', color: BC.green)),
                ),
              ],
            );
          },
        );
      },
    );

    await WidgetsBinding.instance.endOfFrame;
    emailCtrl.dispose();
    tokenCtrl.dispose();
    newPasswordCtrl.dispose();
  }

  Future<void> _login() async {
    final id = _identity.text.trim();
    final pwd = _password.text;
    if (id.isEmpty || pwd.isEmpty) {
      setState(() => _err = 'Please enter username/email and password.');
      return;
    }
    setState(() {
      _loading = true;
      _err = null;
    });
    try {
      final data = await ref.read(authServiceProvider).login(id, pwd);
      final token = data['token']?.toString() ?? '';
      final user = data['user'];
      final username = user is Map ? user['username']?.toString() ?? id : id;
      final userId = user is Map ? user['id'] as int? : null;
      final email = user is Map
          ? user['email']?.toString() ?? (id.contains('@') ? id : null)
          : (id.contains('@') ? id : null);
      await ref.read(authProvider.notifier).login(
            token: token,
            username: username,
            userId: userId,
            email: email,
          );
    } catch (e) {
      final message = e is AuthServiceException
          ? e.message
          : 'Cannot reach server. Check backend URL in Settings.';
      setState(() => _err = message);
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext ctx) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(children: [
        const Positioned.fill(child: TacticalBackdrop()),
        SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 28),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Logo section
                  AnimatedBuilder(
                    animation: _pulse,
                    builder: (_, __) => Container(
                      width: 86,
                      height: 86,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: BC.goldDim,
                        border: Border.all(color: BC.goldBorder, width: 1.5),
                        boxShadow: [
                          BoxShadow(
                            color: BC.gold
                                .withValues(alpha: 0.12 + _pulse.value * 0.14),
                            blurRadius: 24 + _pulse.value * 12,
                          ),
                        ],
                      ),
                      child: const Center(
                        child: Text('🤵', style: TextStyle(fontSize: 38)),
                      ),
                    ),
                  ),
                  const SizedBox(height: 22),
                  const Text('ALFRED SMART HOME',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 24,
                        letterSpacing: 5,
                        color: BC.gold,
                        fontWeight: FontWeight.bold,
                      )),
                  const SizedBox(height: 6),
                  const Text('ELDER CARE SYSTEM',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 10,
                        letterSpacing: 3,
                        color: BC.txtDim,
                      )),
                  const SizedBox(height: 40),

                  // Auth card
                  Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: BC.panel.withValues(alpha: 0.92),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: BC.border),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.3),
                          blurRadius: 24,
                          offset: const Offset(0, 10),
                        ),
                      ],
                    ),
                    child: Column(children: [
                      Row(children: [
                        Container(
                          width: 4,
                          height: 22,
                          decoration: BoxDecoration(
                            color: BC.gold,
                            borderRadius: BorderRadius.circular(2),
                          ),
                        ),
                        const SizedBox(width: 10),
                        const Text('AUTHENTICATE',
                            style: TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 12,
                              letterSpacing: 3,
                              color: BC.txt,
                              fontWeight: FontWeight.bold,
                            )),
                      ]),
                      const SizedBox(height: 22),

                      // Identity field
                      TextField(
                        key: _identityFieldKey,
                        controller: _identity,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 13,
                          color: BC.txt,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'USERNAME OR EMAIL',
                          prefixIcon: Icon(Icons.person_outline,
                              color: BC.txtDim, size: 18),
                        ),
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.next,
                        onSubmitted: (_) => FocusScope.of(ctx).nextFocus(),
                      ),
                      const SizedBox(height: 14),

                      // Password field
                      TextField(
                        key: _passwordFieldKey,
                        controller: _password,
                        obscureText: _obscure,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 13,
                          color: BC.txt,
                        ),
                        decoration: InputDecoration(
                          labelText: 'PASSWORD',
                          prefixIcon: const Icon(
                            Icons.lock_outline,
                            color: BC.txtDim,
                            size: 18,
                          ),
                          suffixIcon: GestureDetector(
                            onTap: () => setState(() => _obscure = !_obscure),
                            child: Icon(
                              _obscure
                                  ? Icons.visibility_off
                                  : Icons.visibility,
                              color: BC.txtDim,
                              size: 18,
                            ),
                          ),
                        ),
                        textInputAction: TextInputAction.done,
                        onSubmitted: (_) => _login(),
                      ),

                      // Error
                      if (_err != null) ...[
                        const SizedBox(height: 14),
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: BC.red.withValues(alpha: 0.07),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                                color: BC.red.withValues(alpha: 0.3)),
                          ),
                          child: Row(children: [
                            const Icon(Icons.warning_amber_rounded,
                                color: BC.red, size: 15),
                            const SizedBox(width: 8),
                            Expanded(
                                child: Text(_err!,
                                    style: const TextStyle(
                                      fontFamily: 'monospace',
                                      fontSize: 10,
                                      color: BC.red,
                                      height: 1.4,
                                    ))),
                          ]),
                        ),
                      ],

                      const SizedBox(height: 22),

                      // Login button
                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: ElevatedButton(
                          key: _submitButtonKey,
                          onPressed: _loading ? null : _login,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: BC.gold,
                            foregroundColor: BC.bg,
                            disabledBackgroundColor: BC.goldDim,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14),
                            ),
                            elevation: 0,
                          ),
                          child: _loading
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    color: BC.bg,
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Text('INITIATE ACCESS',
                                  style: TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 12,
                                    letterSpacing: 2.5,
                                    fontWeight: FontWeight.bold,
                                  )),
                        ),
                      ),

                      const SizedBox(height: 12),
                      Align(
                        alignment: Alignment.centerRight,
                        child: GestureDetector(
                          key: const ValueKey('login.forgotPassword'),
                          onTap: _loading ? null : _showForgotPasswordDialog,
                          child: Text(
                            'FORGOT PASSWORD?',
                            style: TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 9,
                              color: BC.gold.withValues(alpha: 0.85),
                              letterSpacing: 1.5,
                              decoration: TextDecoration.underline,
                              decorationColor: BC.gold.withValues(alpha: 0.5),
                            ),
                          ),
                        ),
                      ),

                      const SizedBox(height: 16),

                      // Biometric placeholder
                      Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Container(
                              decoration: BoxDecoration(
                                color: BC.elevated,
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: BC.border),
                              ),
                              child: Tooltip(
                                message:
                                    'Biometric requires setup in device settings',
                                child: Padding(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 18, vertical: 10),
                                  child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(Icons.fingerprint,
                                            color: BC.txtDim
                                                .withValues(alpha: 0.5),
                                            size: 20),
                                        const SizedBox(width: 8),
                                        Text('BIOMETRIC',
                                            style: TextStyle(
                                              fontFamily: 'monospace',
                                              fontSize: 9,
                                              color: BC.txtDim
                                                  .withValues(alpha: 0.5),
                                              letterSpacing: 2,
                                            )),
                                      ]),
                                ),
                              ),
                            ),
                          ]),
                    ]),
                  ),

                  const SizedBox(height: 14),

                  // Register hint
                  Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Text('No account yet?  ',
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 9,
                          color: BC.txtDim.withValues(alpha: 0.6),
                        )),
                    GestureDetector(
                      onTap: () => ScaffoldMessenger.of(ctx).showSnackBar(
                        const SnackBar(
                          content: Text(
                              'Registration is managed by your administrator.'),
                          backgroundColor: BC.panel,
                          duration: Duration(seconds: 3),
                        ),
                      ),
                      child: Text('REGISTER',
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 9,
                            color: BC.gold,
                            letterSpacing: 1.5,
                            decoration: TextDecoration.underline,
                            decorationColor: BC.gold.withValues(alpha: 0.6),
                          )),
                    ),
                  ]),

                  const SizedBox(height: 20),

                  // Settings link
                  GestureDetector(
                    onTap: () => Navigator.of(ctx).pushNamed('/settings'),
                    child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.settings_ethernet,
                              color: BC.txtDim, size: 14),
                          const SizedBox(width: 6),
                          Text('Configure server URL',
                              style: TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 9,
                                color: BC.txtDim.withValues(alpha: 0.7),
                                letterSpacing: 1,
                                decoration: TextDecoration.underline,
                                decorationColor:
                                    BC.txtDim.withValues(alpha: 0.4),
                              )),
                        ]),
                  ),
                  const SizedBox(height: 30),
                ],
              ),
            ),
          ),
        ),
      ]),
    );
  }
}
