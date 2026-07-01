import os, base64, json, re
from flask import Blueprint, request, jsonify, send_file, g
from app.extensions.limiter import limiter

map_bp = Blueprint('map', __name__, url_prefix='/api/map')
limiter.exempt(map_bp)

# BACKEND/static/blueprints/
BLUEPRINT_BASE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'static', 'blueprints')
os.makedirs(BLUEPRINT_BASE, exist_ok=True)

# ── Security helper ───────────────────────────────────────────

_FLOOR_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,20}$')


def _sanitize_floor_id(floor_id) -> str:
    """Sanitize floor_id to prevent path traversal attacks.
    Only alphanumeric chars, hyphens and underscores are allowed (max 20 chars).
    """
    sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '', str(floor_id))[:20]
    return sanitized if sanitized else '1'

# ── Per-user helpers ──────────────────────────────────────────
def _user_dir(user_id) -> str:
    d = os.path.join(BLUEPRINT_BASE, f'user_{user_id}')
    os.makedirs(d, exist_ok=True)
    return d

def _meta_file(user_id) -> str:
    return os.path.join(_user_dir(user_id), 'floors_meta.json')


def _sort_floor_ids(floor_ids):
    return sorted(
        [str(fid) for fid in floor_ids],
        key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x),
    )


def _normalize_meta_one_device_one_floor(meta: dict):
    """Ensure each device exists in map_cache of only one floor.

    Priority:
    1) floor -> rooms -> devices associations
    2) first map_cache appearance by floor order
    """
    if not isinstance(meta, dict):
        return {}, False

    normalized = dict(meta)
    changed = False
    owner_floor_by_device = {}
    floor_ids = _sort_floor_ids(normalized.keys())

    # Priority 1: room-device ownership.
    for fid in floor_ids:
        floor_info = normalized.get(fid) or {}
        for room in (floor_info.get('rooms') or []):
            for dev in (room.get('devices') or []):
                if not isinstance(dev, dict):
                    continue
                name = str(dev.get('name', '')).strip()
                if name and name not in owner_floor_by_device:
                    owner_floor_by_device[name] = fid

    # Priority 2: first cache appearance ownership.
    for fid in floor_ids:
        floor_info = normalized.get(fid) or {}
        cache = floor_info.get('map_cache') or {}
        if not isinstance(cache, dict):
            continue
        for name in cache.keys():
            key = str(name).strip()
            if key and key not in owner_floor_by_device:
                owner_floor_by_device[key] = fid

    # Remove duplicate cache entries from non-owner floors.
    for fid in floor_ids:
        floor_info = normalized.get(fid) or {}
        cache = floor_info.get('map_cache') or {}
        if not isinstance(cache, dict):
            cache = {}
            floor_info['map_cache'] = cache
            normalized[fid] = floor_info
            changed = True

        remove_keys = []
        for name in list(cache.keys()):
            key = str(name).strip()
            owner = owner_floor_by_device.get(key)
            if owner and owner != fid:
                remove_keys.append(name)

        if remove_keys:
            for k in remove_keys:
                cache.pop(k, None)
            floor_info['map_cache'] = cache
            normalized[fid] = floor_info
            changed = True

    return normalized, changed

def _discover_floor_ids_from_files(user_id):
    ids = []
    try:
        for name in os.listdir(_user_dir(user_id)):
            if not name.startswith('floor_') or not name.endswith('.png'):
                continue
            floor_id = name[len('floor_'):-len('.png')].strip()
            if floor_id:
                ids.append(floor_id)
    except Exception:
        pass
    return sorted(set(ids), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))

def _load_meta(user_id):
    try:
        p = _meta_file(user_id)
        if os.path.exists(p):
            with open(p) as f:
                loaded = json.load(f)
            normalized, changed = _normalize_meta_one_device_one_floor(loaded)
            if changed:
                _save_meta(user_id, normalized)
            return normalized
    except Exception:
        pass
    return {}

def _save_meta(user_id, data):
    with open(_meta_file(user_id), 'w') as f:
        json.dump(data, f)

def _blueprint_path(user_id, floor_id) -> str:
    return os.path.join(_user_dir(user_id), f'floor_{floor_id}.png')

# ── Require auth helper ───────────────────────────────────────
from app.presentation.api.auth_api import auth_required


@map_bp.route('/blueprint', methods=['POST'])
@limiter.exempt
@auth_required
def save_blueprint():
    user_id = g.current_user.id
    data = request.get_json()
    floor_id   = _sanitize_floor_id(data.get('floor_id', '1'))
    floor_name = data.get('floor_name', f'FLOOR {floor_id}')
    image_b64  = data.get('image_base64', '')
    map_cache  = data.get('map_cache', {})
    rooms      = data.get('rooms', [])
    if not image_b64:
        return jsonify({'success': False, 'error': 'No image'}), 400
    # Hard cap: ~6 MB raw image → ≤8 MB base64
    if len(image_b64) > 8 * 1024 * 1024:
        return jsonify({'success': False, 'error': 'Image too large (max ~6 MB)'}), 413
    if ',' in image_b64:
        image_b64 = image_b64.split(',', 1)[1]
    fpath = _blueprint_path(user_id, floor_id)
    try:
        with open(fpath, 'wb') as f:
            f.write(base64.b64decode(image_b64))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    meta = _load_meta(user_id)
    old = meta.get(floor_id, {})
    meta[floor_id] = {
        'id': floor_id,
        'name': floor_name,
        'map_cache': map_cache if isinstance(map_cache, dict) else old.get('map_cache', {}),
        'rooms': rooms if isinstance(rooms, list) else old.get('rooms', []),
    }
    _save_meta(user_id, meta)
    return jsonify({'success': True})

