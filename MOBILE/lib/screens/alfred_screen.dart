import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:math' as math;
import 'package:speech_to_text/speech_to_text.dart';
import '../core/bc.dart';
import '../core/auth_provider.dart';
import '../modules/ai/alfred_provider.dart';

class AlfredScreen extends ConsumerStatefulWidget {
  const AlfredScreen({super.key});
  @override
  ConsumerState<AlfredScreen> createState() => _AlfredState();
}

class _AlfredState extends ConsumerState<AlfredScreen>
    with SingleTickerProviderStateMixin {
  final _ctrl   = TextEditingController();
  final _scroll = ScrollController();
  late AnimationController _pulse;

  // ── Voice ──
  final _speech   = SpeechToText();
  bool _sttReady  = false;
  bool _listening = false;

  static String _buildGreeting(String name) {
    final h = DateTime.now().hour;
    if (h >= 5 && h < 12) {
      return 'Good morning, $name.\nSystems are online. How may I assist you this morning?';
    }
    if (h >= 12 && h < 18) {
      return 'Good afternoon, $name.\nSystems are online. How may I assist you this afternoon?';
    }
    return 'Good evening, $name.\nSystems are online. How may I assist you tonight?';
  }

  static const _quickCmds = [
    'STATUS', 'LIGHTS ON', 'LIGHTS OFF', 'TEMPERATURE', '🚨 EMERGENCY',
  ];

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this, duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _initSpeech();
  }

  Future<void> _initSpeech() async {
    _sttReady = await _speech.initialize(
      onError: (_) {
        if (!mounted) return;
        setState(() => _listening = false);
      },
    );
    if (!mounted) return;
    setState(() {});
  }

  Future<void> _toggleListen() async {
    if (!_sttReady) return;
    if (_listening) {
      await _speech.stop();
      setState(() => _listening = false);
      return;
    }
    setState(() => _listening = true);
    await _speech.listen(
      onResult: (r) {
        if (r.finalResult && r.recognizedWords.isNotEmpty) {
          _ctrl.text = r.recognizedWords;
          if (!mounted) return;
          setState(() => _listening = false);
          _send();
        }
      },
      localeId: 'vi_VN',
      listenFor: const Duration(seconds: 10),
      pauseFor: const Duration(seconds: 3),
    );
  }

  @override
  void dispose() {
    _pulse.dispose();
    _speech.cancel();
    _ctrl.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send([String? preset]) async {
    final text = preset ?? _ctrl.text.trim();
    if (text.isEmpty || ref.read(alfredProvider).thinking) return;
    _ctrl.clear();
    setState(() {});
    _scrollDown();
    await ref.read(alfredProvider.notifier).send(text);
    _scrollDown();
  }

  void _scrollDown() => Future.delayed(const Duration(milliseconds: 120), () {
    if (_scroll.hasClients) {
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  });

  @override
  Widget build(BuildContext ctx) {
    final alfred = ref.watch(alfredProvider);
    final userName = ref.watch(authProvider).username ?? 'User';
    final messages = <ChatMessage>[
      ChatMessage(role: 'assistant', content: _buildGreeting(userName)),
      ...alfred.messages,
    ];

    return Scaffold(
    backgroundColor: Colors.transparent,
    body: SafeArea(child: Column(children: [
      // ── header card ──────────────────────
      Container(
        margin: const EdgeInsets.fromLTRB(14, 12, 14, 0),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: BC.panel.withValues(alpha: 0.88),
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: BC.cyan.withValues(alpha: 0.18)),
        ),
        child: Row(children: [
          AnimatedBuilder(
            animation: _pulse,
            builder: (_, __) => Container(
              width: 12, height: 12,
              decoration: BoxDecoration(
                shape: BoxShape.circle, color: BC.cyan,
                boxShadow: [BoxShadow(
                  color: BC.cyan.withValues(alpha: 0.3 + _pulse.value * 0.6),
                  blurRadius: 6 + _pulse.value * 8,
                )],
              ),
            ),
          ),
          const SizedBox(width: 12),
          const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('ALFRED', style: TextStyle(
              fontFamily: 'monospace', fontSize: 15,
              color: BC.cyan, letterSpacing: 4, fontWeight: FontWeight.bold,
            )),
            Text('BATCAVE INTELLIGENCE', style: TextStyle(
              fontFamily: 'monospace', fontSize: 7,
              color: BC.txtDim, letterSpacing: 2,
            )),
          ]),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: BC.cyanDim,
              border: Border.all(color: BC.cyan.withValues(alpha: 0.3)),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Text('ONLINE', style: TextStyle(
              fontFamily: 'monospace', fontSize: 8,
              color: BC.cyan, letterSpacing: 2,
            )),
          ),
        ]),
      ),

      // ── quick commands ────────────────────
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 6),
        child: Row(children: _quickCmds.map((cmd) {
          final isRed = cmd.contains('EMERGENCY');
          return GestureDetector(
            onTap: () => _send(cmd),
            child: Container(
              margin: const EdgeInsets.only(right: 6),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: isRed ? BC.red.withValues(alpha: 0.07) : BC.cyanDim,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isRed ? BC.red.withValues(alpha: 0.35) : BC.cyan.withValues(alpha: 0.25),
                ),
              ),
              child: Text(cmd, style: TextStyle(
                fontFamily: 'monospace', fontSize: 9, letterSpacing: 1,
                color: isRed ? BC.red : BC.cyan,
              )),
            ),
          );
        }).toList()),
      ),

      // ── info card ─────────────────────────
      Container(
        margin: const EdgeInsets.fromLTRB(14, 6, 14, 10),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: BC.panel.withValues(alpha: 0.88),
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: BC.cyan.withValues(alpha: 0.20)),
          gradient: LinearGradient(
            begin: Alignment.topLeft, end: Alignment.bottomRight,
            colors: [
              BC.cyan.withValues(alpha: 0.10),
              Colors.transparent,
              BC.gold.withValues(alpha: 0.05),
            ],
          ),
        ),
        child: const Row(children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('AI COMMAND RELAY', style: TextStyle(
              fontSize: 9, letterSpacing: 2.2,
              color: BC.cyan, fontWeight: FontWeight.bold,
            )),
            SizedBox(height: 6),
            Text(
              'Ask Alfred to inspect rooms, summarize device state, or trigger quick actions from your phone.',
              style: TextStyle(fontSize: 12, color: BC.txt, height: 1.55),
            ),
          ])),
          SizedBox(width: 12),
          Icon(Icons.auto_awesome_rounded, color: BC.gold, size: 24),
        ]),
      ),

      // ── messages ──────────────────────────
      Expanded(
        child: ListView.builder(
          controller: _scroll,
          padding: const EdgeInsets.fromLTRB(14, 8, 14, 8),
          itemCount: messages.length + (alfred.thinking ? 1 : 0),
          itemBuilder: (_, i) {
            if (i == messages.length) {
              return const Align(
                alignment: Alignment.centerLeft,
                child: Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: _TypingBubble(),
                ),
              );
            }
            final m = messages[i];
            final isUser = m.role == 'user';
            return Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: Align(
                alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                child: Column(
                  crossAxisAlignment: isUser
                      ? CrossAxisAlignment.end
                      : CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(bottom: 5, left: 4, right: 4),
                      child: Text(
                        isUser ? userName.toUpperCase() : 'ALFRED',
                        style: TextStyle(
                          fontFamily: 'monospace', fontSize: 8, letterSpacing: 2,
                          color: isUser ? BC.gold : BC.cyan,
                        ),
                      ),
                    ),
                    Container(
                      constraints: BoxConstraints(
                        maxWidth: MediaQuery.of(ctx).size.width * 0.78,
                      ),
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
                      decoration: BoxDecoration(
                        color: isUser ? BC.goldDim : BC.cyanDim,
                        border: Border.all(
                          color: isUser ? BC.goldBorder : BC.cyan.withValues(alpha: 0.18),
                        ),
                        borderRadius: BorderRadius.only(
                          topLeft:     const Radius.circular(14),
                          topRight:    const Radius.circular(14),
                          bottomLeft:  Radius.circular(isUser ? 14 : 3),
                          bottomRight: Radius.circular(isUser ? 3 : 14),
                        ),
                      ),
                      child: Text(m.content, style: const TextStyle(
                        fontFamily: 'monospace', fontSize: 13,
                        color: BC.txt, height: 1.55,
                      )),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),

      // ── input bar ────────────────────────
      Container(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 24),
        decoration: BoxDecoration(
          color: BC.panel.withValues(alpha: 0.92),
          border: const Border(top: BorderSide(color: Color(0x1200D8FF))),
        ),
        child: Row(children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: BC.bg,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: BC.cyan.withValues(alpha: 0.22)),
              ),
              child: TextField(
                controller: _ctrl,
                style: const TextStyle(
                  fontFamily: 'monospace', fontSize: 13, color: BC.txt,
                ),
                decoration: InputDecoration(
                  hintText: 'Issue command to Alfred…',
                  hintStyle: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: BC.txtDim.withValues(alpha: 0.6),
                  ),
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 14, vertical: 12,
                  ),
                ),
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
              ),
            ),
          ),
          const SizedBox(width: 10),
          // ── Mic button ──
          GestureDetector(
            onTap: _toggleListen,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 50, height: 50,
              decoration: BoxDecoration(
                color: _listening
                    ? BC.red.withValues(alpha: 0.18)
                    : BC.elevated,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: _listening
                      ? BC.red.withValues(alpha: 0.7)
                      : BC.border,
                ),
                boxShadow: _listening
                    ? [BoxShadow(
                        color: BC.red.withValues(alpha: 0.35),
                        blurRadius: 14,
                      )]
                    : null,
              ),
              child: Icon(
                _listening ? Icons.mic : Icons.mic_none_rounded,
                color: _listening ? BC.red : BC.txtDim,
                size: 20,
              ),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: alfred.thinking ? null : _send,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 50, height: 50,
              decoration: BoxDecoration(
                color: alfred.thinking ? BC.elevated : BC.cyanDim,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: alfred.thinking ? BC.border : BC.cyan.withValues(alpha: 0.4),
                ),
                boxShadow: alfred.thinking
                  ? null
                  : [BoxShadow(
                      color: BC.cyan.withValues(alpha: 0.2), blurRadius: 10,
                    )],
              ),
              child: const Icon(Icons.send_rounded, color: BC.cyan, size: 18),
            ),
          ),
        ]),
      ),
    ])),
  );
  }
}

