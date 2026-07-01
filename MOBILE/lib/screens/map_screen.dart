import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/bc.dart';
import '../core/auth_provider.dart';
import '../core/cfg_provider.dart';
import '../core/socket_service.dart';
import '../modules/map/map_provider.dart';
import '../widgets/common_widgets.dart';

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});
  @override
  ConsumerState<MapScreen> createState() => _MapState();
}

class _MapState extends ConsumerState<MapScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulse;
  Timer? _pollTimer;
  Timer? _syncTimer;
  StreamSubscription? _socketSub;
  StreamSubscription? _mapLayoutSub;
  DateTime? _lastSync;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this, duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    Future.microtask(() async {
      await ref.read(mapProvider.notifier).loadAll();
      if (mounted) setState(() => _lastSync = DateTime.now());
    });
    // Poll device status every 2s for near-realtime ON/OFF updates
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      if (!mounted) return;
      ref.read(mapProvider.notifier).refreshDevices();
    });
    // Full layout+position sync every 5s
    _syncTimer = Timer.periodic(const Duration(seconds: 5), (_) async {
      if (!mounted) return;
      await ref.read(mapProvider.notifier).loadAll(silent: true);
      if (mounted) setState(() => _lastSync = DateTime.now());
    });
    _connectSocketListener();
  }

  void _connectSocketListener() {
    final svc = ref.read(socketServiceProvider);
    _socketSub = svc.onDeviceUpdate.listen((data) {
      if (!mounted) return;
      ref.read(mapProvider.notifier).applyDeviceUpdate(data);
      setState(() => _lastSync = DateTime.now());
    });
    _mapLayoutSub = svc.onMapLayoutUpdate.listen((data) {
      if (!mounted) return;
      final updatedFloorId = data['floor_id']?.toString();
      final currentFloorId = ref.read(mapProvider).currentFloorId;
      if (updatedFloorId == null || updatedFloorId == currentFloorId) {
        ref.read(mapProvider.notifier).loadFloorLayout();
        setState(() => _lastSync = DateTime.now());
      }
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _syncTimer?.cancel();
    _socketSub?.cancel();
    _mapLayoutSub?.cancel();
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext ctx) {
    final mapState = ref.watch(mapProvider);
    final base = ref.watch(cfgProvider);
    final blueprintUrl = '$base/api/map/blueprint/${mapState.currentFloorId}';

    return Scaffold(
    backgroundColor: BC.bg,
    body: SafeArea(child: Column(children: [
      // header
      Container(
        padding: const EdgeInsets.fromLTRB(16, 10, 12, 10),
        decoration: const BoxDecoration(
          color: BC.panel,
          border: Border(bottom: BorderSide(color: BC.border)),
        ),
        child: Row(children: [
          const Text('🗺️', style: TextStyle(fontSize: 20)),
          const SizedBox(width: 10),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('FACILITY MAP', style: TextStyle(
              fontFamily: 'monospace', fontSize: 13, color: BC.gold,
              letterSpacing: 3, fontWeight: FontWeight.bold,
            )),
            Text(
              _lastSync != null
                ? 'SYNCED ${_lastSync!.hour.toString().padLeft(2,'0')}:${_lastSync!.minute.toString().padLeft(2,'0')}:${_lastSync!.second.toString().padLeft(2,'0')}'
                : 'BLUEPRINT OVERLAY',
              style: const TextStyle(
                fontFamily: 'monospace', fontSize: 7,
                color: BC.txtDim, letterSpacing: 2,
              ),
            ),
          ]),
          const Spacer(),
          GestureDetector(
            onTap: () => ref.read(mapProvider.notifier).loadAll(),
            child: Container(
              padding: const EdgeInsets.all(7),
              decoration: BoxDecoration(
                border: Border.all(color: BC.border),
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Icon(Icons.refresh_rounded, color: BC.txtDim, size: 17),
            ),
          ),
        ]),
      ),
      // floor tabs
      if (mapState.floors.isNotEmpty)
        Container(
          height: 38,
          decoration: const BoxDecoration(
            color: BC.panel,
            border: Border(bottom: BorderSide(color: BC.border)),
          ),
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            itemCount: mapState.floors.length,
            itemBuilder: (_, i) {
              final active = i == mapState.floorIndex;
              return GestureDetector(
                onTap: () => ref.read(mapProvider.notifier).selectFloor(i),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  margin: const EdgeInsets.only(right: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                  decoration: BoxDecoration(
                    color: active ? BC.goldDim : Colors.transparent,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: active ? BC.goldBorder : BC.border),
                  ),
                  child: Text(
                    (mapState.floors[i]['name'] ?? 'FLOOR ${i + 1}').toString().toUpperCase(),
                    style: TextStyle(
                      fontFamily: 'monospace', fontSize: 9, letterSpacing: 2,
                      color: active ? BC.gold : BC.txtDim,
                      fontWeight: active ? FontWeight.bold : FontWeight.normal,
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      // map area
      Expanded(
        child: mapState.loading
          ? const BcLoader()
          : mapState.floors.isEmpty
            ? Center(
                child: Container(
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: BC.panel.withValues(alpha: 0.9),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: BC.border),
                  ),
                  child: const Text(
                    'No floors available from backend.',
                    style: TextStyle(color: BC.txtDim),
                    textAlign: TextAlign.center,
                  ),
                ),
              )
            : InteractiveViewer(
                minScale: 0.5,
                maxScale: 4.0,
                boundaryMargin: const EdgeInsets.all(80),
                child: _MapCanvas(
                  blueprintUrl: blueprintUrl,
                  hasBlueprint: mapState.hasBlueprint,
                  authHeaders: ref.read(authProvider).bearerHeader,
                  devices: mapState.floorDevices,
                  rooms: mapState.layoutRooms,
                  pulse: _pulse,
                  onTap: (device) => ref.read(mapProvider.notifier).toggleDevice(
                    Map<String, dynamic>.from(device as Map),
                  ),
                  onRoomSelected: (roomId, roomName) {
                    ref.read(mapProvider.notifier).selectRoom(roomId, roomName);
                  },
                ),
              ),
      ),
      _RoomDevicePanel(
        rooms: mapState.layoutRooms,
        devices: mapState.floorDevices,
        onToggle: (device) => ref.read(mapProvider.notifier).toggleDevice(
          Map<String, dynamic>.from(device as Map),
        ),
      ),
      // legend
      _MapLegend(devices: mapState.floorDevices),
    ])),
  );
  }
}

// ── Map Canvas ─────────────────────────────
class _MapCanvas extends StatefulWidget {
  final String blueprintUrl;
  final bool hasBlueprint;
  final Map<String, String> authHeaders;
  final List devices;
  final List rooms;
  final AnimationController pulse;
  final Function(dynamic) onTap;
  final Function(String, String)? onRoomSelected;
  const _MapCanvas({
    required this.blueprintUrl,
    required this.hasBlueprint,
    required this.authHeaders,
    required this.devices,
    required this.rooms,
    required this.pulse,
    required this.onTap,
    this.onRoomSelected,
  });

  @override
  State<_MapCanvas> createState() => _MapCanvasState();
}

class _MapCanvasState extends State<_MapCanvas> {
  Size? _naturalSize;

  @override
  void initState() {
    super.initState();
    if (widget.hasBlueprint) _loadNaturalSize();
  }

  @override
  void didUpdateWidget(_MapCanvas old) {
    super.didUpdateWidget(old);
    if ((old.blueprintUrl != widget.blueprintUrl ||
            old.hasBlueprint != widget.hasBlueprint) &&
        widget.hasBlueprint) {
      _naturalSize = null;
      _loadNaturalSize();
    }
  }

  void _loadNaturalSize() {
    final provider = NetworkImage(
      widget.blueprintUrl,
      headers: {'Cache-Control': 'no-cache', ...widget.authHeaders},
    );
    final stream = provider.resolve(const ImageConfiguration());
    stream.addListener(ImageStreamListener(
      (info, _) {
        if (mounted) {
          setState(() => _naturalSize = Size(
            info.image.width.toDouble(),
            info.image.height.toDouble(),
          ));
        }
      },
      onError: (_, __) {},
    ));
  }

  void _selectRoomAtPoint(double x, double y, List rooms, double width, double height) {
    for (final room in rooms) {
      final points = room['points'] as List?;
      if (points == null || points.isEmpty) continue;
      
      final path = Path();
      for (int i = 0; i < points.length; i++) {
        final pt = points[i] as Map?;
        if (pt == null) continue;
        final xPct = (pt['xPct'] as num? ?? pt['x'] as num? ?? 0).toDouble();
        final yPct = (pt['yPct'] as num? ?? pt['y'] as num? ?? 0).toDouble();
        final px = xPct / 100 * width;
        final py = yPct / 100 * height;
        
        if (i == 0) {
          path.moveTo(px, py);
        } else {
          path.lineTo(px, py);
        }
      }
      path.close();
      
      if (path.contains(Offset(x, y))) {
        final roomId = room['id']?.toString() ?? '';
        final roomName = room['name'] as String? ?? '';
        if (roomId.isNotEmpty && widget.onRoomSelected != null) {
          debugPrint('[Map] Room selected: $roomName ($roomId)');
          widget.onRoomSelected!(roomId, roomName);
        }
        return;
      }
    }
  }

  /// Returns the rect that BoxFit.contain would render the image into.
  Rect _imageRect(double containerW, double containerH) {
    final nat = _naturalSize;
    if (nat == null) return Rect.fromLTWH(0, 0, containerW, containerH);
    final scale = math.min(containerW / nat.width, containerH / nat.height);
    final w = nat.width * scale;
    final h = nat.height * scale;
    return Rect.fromLTWH(
      (containerW - w) / 2,
      (containerH - h) / 2,
      w, h,
    );
  }

  @override
  Widget build(BuildContext ctx) => LayoutBuilder(
    builder: (_, constraints) {
      final w = constraints.maxWidth;
      final h = constraints.maxHeight.isInfinite ? 400.0 : constraints.maxHeight;
      // Compute exact rect where the image is rendered (accounts for letterboxing).
      final imageRect = widget.hasBlueprint
          ? _imageRect(w, h)
          : Rect.fromLTWH(0, 0, w, h);
      final ow = imageRect.width;
      final oh = imageRect.height;
      return SizedBox(
        width: w, height: h,
        child: Stack(children: [
          Positioned.fill(
            child: !widget.hasBlueprint
              ? _NoBlueprint(
                  devices: widget.devices,
                  rooms: widget.rooms,
                  pulse: widget.pulse,
                  onTap: widget.onTap,
                )
              : Image.network(
                  widget.blueprintUrl,
                  fit: BoxFit.contain,
                  headers: {'Cache-Control': 'no-cache', ...widget.authHeaders},
                  loadingBuilder: (_, child, progress) {
                    if (progress == null) return child;
                    return Center(child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        CircularProgressIndicator(
                          value: progress.expectedTotalBytes != null
                            ? progress.cumulativeBytesLoaded / progress.expectedTotalBytes!
                            : null,
                          color: BC.gold, strokeWidth: 2,
                        ),
                        const SizedBox(height: 10),
                        const Text('LOADING BLUEPRINT...', style: TextStyle(
                          fontFamily: 'monospace', fontSize: 9,
                          color: BC.txtDim, letterSpacing: 2,
                        )),
                      ],
                    ));
                  },
                  errorBuilder: (_, __, ___) => _NoBlueprint(
                    devices: widget.devices,
                    rooms: widget.rooms,
                    pulse: widget.pulse,
                    onTap: widget.onTap,
                  ),
                ),
          ),
          // Room polygons — positioned relative to the actual image rect,
          // not the full container, so they align with the blueprint correctly.
          if (widget.rooms.isNotEmpty)
            Positioned(
              left: imageRect.left,
              top: imageRect.top,
              width: ow,
              height: oh,
              child: GestureDetector(
                onDoubleTapDown: (details) {
                  final localX = details.localPosition.dx;
                  final localY = details.localPosition.dy;
                  _selectRoomAtPoint(localX, localY, widget.rooms, ow, oh);
                },
                child: CustomPaint(
                  painter: _RoomPainter(rooms: widget.rooms, width: ow, height: oh),
                  size: Size(ow, oh),
                  isComplex: true,
                  willChange: false,
                ),
              ),
            ),
          // Device icons — offset by image rect origin so they sit on the blueprint.
          ...widget.devices.map((d) {
            final mx = (d['map_x'] ?? 0.0).toDouble();
            final my = (d['map_y'] ?? 0.0).toDouble();
            if (mx == 0 && my == 0) return const SizedBox.shrink();
            final x = mx / 100 * ow + imageRect.left;
            final y = my / 100 * oh + imageRect.top;
            return Positioned(
              left: x - 18, top: y - 18,
              child: _MapDeviceIcon(
                device: d, pulse: widget.pulse, onTap: () => widget.onTap(d),
              ),
            );
          }),
        ]),
      );
    },
  );
}

// ── No Blueprint fallback ──────────────────
class _NoBlueprint extends StatelessWidget {
  final List devices;
  final List rooms;
  final AnimationController pulse;
  final Function(dynamic) onTap;
  const _NoBlueprint({
    required this.devices,
    required this.rooms,
    required this.pulse,
    required this.onTap,
  });

  @override
  Widget build(BuildContext ctx) {
    final devWithPos = devices
        .where((d) =>
            d['map_x'] != null &&
            d['map_y'] != null &&
            (d['map_x'] != 0 || d['map_y'] != 0))
        .toList();
    return Container(
      decoration: BoxDecoration(
        color: BC.card,
        border: Border.all(color: BC.border),
        borderRadius: BorderRadius.circular(8),
      ),
      child: devWithPos.isEmpty
        ? const Center(child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('🏗️', style: TextStyle(fontSize: 48)),
              SizedBox(height: 12),
              Text('NO BLUEPRINT UPLOADED', style: TextStyle(
                fontFamily: 'monospace', fontSize: 10,
                color: BC.txtDim, letterSpacing: 3,
              )),
              SizedBox(height: 6),
              Text('Upload blueprint on web dashboard', style: TextStyle(
                fontFamily: 'monospace', fontSize: 9, color: BC.txtDim,
              )),
            ],
          ))
        : LayoutBuilder(builder: (_, c) => Stack(
            children: [
              CustomPaint(
                painter: _MapGridPainter(),
                size: Size(c.maxWidth, c.maxHeight),
              ),
              // ✅ Draw room polygons in fallback
              if (rooms.isNotEmpty)
                CustomPaint(
                  painter: _RoomPainter(rooms: rooms, width: c.maxWidth, height: c.maxHeight),
                  isComplex: true,
                  willChange: false,
                ),
              ...devWithPos.map((d) {
                final mx = (d['map_x'] ?? 0.0).toDouble();
                final my = (d['map_y'] ?? 0.0).toDouble();
                final x  = mx / 100 * c.maxWidth;
                final y  = my / 100 * c.maxHeight;
                return Positioned(
                  left: x - 18, top: y - 18,
                  child: _MapDeviceIcon(
                    device: d, pulse: pulse, onTap: () => onTap(d),
                  ),
                );
              }),
            ],
          )),
    );
  }
}