@map_bp.route('/floors', methods=['GET'])
@limiter.exempt
@auth_required
def get_floors():
    user_id = g.current_user.id
    meta = _load_meta(user_id)
    discovered_ids = _discover_floor_ids_from_files(user_id)

    all_ids = set(meta.keys())
    all_ids.update(discovered_ids)

    result = []
    for fid in _sort_floor_ids(all_ids):
        info = meta.get(str(fid), {})
        fpath = _blueprint_path(user_id, fid)
        result.append({
            'id': str(fid),
            'name': info.get('name', f'FLOOR {fid}'),
            'has_blueprint': os.path.exists(fpath),
            'device_count': len((info.get('map_cache') or {}).keys()),
        })

    return jsonify({'success': True, 'data': result})

@map_bp.route('/blueprint/<floor_id>', methods=['GET'])
@limiter.exempt
@auth_required
def get_blueprint(floor_id):
    floor_id = _sanitize_floor_id(floor_id)
    fpath = _blueprint_path(g.current_user.id, floor_id)
    if not os.path.exists(fpath):
        return jsonify({'success': False, 'error': 'No blueprint'}), 404
    return send_file(fpath, mimetype='image/png')


@map_bp.route('/layout/<floor_id>', methods=['GET'])
@limiter.exempt
@auth_required
def get_floor_layout(floor_id):
    floor_id = _sanitize_floor_id(floor_id)
    user_id = g.current_user.id
    meta = _load_meta(user_id)
    info = meta.get(str(floor_id), {})
    rooms = info.get('rooms', [])

    # Fallback: only for floor "1" (the default floor) — if floors_meta.json has
    # no rooms yet, seed from the MySQL rooms table so first-time users see their
    # rooms immediately.  Other floors start empty until the user draws them.
    if not rooms and str(floor_id) == '1':
        try:
            from app.infrastructure.persistence.models.rooms_model import RoomModel
            db_rooms = RoomModel.query.filter_by(user_id=user_id).all()
            if db_rooms:
                rooms = [
                    {
                        'id': r.id,
                        'name': r.name,
                        'color': r.color or 'rgba(253,185,19,0.22)',
                        'points': r.polygon_json,
                        'devices': [],
                    }
                    for r in db_rooms
                ]
        except Exception:
            rooms = []

    return jsonify({
        'success': True,
        'data': {
            'id': str(floor_id),
            'rooms': rooms,
            'map_cache': info.get('map_cache', {}),
        }
    })


@map_bp.route('/layout/<floor_id>', methods=['POST'])
@limiter.exempt
@auth_required
def save_floor_layout(floor_id):
    floor_id = _sanitize_floor_id(floor_id)
    user_id = g.current_user.id
    data = request.get_json(silent=True) or {}
    rooms = data.get('rooms', [])
    map_cache = data.get('map_cache', {})

    meta = _load_meta(user_id)
    old = meta.get(str(floor_id), {})
    meta[str(floor_id)] = {
        'id': str(floor_id),
        'name': old.get('name', f'FLOOR {floor_id}'),
        'rooms': rooms if isinstance(rooms, list) else old.get('rooms', []),
        'map_cache': map_cache if isinstance(map_cache, dict) else old.get('map_cache', {}),
    }
    _save_meta(user_id, meta)

    try:
        from app.extensions.socketio import socketio
        socketio.emit('map_layout_updated', {
            'floor_id': str(floor_id),
            'user_id': user_id,
        }, room=f'user_{user_id}')
    except Exception:
        pass

    return jsonify({'success': True})


@map_bp.route('/floor/<floor_id>', methods=['DELETE'])
@limiter.exempt
@auth_required
def delete_floor(floor_id):
    floor_id = _sanitize_floor_id(floor_id)
    user_id = g.current_user.id

    meta = _load_meta(user_id)

    # Prevent deleting the last floor
    if len(meta) <= 1 and floor_id in meta:
        return jsonify({'success': False, 'error': 'Cannot delete the last floor'}), 400

    # Remove from meta
    removed_from_meta = floor_id in meta
    meta.pop(floor_id, None)
    _save_meta(user_id, meta)

    # Remove blueprint PNG if exists
    fpath = _blueprint_path(user_id, floor_id)
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
        except Exception:
            pass

    if not removed_from_meta and not os.path.exists(_blueprint_path(user_id, floor_id)):
        return jsonify({'success': False, 'error': 'Floor not found'}), 404

    return jsonify({'success': True})


@map_bp.route('/floor', methods=['POST'])
@limiter.exempt
@auth_required
def create_floor():
    """Create a new floor and return a server-assigned sequential ID."""
    user_id = g.current_user.id
    data = request.get_json(silent=True) or {}
    floor_name = data.get('name', '').strip() or 'NEW FLOOR'

    meta = _load_meta(user_id)

    # Assign next sequential integer ID — consider both meta keys AND floor PNG files on disk
    # to avoid assigning an ID that already exists as a discovered floor
    ids_from_meta  = {int(k) for k in meta.keys() if str(k).isdigit()}
    ids_from_files = {int(fid) for fid in _discover_floor_ids_from_files(user_id) if str(fid).isdigit()}
    existing_ids   = ids_from_meta | ids_from_files
    next_id = str(max(existing_ids) + 1) if existing_ids else '1'

    meta[next_id] = {
        'id': next_id,
        'name': floor_name,
        'map_cache': {},
        'rooms': [],
    }
    _save_meta(user_id, meta)

    return jsonify({'success': True, 'data': {'id': next_id, 'name': floor_name}})