// ── Typing indicator ──────────────────────
class _TypingBubble extends StatefulWidget {
  const _TypingBubble();
  @override
  State<_TypingBubble> createState() => _TypingBubbleState();
}

class _TypingBubbleState extends State<_TypingBubble>
    with SingleTickerProviderStateMixin {
  late AnimationController _c;
  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 1400),
    )..repeat();
  }
  @override
  void dispose() { _c.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext ctx) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
    decoration: BoxDecoration(
      color: BC.cyanDim,
      border: Border.all(color: BC.cyan.withValues(alpha: 0.18)),
      borderRadius: const BorderRadius.only(
        topLeft:    Radius.circular(14),
        topRight:   Radius.circular(14),
        bottomRight: Radius.circular(14),
      ),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (i) => AnimatedBuilder(
        animation: _c,
        builder: (_, __) {
          final t = ((_c.value * 3) - i).clamp(0.0, 1.0);
          final y = math.sin(t * math.pi) * 5;
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 2.5),
            child: Transform.translate(
              offset: Offset(0, -y),
              child: Container(
                width: 7, height: 7,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: BC.cyan.withValues(alpha: 0.4 + t * 0.6),
                  boxShadow: [BoxShadow(
                    color: BC.cyan.withValues(alpha: t * 0.7), blurRadius: 4,
                  )],
                ),
              ),
            ),
          );
        },
      )),
    ),
  );
}