// ── Room Painter ───────────────────────────
class _RoomPainter extends CustomPainter {
  final List rooms;
  final double width;
  final double height;

  _RoomPainter({required this.rooms, required this.width, required this.height});

  @override
  void paint(Canvas canvas, Size size) {
    for (final room in rooms) {
      final points = room['points'] as List?;
      final color = room['color'] as String?;
      final name = room['name'] as String?;
      
      if (points == null || points.isEmpty) continue;

      // Parse color string (e.g., "rgba(253,185,19,0.22)")
      final fillColor = _parseColor(color ?? 'rgba(253,185,19,0.22)');
      final strokeColor = fillColor.withValues(alpha: 0.75);

      // Convert percentage points to canvas coordinates
      final path = Path();
      for (int i = 0; i < points.length; i++) {
        final pt = points[i] as Map?;
        if (pt == null) continue;
        final xPct = (pt['xPct'] as num? ?? pt['x'] as num? ?? 0).toDouble();
        final yPct = (pt['yPct'] as num? ?? pt['y'] as num? ?? 0).toDouble();
        final x = xPct / 100 * width;
        final y = yPct / 100 * height;
        
        if (i == 0) {
          path.moveTo(x, y);
        } else {
          path.lineTo(x, y);
        }
      }
      path.close();

      // Draw fill
      canvas.drawPath(
        path,
        Paint()
          ..color = fillColor
          ..style = PaintingStyle.fill,
      );

      // Draw stroke
      canvas.drawPath(
        path,
        Paint()
          ..color = strokeColor
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5,
      );

      // Draw room name at center
      if (name != null && name.isNotEmpty) {
        // Calculate centroid
        double cx = 0, cy = 0;
        for (final pt in points) {
          final p = pt as Map?;
          if (p != null) {
            cx += (p['xPct'] as num? ?? p['x'] as num? ?? 0).toDouble();
            cy += (p['yPct'] as num? ?? p['y'] as num? ?? 0).toDouble();
          }
        }
        cx = (cx / points.length) / 100 * width;
        cy = (cy / points.length) / 100 * height;

        final textPainter = TextPainter(
          text: TextSpan(
            text: name,
            style: const TextStyle(
              color: Color.fromARGB(200, 253, 185, 19),
              fontSize: 10,
              fontWeight: FontWeight.bold,
              fontFamily: 'monospace',
            ),
          ),
          textDirection: TextDirection.ltr,
        );
        textPainter.layout();
        textPainter.paint(
          canvas,
          Offset(cx - textPainter.width / 2, cy - textPainter.height / 2),
        );
      }
    }
  }

  Color _parseColor(String colorStr) {
    // Parse "rgba(R,G,B,A)" format
    final match = RegExp(r'rgba?\((\d+),(\d+),(\d+),?([\d.]+)?\)').firstMatch(colorStr);
    if (match != null) {
      final r = int.parse(match.group(1)!);
      final g = int.parse(match.group(2)!);
      final b = int.parse(match.group(3)!);
      final a = match.group(4) != null ? double.parse(match.group(4)!) : 1.0;
      return Color.fromARGB((a * 255).toInt(), r, g, b);
    }
    return const Color(0xFFfdB913); // default gold
  }

  @override
  bool shouldRepaint(_RoomPainter old) => old.rooms != rooms;
}

class _MapGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0x0FFFBE00)
      ..strokeWidth = 0.5;
    const step = 30.0;
    for (double x = 0; x < size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }
  @override
  bool shouldRepaint(_) => false;
}

class _RoomDevicePanel extends StatelessWidget {
  final List rooms;
  final List devices;
  final Function(dynamic) onToggle;
  const _RoomDevicePanel({
    required this.rooms,
    required this.devices,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext ctx) {
    final byRoom = <String, List<dynamic>>{};
    for (final d in devices) {
      final room = (d['room'] ?? 'UNASSIGNED').toString().trim();
      byRoom.putIfAbsent(room.isEmpty ? 'UNASSIGNED' : room, () => []).add(d);
    }

    final roomOrder = <String>[
      ...rooms.map((r) => (r['name'] ?? '').toString()).where((n) => n.isNotEmpty),
      ...byRoom.keys.where((k) => !rooms.any((r) => (r['name'] ?? '').toString() == k)),
    ];

    return Container(
      height: 160,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      decoration: const BoxDecoration(
        color: BC.panel,
        border: Border(top: BorderSide(color: BC.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('ROOMS & DEVICES', style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 9,
            color: BC.gold,
            letterSpacing: 2,
            fontWeight: FontWeight.bold,
          )),
          const SizedBox(height: 8),
          SizedBox(
            height: 26,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: roomOrder.map((name) {
                final count = byRoom[name]?.length ?? 0;
                return Container(
                  margin: const EdgeInsets.only(right: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: BC.elevated,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: BC.border),
                  ),
                  child: Text(
                    '$name ($count)',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 9,
                      color: BC.txt,
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: ListView(
              children: devices.map((d) => _DeviceListRow(device: d, onTap: () => onToggle(d))).toList(),
            ),
          ),
        ],
      ),
    );
  }
}

class _DeviceListRow extends StatelessWidget {
  final dynamic device;
  final VoidCallback onTap;
  const _DeviceListRow({required this.device, required this.onTap});

  static const _icons = {
    'light': '💡',
    'fan': '🌀',
    'ac': '❄️',
    'camera': '📷',
    'tv': '📺',
    'temp': '🌡️',
  };

  String get _emoji {
    final name = (device['name'] ?? '').toString().toLowerCase();
    for (final key in _icons.keys) {
      if (name.contains(key)) return _icons[key]!;
    }
    return '🔌';
  }

  @override
  Widget build(BuildContext ctx) {
    final isOn = device['is_on'] == true;
    final room = (device['room'] ?? 'UNASSIGNED').toString();
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: BC.card,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: BC.border),
        ),
        child: Row(
          children: [
            Text(_emoji, style: const TextStyle(fontSize: 16)),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '${device['name'] ?? 'Device'}  ·  $room',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 10,
                  color: BC.txt,
                ),
              ),
            ),
            Text(
              isOn ? 'ON' : 'OFF',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 9,
                color: isOn ? BC.green : BC.txtDim,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Device icon on map ─────────────────────
class _MapDeviceIcon extends StatelessWidget {
  final dynamic device;
  final AnimationController pulse;
  final VoidCallback onTap;
  const _MapDeviceIcon({
    required this.device, required this.pulse, required this.onTap,
  });

  static const _icons = {
    'light': '💡', 'lamp': '💡', 'den': '💡',
    'fan': '🌀', 'quat': '🌀',
    'ac': '❄️', 'air': '❄️', 'mayl': '❄️', 'may lanh': '❄️',
    'camera': '📷', 'cam': '📷',
    'door': '🚪', 'cua': '🚪',
    'tv': '📺', 'temp': '🌡️',
  };

  String _normalize(String value) {
    var normalized = value.toLowerCase().trim();
    const replacements = {
      'đ': 'd',
      'ð': 'd',
      'máy lạnh': 'may lanh',
      'máy láº¡nh': 'may lanh',
      'quạt': 'quat',
      'quáº¡t': 'quat',
      'cửa': 'cua',
      'cá»­a': 'cua',
      'đèn': 'den',
    };
    replacements.forEach((source, target) {
      if (normalized.contains(source)) {
        normalized = normalized.replaceAll(source, target);
      }
    });
    if (normalized.contains('â') || normalized.contains('❄')) return '❄️';
    if (normalized.contains('🌡')) return '🌡️';
    if (normalized.contains('⚙')) return '⚙️';
    return normalized;
  }

  String get _emoji {
    final stored = _normalize((device['icon'] ?? '').toString());
    if (stored.isNotEmpty && stored != '⚙️') return stored;
    final n = _normalize((device['name'] ?? '').toString());
    for (final k in _icons.keys) { if (n.contains(k)) return _icons[k]!; }
    return '🔌';
  }

  Color get _color {
    switch (_emoji) {
      case '💡': return BC.gold;
      case '🌀': return BC.cyan;
      case '❄️': return const Color(0xFF40E0FF);
      case '📷': return BC.red;
      case '📺': return BC.purple;
      case '🌡️': return const Color(0xFFFF8844);
      default:   return BC.green;
    }
  }

  bool get _isSensor {
    final t = (device['type'] ?? device['device_type'] ?? '').toString().toLowerCase();
    return t == 'sensor';
  }

  String _formatVal(dynamic v) {
    if (v == null) return '—';
    final d = double.tryParse(v.toString());
    if (d == null) return v.toString();
    return d == d.truncateToDouble() ? d.toInt().toString() : d.toStringAsFixed(1);
  }

  String get _unit {
    final n = _normalize((device['name'] ?? '').toString());
    if (n.contains('temp') || n.contains('thermo') || n.contains('nhiet')) return '°C';
    if (n.contains('humid') || n.contains('am') || n.contains('doam')) return '%';
    if (n.contains('heart') || n.contains('pulse') || n.contains('bpm')) return 'BPM';
    if (n.contains('light') || n.contains('lux') || n.contains('sang')) return 'lux';
    return '';
  }

  @override
  Widget build(BuildContext ctx) {
    final isOn = device['is_on'] == true;
    final color = isOn ? _color : BC.txtDim;

    if (_isSensor) {
      final val = _formatVal(device['value']);
      final unit = _unit;
      return GestureDetector(
        onTap: onTap,
        child: AnimatedBuilder(
          animation: pulse,
          builder: (_, __) => Container(
            width: 44, height: 44,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(6),
              color: BC.bg.withValues(alpha: 0.90),
              border: Border.all(
                color: isOn ? color.withValues(alpha: 0.85) : BC.border,
                width: 1.2,
              ),
              boxShadow: isOn
                ? [BoxShadow(color: color.withValues(alpha: 0.35 + pulse.value * 0.1), blurRadius: 6)]
                : null,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(_emoji, style: const TextStyle(fontSize: 11, height: 1)),
                Text(val, style: TextStyle(
                  fontFamily: 'monospace', fontSize: 11,
                  color: color, fontWeight: FontWeight.bold, height: 1.1,
                )),
                if (unit.isNotEmpty)
                  Text(unit, style: const TextStyle(
                    fontFamily: 'monospace', fontSize: 7,
                    color: BC.txtDim, height: 1.1,
                  )),
              ],
            ),
          ),
        ),
      );
    }

    return GestureDetector(
      onTap: onTap,
      child: AnimatedBuilder(
        animation: pulse,
        builder: (_, __) => Stack(
          alignment: Alignment.center,
          children: [
            if (isOn)
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: 36 + pulse.value * 8,
                height: 36 + pulse.value * 8,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.transparent,
                  border: Border.all(
                    color: color.withValues(alpha: 0.3 - pulse.value * 0.2),
                    width: 1.5,
                  ),
                ),
              ),
            Container(
              width: 34, height: 34,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isOn ? color.withValues(alpha: 0.2) : BC.bg.withValues(alpha: 0.85),
                border: Border.all(
                  color: isOn ? color.withValues(alpha: 0.8) : BC.border,
                  width: isOn ? 1.5 : 1,
                ),
                boxShadow: isOn
                  ? [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 10)]
                  : null,
              ),
              child: Center(child: Text(_emoji, style: const TextStyle(fontSize: 16))),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Map legend ──────────────────────────────
class _MapLegend extends StatelessWidget {
  final List devices;
  const _MapLegend({required this.devices});

  @override
  Widget build(BuildContext ctx) {
    final on    = devices.where((d) => d['is_on'] == true).length;
    final total = devices.length;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: const BoxDecoration(
        color: BC.panel,
        border: Border(top: BorderSide(color: BC.border)),
      ),
      child: Row(children: [
        BcLegendDot(color: BC.green,   label: '$on ACTIVE'),
        const SizedBox(width: 14),
        BcLegendDot(color: BC.txtDim,  label: '${total - on} STANDBY'),
        const Spacer(),
        const Text('PINCH TO ZOOM', style: TextStyle(
          fontFamily: 'monospace', fontSize: 8,
          color: BC.txtDim, letterSpacing: 1.5,
        )),
        const SizedBox(width: 4),
        const Icon(Icons.zoom_in, color: BC.txtDim, size: 14),
      ]),
    );
  }
}

