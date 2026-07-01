# app/usecases/ai_usecase.py
# ============================================================
# Alfred AI Use Case — Real-time DB Lookup Architecture
# Không đoán, không hardcode — mọi quyết định dựa trên DB thực tế
# ============================================================
from datetime import datetime
import json
import logging
import re
import time
import unicodedata

logger = logging.getLogger(__name__)


class AIUseCase:
    def __init__(self, ai_service, alert_usecase, mqtt_publisher, realtime_notifier,
                 device_usecase=None, sensor_usecase=None, room_usecase=None,
                 alfred_ai_service=None, email_notifier=None):
        self.ai_service        = ai_service
        self.alfred_ai_service = alfred_ai_service   # Gemini — optional
        self.alert            = alert_usecase
        self.mqtt             = mqtt_publisher
        self.realtime         = realtime_notifier
        self.device_usecase   = device_usecase
        self.sensor_usecase   = sensor_usecase
        self.room_usecase     = room_usecase
        self.email_notifier   = email_notifier
        # Pending actions chờ xác nhận, lưu theo user_id để không rò trạng thái giữa users.
        self._pending_actions: dict = {}
        # House state cache (user_id → {data, ts}) — TTL 10s to avoid DB query on every message
        self._house_cache: dict = {}

    def _get_pending_action(self, user_id=None) -> dict | None:
        key = user_id if user_id is not None else "_anon"
        pending = self._pending_actions.get(key)
        if not pending:
            return None
        # Auto-expire pending action to avoid stale accidental confirmations.
        if time.time() - pending.get("created_at", 0) > 90:
            self._pending_actions.pop(key, None)
            return None
        return pending

    def _set_pending_action(self, payload: dict, user_id=None):
        key = user_id if user_id is not None else "_anon"
        payload = dict(payload)
        payload["created_at"] = time.time()
        self._pending_actions[key] = payload

    def _clear_pending_action(self, user_id=None):
        key = user_id if user_id is not None else "_anon"
        self._pending_actions.pop(key, None)

    # ─────────────────────────────────────────
    # PRIVATE: Query real-time data từ DB
    # ─────────────────────────────────────────
    def _get_realtime_house(self, context_data: dict = None, user_id=None) -> dict:
        """
        Lấy toàn bộ trạng thái nhà từ DB theo thời gian thực.
        Cache TTL 10s per user to avoid redundant DB queries on every chat message.
        Trả về:
          devices: [{id, name, code, is_on, value, room_name, room_id, control_types}]
          rooms:   [{id, name, floor, device_names, devices}]
          floors:  [{name, room_names}]
        """
        _TTL = 10  # seconds
        now = time.time()
        cache_key = user_id
        cached = self._house_cache.get(cache_key)
        if cached and now - cached["ts"] < _TTL:
            return cached["data"]

        house = {"devices": [], "rooms": [], "floors": []}

        # ── Devices từ DB ──
        if self.device_usecase:
            raw = []
            for m in ["get_all_devices", "get_all_active", "get_all"]:
                if hasattr(self.device_usecase, m):
                    raw = getattr(self.device_usecase, m)(user_id=user_id)
                    break
            logger.debug("Loaded %d devices from DB (user_id=%s)", len(raw), user_id)
            for d in raw:
                if isinstance(d, dict):
                    house["devices"].append(d)
                    continue
                status    = getattr(d, "status", None)
                is_on     = bool(getattr(status, "is_on", False)) if status else False
                value     = getattr(status, "value", None) if status else None
                room_obj  = getattr(d, "room", None)
                room_name = getattr(room_obj, "name", None) if room_obj else None
                room_id   = getattr(room_obj, "id", None) if room_obj else None
                house["devices"].append({
                    "id":            getattr(d, "id", None),
                    "name":          getattr(d, "name", ""),
                    "code":          getattr(d, "code", None) or getattr(d, "name", ""),
                    "is_on":         is_on,
                    "value":         value,
                    "room_name":     room_name,
                    "room_id":       room_id,
                    "control_types": str(getattr(d, "control_types", "") or "").lower(),
                    "category":      str(getattr(d, "category", "") or "").lower(),
                    "icon":          getattr(d, "icon", None),
                })

        # ── Rooms từ frontend context (có floor info) ──
        if context_data and context_data.get("rooms"):
            house["rooms"] = context_data["rooms"]
        elif self.room_usecase and hasattr(self.room_usecase, "get_all_rooms"):
            house["rooms"] = self.room_usecase.get_all_rooms(user_id=user_id)

        # ── Floors từ frontend context ──
        if context_data and context_data.get("floors"):
            house["floors"] = context_data["floors"]

        # ── Log context ──
        logger.debug("Floor context: %s", [f['name'] for f in house['floors']])
        logger.debug("Room context: %s", [r['name']+'('+str(len(r.get('device_names',[])))+'dev)' for r in house['rooms']])
        self._house_cache[cache_key] = {"data": house, "ts": now}
        return house

    def _find_devices_in_room(self, house: dict, room_name: str) -> list:
        """Tìm tất cả device objects thuộc một phòng cụ thể (real-time từ DB)."""
        room_name_lower = room_name.lower()
        # Tìm room trong context
        target_room = next(
            (r for r in house["rooms"] if r.get("name", "").lower() == room_name_lower),
            None
        )
        if not target_room:
            return []
        device_names = target_room.get("device_names", [])
        # Map device_names → device objects từ DB
        result = []
        for dev in house["devices"]:
            if dev["name"] in device_names:
                result.append(dev)
        return result

    def _norm_text(self, value: str) -> str:
        """Normalize text for robust Vietnamese/English alias matching."""
        if value is None:
            return ""
        text = str(value).strip().lower()
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = text.replace("đ", "d")
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _is_controllable_device(self, dev: dict) -> bool:
        """Allow only controllable devices and exclude sensor/camera-like entries."""
        category = self._norm_text(dev.get("category", ""))
        if category in {"sensor", "camera"}:
            return False

        ctype_raw = dev.get("control_types", "")
        if isinstance(ctype_raw, (list, tuple, set)):
            ctype = " ".join(str(x) for x in ctype_raw)
        else:
            ctype = str(ctype_raw or "")
        ctype_norm = self._norm_text(ctype)

        # Explicitly-controllable signal from schema/control_types.
        if any(tok in ctype_norm for tok in ["switch", "toggle", "dimmer", "fan", "ac"]):
            return True

        # Fallback by category naming used in some datasets.
        if category in {"actuator", "switch", "fan", "light", "ac", "aircon", "door", "lock"}:
            return True

        return False

    def _device_matches_type(self, dev: dict, category: str) -> bool:
        """Match user-requested type (fan/light/ac) against device code/name aliases."""
        requested = self._norm_text(category)
        if not requested:
            return False

        # Direct category field match — catches devices like "debi" whose category="light"
        dev_category = self._norm_text(dev.get("category", ""))
        if dev_category == requested:
            return True

        aliases = {
            "fan": {"fan", "quat", "quạt", "ceiling fan", "blower"},
            "light": {"light", "den", "đèn", "lamp", "bulb"},
            "ac": {"ac", "aircon", "air con", "dieu hoa", "điều hòa", "may lanh", "máy lạnh", "lanh"},
        }

        tokens = aliases.get(requested, {requested})
        haystack = " ".join([
            dev_category,
            self._norm_text(dev.get("code", "")),
            self._norm_text(dev.get("name", "")),
            self._norm_text(dev.get("icon", "")),
        ]).strip()
        words = set(haystack.split())

        # Single-word aliases must match full words to avoid false positives,
        # e.g. "ac" must not match "actuator".
        for tok in tokens:
            t = self._norm_text(tok)
            if not t:
                continue
            if " " in t:
                if t in haystack:
                    return True
            else:
                if t in words:
                    return True
        return False

    def _find_devices_by_category(self, house: dict, category: str, room_name: str = None) -> list:
        """
        Tìm device theo CATEGORY từ DB — chính xác, không đoán.
        category: fan | ac | light | switch | sensor | camera | tv | speaker
        """
        candidates = self._find_devices_in_room(house, room_name) if room_name else house["devices"]
        return [
            d for d in candidates
            if self._is_controllable_device(d) and self._device_matches_type(d, category)
        ]

    def _find_devices_by_type(self, house: dict, dev_type: str, room_name: str = None) -> list:
        """Alias cho _find_devices_by_category — backward compat."""
        return self._find_devices_by_category(house, dev_type, room_name)

    def _execute_plan(self, plan: list, user_id=None) -> tuple:
        """
        Thực thi danh sách lệnh.
        plan: [{"dev": {...}, "action": "ON/OFF", "value": None, "msg": "..."}]
        Trả về (results, controlled_devices)
        """
        results, controlled = [], []
        seen_msgs = set()
        for item in plan:
            dev    = item["dev"]
            action = item["action"]
            value  = item.get("value")
            payload = {"device_code": dev["code"], "action": action}
            if value is not None:
                payload["value"] = float(value)
            if self.device_usecase:
                res = self.device_usecase.control_device(payload, user_id=user_id)
                if res.get("success"):
                    msg = item.get("msg") or dev["name"]
                    if msg not in seen_msgs:
                        results.append(msg)
                        seen_msgs.add(msg)
                    controlled.append({"code": dev["code"], "is_on": action != "OFF", "value": value})
                    logger.debug("Executed: %s -> %s%s", dev['code'], action, f" val={value}" if value else "")
                else:
                    logger.warning("Failed: %s -> %s", dev['code'], action)
        return results, controlled

    # ─────────────────────────────────────────
    # MAIN: handle_chat
    # ─────────────────────────────────────────
    def handle_chat(self, message: str, context_data: dict = None, mode: str = "llm", language: str = "vi", user_id=None, username=None):
        logger.debug("handle_chat called (mode=%s)", mode)

        lang = str(language or "vi").lower()
        if lang.startswith("en"):
            lang = "en"
        elif lang.startswith("vi"):
            lang = "vi"
        else:
            lang = "vi"

        def _l(vi_text: str, en_text: str) -> str:
            return en_text if lang == "en" else vi_text

        def _localize_action_msg(msg: str) -> str:
            if lang != "en":
                return msg
            text = str(msg or "")
            replacements = [
                ("bật ", "turn on "),
                ("tắt ", "turn off "),
                ("mở ", "open "),
                ("đóng ", "close "),
                ("kích hoạt ", "activate "),
                ("giảm ", "decrease "),
                ("tăng ", "increase "),
            ]
            low = text.lower()
            for vi_prefix, en_prefix in replacements:
                if low.startswith(vi_prefix):
                    return en_prefix + text[len(vi_prefix):]
            return text

        # ── Query real-time data ──
        house = self._get_realtime_house(context_data, user_id=user_id)
        is_llm_mode  = mode in ("llm", "gemini")
        is_rule_mode = mode == "rule"   # rule-only: không fallback sang LLM

        msg_lower = message.lower().strip()
        tokens    = set(re.split(r"[\s,./\-]+", msg_lower))

        def _norm(s):
            """Normalize tiếng Việt để match: tầng=tang, phòng=phong..."""
            s = s.lower().strip()
            replacements = {
                "tầng": "tang", "tầng": "tang", "phòng": "phong",
                "ă": "a", "â": "a", "đ": "d", "ê": "e", "ô": "o",
                "ơ": "o", "ư": "u", "à": "a", "á": "a", "ả": "a",
                "ã": "a", "ạ": "a", "ề": "e", "ế": "e", "ệ": "e",
                "ồ": "o", "ố": "o", "ổ": "o", "ỗ": "o", "ộ": "o",
                "ừ": "u", "ứ": "u", "ử": "u", "ữ": "u", "ự": "u",
                "ì": "i", "í": "i", "ỉ": "i", "ĩ": "i", "ị": "i",
            }
            for k, v in replacements.items():
                s = s.replace(k, v)
            return s

        msg_norm = _norm(msg_lower)
        rooms     = house["rooms"]
        floors    = house["floors"]
        all_devs  = house["devices"]
        owner_room_ctx = (context_data or {}).get("owner_room") if isinstance(context_data, dict) else None
        owner_room_name = None
        owner_room_id = None
        if isinstance(owner_room_ctx, dict):
            _nm = owner_room_ctx.get("name")
            _id = owner_room_ctx.get("id")
            owner_room_name = str(_nm).strip() if _nm is not None else None
            owner_room_id = str(_id).strip() if _id is not None else None
        elif owner_room_ctx is not None:
            owner_room_name = str(owner_room_ctx).strip()

        def _same_room_name(a: str | None, b: str | None) -> bool:
            if not a or not b:
                return False
            return _norm(str(a)) == _norm(str(b))

        def _resolve_owner_room_obj():
            if not owner_room_name and not owner_room_id:
                return None
            for r in rooms:
                rid = str(r.get("id", "")).strip()
                rname = str(r.get("name", "")).strip()
                if owner_room_id and rid and rid == owner_room_id:
                    return r
                if owner_room_name and _same_room_name(rname, owner_room_name):
                    return r
            return None

        def _is_this_room_phrase() -> bool:
            this_room_kws = ["phong nay", "phòng này", "o day", "ở đây", "room here", "this room"]
            return any(k in msg_norm for k in this_room_kws)

        def _smart_not_understood_reply() -> str:
            owner_obj = _resolve_owner_room_obj()
            owner_name = owner_obj.get("name") if owner_obj else owner_room_name

            room_names = [r.get("name") for r in rooms if r.get("name")]
            room_names = room_names[:3]

            controllable = [d.get("name") for d in all_devs if self._is_controllable_device(d)]
            controllable = [n for n in controllable if n][:3]

            if lang == "en":
                parts = ["Sir, I did not fully understand your intent."]
                if owner_name:
                    parts.append(f"I can prioritize your marker room: {owner_name}.")
                sample_room = room_names[0] if room_names else "Kitchen"
                parts.append(
                    "Try one of these: "
                    f"'turn on light in {sample_room}', "
                    "'turn off fan here', "
                    "or 'what devices are in this room?'."
                )
                if controllable:
                    parts.append(f"Available controllable devices include: {', '.join(controllable)}.")
                return " ".join(parts)

            parts = ["Thưa Ngài, tôi chưa hiểu trọn ý của Ngài."]
            if owner_name:
                parts.append(f"Tôi có thể ưu tiên phòng marker của Ngài: {owner_name}.")
            sample_room = room_names[0] if room_names else "Kitchen"
            parts.append(
                "Ngài có thể nói: "
                f"'bật đèn phòng {sample_room}', "
                "'tắt quạt ở đây', "
                "hoặc 'phòng này có thiết bị gì?'."
            )
            if controllable:
                parts.append(f"Thiết bị có thể điều khiển hiện tại: {', '.join(controllable)}.")
            return " ".join(parts)

        # ── Intent detection ──
        is_off    = any(w in msg_lower for w in ["tắt", "đóng", "turn off"])
        is_on     = any(w in msg_lower for w in ["bật", "mở", "turn on"])
        has_ctrl  = is_on or is_off
        action_val = "OFF" if is_off else "ON"
        verb       = _l("Đã tắt" if is_off else "Đã bật", "Turned off" if is_off else "Turned on")

        CONFIRM_KW = [
            "yes", "ok", "oke", "okay",
            "đồng ý", "dong y", "được", "duoc", "vâng", "vang", "uh", "ừ", "u",
            "sure", "làm đi", "lam di", "thực hiện đi", "thuc hien di",
            "tiến hành", "tien hanh", "proceed", "confirm", "xac nhan",
        ]

        # Two-pass strip: _norm handles "đ"→"d" (NFD can't decompose it), then NFD strips
        # remaining tone marks like "ý"→"y". Without this "đồng ý"→"dong" (ý lost).
        _msg_nfd = unicodedata.normalize("NFD", msg_norm).encode("ascii", "ignore").decode()
        msg_compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", _msg_nfd)).strip()

        def _is_confirm_phrase(text: str) -> bool:
            if any(n in text for n in ["khong", "thoi", "huy", "cancel", "no"]):
                return False
            if any(text == kw for kw in CONFIRM_KW):
                return True
            # Accept expanded forms such as "ok lam di", "vâng làm đi", etc.
            strong_phrases = ["lam di", "thuc hien di", "tien hanh", "dong y", "xac nhan", "confirm", "proceed"]
            return any(p in text for p in strong_phrases)

        def _is_deny_phrase(text: str) -> bool:
            deny_set = {"khong", "thoi", "no", "cancel", "huy", "dung"}
            return text in deny_set

        # ══════════════════════════════════════════
        # BƯỚC -2: SOS — keyword trong chat → emergency alert + email
        # ══════════════════════════════════════════
        _SOS_KEYWORDS = [
            "sos", "cứu tôi", "cứu với", "help me", "khẩn cấp",
            "cấp cứu", "emergency", "nguy hiểm", "tôi cần giúp đỡ",
            "goi cap cuu", "gọi cấp cứu",
        ]
        _msg_compact_sos = unicodedata.normalize("NFC", msg_lower).strip()
        if any(kw in _msg_compact_sos for kw in _SOS_KEYWORDS) or _msg_compact_sos in ("sos", "cứu"):
            # Clear stale pending so no device command fires after SOS
            self._clear_pending_action(user_id=user_id)
            sos_message = f"🆘 SOS EMERGENCY từ chat — {username or 'user'}: \"{message}\""
            try:
                from app.extensions.database import db
                sos_alert = self.alert.create_alert(
                    device_code="SOS_CHAT",
                    message=sos_message,
                    level="critical",
                    user_id=user_id,
                )
                db.session.commit()
            except Exception:
                try:
                    from app.extensions.database import db
                    db.session.rollback()
                except Exception:
                    pass
            # Emit socket popup to frontend
            try:
                self.realtime.notify_sos_alert({
                    "user_name": username or "user",
                    "note": message,
                    "source": "chat",
                }, user_id=user_id)
            except Exception:
                pass
            # Send email async
            if self.email_notifier:
                try:
                    from app.infrastructure.persistence.models.user_model import UserModel
                    user_obj = UserModel.query.filter_by(id=user_id).first() if user_id else None
                    user_email = getattr(user_obj, "email", None)
                    recipients = self.email_notifier.resolve_recipients(
                        user_email=user_email, include_default_recipients=True
                    )
                    self.email_notifier.send_async(
                        subject=f"🆘 SOS Emergency: {username or 'User'}",
                        body=(
                            f"⚠️ Emergency SOS triggered via Alfred AI chat.\n\n"
                            f"User: {username or 'unknown'}\n"
                            f"Message: \"{message}\"\n\n"
                            f"Please check on the patient immediately."
                        ),
                        recipients=recipients,
                    )
                    logger.info("SOS email queued for %s", recipients)
                except Exception as e:
                    logger.warning("SOS email failed: %s", e, exc_info=True)
            return _reply(_l(
                "🆘 Thưa Ngài, tôi đã kích hoạt cảnh báo khẩn cấp và thông báo cho người thân. Ngài có ổn không?",
                "🆘 Sir, I have triggered an emergency alert and notified your contacts. Are you okay?"
            ))

        # ══════════════════════════════════════════
        # BƯỚC -1: FAQ cứng — luôn chạy kể cả rule mode
        # ══════════════════════════════════════════
        if is_rule_mode:
            from datetime import datetime as _dt
            _faq = [
                (["xin chào","hello","hi","hey","chào","howdy"],
                      _l("Kính chào, thưa Ngài. Alfred luôn sẵn sàng phục vụ. Gõ /help để xem lệnh.",
                          "Greetings, Sir. Alfred is always at your service. Type /help to see available commands.")),
                (["/help","help","giúp","hướng dẫn","lệnh"],
                      _l("📋 Rule Mode hỗ trợ:\n• bật/tắt đèn [phòng X]\n• bật/tắt điều hòa\n• bật/tắt quạt\n• mở/khóa cửa\n• tắt hết\nChuyển LLM Mode để hỏi phức tạp hơn.",
                          "📋 Rule Mode supports:\n• turn on/off lights [room X]\n• turn on/off AC\n• turn on/off fan\n• open/lock door\n• turn everything off\nSwitch to LLM Mode for complex requests.")),
                (["mấy giờ","what time","bây giờ","giờ hiện tại","thời gian"],
                      _l(f"Hiện tại là {_dt.now().strftime('%H:%M — %d/%m/%Y')}, thưa Ngài.",
                          f"Current time is {_dt.now().strftime('%H:%M — %d/%m/%Y')}, Sir.")),
                (["cảm ơn","thank","thanks","tks"],
                      _l("Không có gì, thưa Ngài. Đó là nhiệm vụ của tôi. 🎩",
                          "You're most welcome, Sir. That is my duty. 🎩")),
                (["bạn là ai","who are you","tên bạn","alfred là ai"],
                      _l("Tôi là Alfred — trợ lý AI của Batman OS Smart Home.",
                          "I am Alfred, the AI assistant of Batman OS Smart Home.")),
                (["thời tiết","weather","trời hôm nay"],
                      _l("Rule Mode chưa kết nối thời tiết. Hãy thử LLM hoặc Gemini Mode.",
                          "Rule Mode is not connected to weather yet. Please try LLM or Gemini Mode.")),
            ]
            for keywords, response in _faq:
                if any(kw in msg_lower for kw in keywords):
                    return _reply(response)

        # ══════════════════════════════════════════
        # BƯỚC 0: Xử lý pending action (chờ xác nhận)
        # ══════════════════════════════════════════
        pending = self._get_pending_action(user_id=user_id)
        if pending:

            # ── Schedule pending: chờ xác nhận tạo lịch hẹn giờ ──
            if pending.get("type") == "schedule":
                if _is_confirm_phrase(msg_compact) or _is_deny_phrase(msg_compact) is False and has_ctrl is False and any(
                    w in msg_lower for w in ["yes", "đồng ý", "được", "ok", "lam di", "xac nhan", "confirm"]
                ):
                    pass  # handled below
                if _is_deny_phrase(msg_compact):
                    self._clear_pending_action(user_id=user_id)
                    return _reply(_l("Thưa Ngài, đã hủy lịch hẹn.", "Sir, schedule cancelled."))
                if _is_confirm_phrase(msg_compact):
                    self._clear_pending_action(user_id=user_id)
                    sched_intent = pending["intent"]
                    dev          = pending["device"]
                    try:
                        from app.infrastructure.persistence.models.schedule_model import ScheduleModel
                        from app.extensions.database import db
                        from datetime import datetime as _dtnow, timezone as _tz
                        new_sched = ScheduleModel(
                            device_id  = dev["id"],
                            action     = {"is_on": sched_intent["action"] == "ON"},
                            cron_expr  = sched_intent["cron_expr"],
                            is_active  = True,
                            label      = sched_intent["label"],
                            remind_only= False,
                            created_by = user_id,
                            created_at = _dtnow.now(_tz.utc),
                        )
                        db.session.add(new_sched)
                        db.session.commit()
                        # Reload APScheduler so the new job fires at the correct time
                        try:
                            from app.scheduler import _scheduler, _reload_schedules
                            from flask import current_app
                            if _scheduler and _scheduler.running:
                                _reload_schedules(current_app._get_current_object(), _scheduler)
                        except Exception:
                            pass
                        return _reply(_l(
                            f"Thưa Ngài, đã tạo lịch: {sched_intent['label']} cho {dev['name']}. "
                            f"Lịch sẽ tự động chạy theo cron `{sched_intent['cron_expr']}`.",
                            f"Sir, schedule created: {sched_intent['label']} for {dev['name']}. "
                            f"It will run automatically (cron: `{sched_intent['cron_expr']}`).",
                        ))
                    except Exception as exc:
                        logger.error("Failed to create schedule from Alfred: %s", exc)
                        return _reply(_l(
                            "Thưa Ngài, có lỗi khi tạo lịch. Vui lòng thử lại qua trang Device Schedule.",
                            "Sir, an error occurred while creating the schedule. Please try via the Device Schedule page.",
                        ))
                # Still waiting for confirmation
                sched_intent = pending["intent"]
                dev          = pending["device"]
                return _reply(_l(
                    f"Thưa Ngài, xác nhận tạo lịch: {sched_intent['label']} cho {dev['name']}? "
                    "Nói 'đồng ý' để xác nhận hoặc 'hủy' để bỏ qua.",
                    f"Sir, confirm schedule: {sched_intent['label']} for {dev['name']}? "
                    "Say 'confirm' to proceed or 'cancel' to abort.",
                ))

            # Nếu đang chờ chọn phòng
            if pending.get("need_room"):
                scenario_plan = pending["plan"]
                available_rooms = sorted(set(p["room"] for p in scenario_plan if p.get("room")))

                # Tìm phòng user đề cập
                matched_room = next(
                    (r for r in available_rooms if r.lower() in tokens),
                    None
                )

                # If user has an owner marker room, use it as implicit room selection.
                if not matched_room:
                    owner_room_obj = _resolve_owner_room_obj()
                    owner_candidate = owner_room_obj.get("name") if owner_room_obj else owner_room_name
                    if owner_candidate:
                        matched_room = next((r for r in available_rooms if _same_room_name(r, owner_candidate)), None)

                if matched_room:
                    self._clear_pending_action(user_id=user_id)
                    target_items = [p for p in scenario_plan if _same_room_name(p.get("room"), matched_room)]
                    if not target_items:
                        # Phòng không có thiết bị trong plan → tìm thiết bị phù hợp nhất trong phòng
                        house_ctx   = pending.get("house", house)
                        scenario_obj = pending.get("scenario", {})
                        room_devs = self._find_devices_in_room(house_ctx, matched_room)
                        # Thử từng action trong scenario
                        fallback_plan = []
                        for act in scenario_obj.get("actions", []):
                            cat = act.get("category") or act.get("type", "")
                            matched_devs = [d for d in room_devs if d.get("category","").lower() == cat.lower()]
                            for dev in matched_devs:
                                fallback_plan.append({"dev": dev, "action": act["action"],
                                    "value": act.get("value"), "room": matched_room, "msg": _localize_action_msg(act["msg"])})
                        if fallback_plan:
                            results, controlled = self._execute_plan(fallback_plan, user_id=user_id)
                            if results:
                                return _reply(_l(
                                    f"Thưa Ngài, đã thực hiện phòng {matched_room}: {'; '.join(results)}.",
                                    f"Sir, completed actions in room {matched_room}: {'; '.join(results)}."
                                ), controlled)
                        # Không có thiết bị phù hợp → chỉ trả về thông báo, không thực hiện hành động nào
                        return _reply(_l(
                            f"Thưa Ngài, phòng {matched_room} không có thiết bị phù hợp.",
                            f"Sir, room {matched_room} has no matching devices."
                        ))
                    results, controlled = self._execute_plan(target_items, user_id=user_id)
                    if results:
                        return _reply(_l(
                            f"Thưa Ngài, đã thực hiện phòng {matched_room}: {'; '.join(results)}.",
                            f"Sir, completed actions in room {matched_room}: {'; '.join(results)}."
                        ), controlled)
                    return _reply(_l(
                        f"Thưa Ngài, không thể thực hiện với thiết bị phòng {matched_room}.",
                        f"Sir, I could not execute actions for devices in room {matched_room}."
                    ))

                elif _is_deny_phrase(msg_compact):
                    self._clear_pending_action(user_id=user_id)
                    return _reply(_l("Thưa Ngài, đã hủy lệnh.", "Sir, command cancelled."))

                else:
                    opts = ", ".join(_l(f"phòng {r}", f"room {r}") for r in available_rooms)
                    owner_hint = ""
                    owner_room_obj = _resolve_owner_room_obj()
                    if owner_room_obj:
                        owner_hint = _l(
                            f" Marker hiện tại của Ngài: phòng {owner_room_obj.get('name')}.",
                            f" Your current marker room: {owner_room_obj.get('name')}."
                        )
                    return _reply(_l(
                        f"Thưa Ngài, Ngài muốn thực hiện ở phòng nào? ({opts}).{owner_hint}",
                        f"Sir, which room should I execute this in? ({opts}).{owner_hint}"
                    ))

            # Nếu đang chờ xác nhận yes/no
            elif _is_confirm_phrase(msg_compact) and not has_ctrl:
                plan_rooms = sorted(set(p.get("room") for p in pending.get("plan", []) if p.get("room")))
                if len(plan_rooms) > 1:
                    pending["need_room"] = True
                    self._set_pending_action(pending, user_id=user_id)
                    opts = ", ".join(_l(f"phòng {r}", f"room {r}") for r in plan_rooms)
                    return _reply(_l(
                        f"Thưa Ngài, có nhiều phòng phù hợp. Ngài muốn thực hiện ở phòng nào? ({opts})",
                        f"Sir, multiple rooms match. Which room should I execute in? ({opts})"
                    ))

                self._clear_pending_action(user_id=user_id)
                if pending.get("mood_only"):
                    mood_key = pending.get("mood")
                    mood_theme_map = {
                        "buồn": "meditation",
                        "vui": "focus",
                        "chán": "vigilant",
                        "buồn_ngủ": "meditation",
                        "stress": "meditation",
                        "bệnh": "medical",
                        "lãng_mạn": "meditation",
                        "tâm_sự": "meditation",
                    }
                    return _reply(
                        _l(
                            "Thưa Ngài, đã áp dụng hỗ trợ cảm xúc: đổi giao diện theo mood và giữ đề xuất nội dung phù hợp.",
                            "Sir, emotional support has been applied: theme adjusted by mood and suitable content suggestions retained."
                        ),
                        mood_data={
                            "mood": mood_key,
                            "movies": pending.get("movies", []),
                            "music": pending.get("music", []),
                            "reminders": pending.get("reminders", []),
                            "has_plan": False,
                            "auto_apply_theme": True,
                            "suggested_theme": mood_theme_map.get(mood_key, "vigilant"),
                        }
                    )
                results, controlled = self._execute_plan(pending["plan"], user_id=user_id)
                if results:
                    return _reply(_l(
                        f"Thưa Ngài, đã thực hiện: {'; '.join(results)}.",
                        f"Sir, completed: {'; '.join(results)}."
                    ), controlled)
                return _reply(_l("Thưa Ngài, không thể thực hiện lệnh.", "Sir, I could not execute the command."))

            elif _is_deny_phrase(msg_compact):
                self._clear_pending_action(user_id=user_id)
                return _reply(_l("Thưa Ngài, đã hủy lệnh.", "Sir, command cancelled."))

            elif not has_ctrl:
                return _reply(_l(
                    "Thưa Ngài, Ngài muốn tôi thực hiện đề xuất vừa rồi không? Hãy nói rõ 'làm đi' để xác nhận hoặc 'hủy'.",
                    "Sir, should I proceed with the previous suggestion? Please say 'confirm' to proceed or 'cancel'."
                ))

        # ══════════════════════════════════════════
        # BƯỚC 0.5: Hẹn lịch theo giờ (schedule intent)
        # ══════════════════════════════════════════
        if not (pending and pending.get("type") == "schedule"):
            # ── 0.5a: DELETE schedule intent (must check before create) ──
            try:
                from app.ai.services.schedule_intent_parser import parse_delete_schedule_intent
                del_intent = parse_delete_schedule_intent(message)
                if del_intent:
                    if pending:
                        self._clear_pending_action(user_id=user_id)
                    from app.infrastructure.persistence.models.schedule_model import ScheduleModel
                    from app.infrastructure.persistence.models.device_model import Device
                    from app.extensions.database import db

                    # Resolve device IDs early so we can bail if category unknown
                    dev_ids_filter: list[int] | None = None
                    if del_intent.get("device_category"):
                        dev_cat   = del_intent["device_category"]
                        cands     = self._find_devices_by_category(house, dev_cat)
                        if not cands:
                            cat_vi = {"fan":"quạt","light":"đèn","ac":"điều hòa",
                                      "tv":"TV","speaker":"loa","outlet":"ổ cắm"}.get(dev_cat, dev_cat)
                            return _reply(_l(
                                f"Thưa Ngài, không tìm thấy thiết bị {cat_vi} để xóa lịch.",
                                f"Sir, no {dev_cat} device found to delete schedule.",
                            ))
                        dev_ids_filter = [d["id"] for d in cands]

                    # Build query: join Schedule → Device, filter by user
                    q = (db.session.query(ScheduleModel)
                         .join(Device, Device.id == ScheduleModel.device_id)
                         .filter(Device.user_id == user_id, ScheduleModel.is_active == True))

                    if del_intent.get("cron_expr"):
                        q = q.filter(ScheduleModel.cron_expr == del_intent["cron_expr"])

                    if dev_ids_filter:
                        q = q.filter(ScheduleModel.device_id.in_(dev_ids_filter))

                    # Post-filter by action in Python — avoids SQLAlchemy JSON path issues
                    rows = q.all()
                    if del_intent.get("action"):
                        want_on = del_intent["action"] == "ON"
                        rows = [r for r in rows
                                if (r.action or {}).get("is_on") == want_on]

                    if not rows:
                        return _reply(_l(
                            "Thưa Ngài, không tìm thấy lịch nào khớp. Vui lòng kiểm tra tại trang Device Schedule.",
                            "Sir, no matching schedule found. Please check the Device Schedule page.",
                        ))
                    for s in rows:
                        db.session.delete(s)
                    db.session.commit()
                    try:
                        from app.scheduler import _scheduler, _reload_schedules
                        from flask import current_app
                        if _scheduler and _scheduler.running:
                            _reload_schedules(current_app._get_current_object(), _scheduler)
                    except Exception:
                        pass
                    labels = ", ".join(s.label or f"#{s.id}" for s in rows)
                    return _reply(_l(
                        f"Thưa Ngài, đã xóa {len(rows)} lịch: {labels}.",
                        f"Sir, deleted {len(rows)} schedule(s): {labels}.",
                    ))
            except Exception as _del_exc:
                logger.warning("delete_schedule_intent error: %s", _del_exc)

            # ── 0.5b: CREATE schedule intent ──
            try:
                from app.ai.services.schedule_intent_parser import parse_schedule_intent
                sched_intent = parse_schedule_intent(message)
                if sched_intent:
                    # Clear stale non-schedule pending so the new schedule takes over
                    if pending:
                        self._clear_pending_action(user_id=user_id)
                    dev_cat    = sched_intent["device_category"]
                    candidates = self._find_devices_by_category(house, dev_cat)
                    # Filter out sensors/cameras
                    candidates = [d for d in candidates if self._is_controllable_device(d)]
                    if candidates:
                        dev = candidates[0]
                        self._set_pending_action({
                            "type":        "schedule",
                            "intent":      sched_intent,
                            "device":      dev,
                            "created_at":  time.time(),
                        }, user_id=user_id)
                        cat_vi = {
                            "fan": "quạt", "light": "đèn", "ac": "điều hòa",
                            "tv": "TV", "speaker": "loa", "outlet": "ổ cắm",
                        }.get(dev_cat, dev_cat)
                        return _reply(_l(
                            f"Thưa Ngài, tôi hiểu Ngài muốn: {sched_intent['label']} — thiết bị: {dev['name']}.\n"
                            f"Xác nhận tạo lịch này không? Nói 'đồng ý' hoặc 'hủy'.",
                            f"Sir, I understand: {sched_intent['label']} — device: {dev['name']}.\n"
                            f"Confirm creating this schedule? Say 'confirm' or 'cancel'.",
                        ))
                    else:
                        cat_vi = {
                            "fan": "quạt", "light": "đèn", "ac": "điều hòa",
                            "tv": "TV", "speaker": "loa", "outlet": "ổ cắm",
                        }.get(dev_cat, dev_cat)
                        return _reply(_l(
                            f"Thưa Ngài, không tìm thấy thiết bị {cat_vi} nào trong hệ thống. "
                            "Vui lòng thêm thiết bị trước khi đặt lịch.",
                            f"Sir, no {dev_cat} device was found in the system. "
                            "Please add the device before scheduling.",
                        ))
            except Exception as _sched_exc:
                logger.debug("schedule_intent_parser error (non-fatal): %s", _sched_exc)

            # ── 0.5c: Lifestyle time intent (sleep/wake at X) — no explicit device ──
            # Catches "i want to sleep at 9h10 every day" / "sleep on Monday at 9pm"
            # without guessing which device to control.
            try:
                from app.ai.services.schedule_intent_parser import (
                    detect_lifestyle_keyword, _has_schedule_trigger, _detect_time,
                    _detect_specific_days, _DOW_LABEL, _norm as _sip_norm
                )
                _sip_norm_msg = _sip_norm(message)
                _specific_days_05c = _detect_specific_days(_sip_norm_msg)
                _has_trigger_05c   = _has_schedule_trigger(msg_lower)
                if (_has_trigger_05c or _specific_days_05c) and not sched_intent:
                    _time_res = _detect_time(message)
                    if _time_res:
                        _activity = detect_lifestyle_keyword(_sip_norm_msg)
                        if _activity:
                            _h, _m, _ = _time_res
                            _time_str  = f"{_h:02d}:{_m:02d}"
                            _ctrl_devs = [d.get("name") for d in all_devs if self._is_controllable_device(d)][:4]
                            _ex_devs   = ", ".join(_ctrl_devs) if _ctrl_devs else ("light, fan" if lang == "en" else "đèn, quạt")
                            # Build day context if specific days were mentioned
                            if _specific_days_05c:
                                _day_str_en = ", ".join(_DOW_LABEL[d] for d in _specific_days_05c)
                                _day_str_vi = _day_str_en
                                _when_en = f"on {_day_str_en} at {_time_str}"
                                _when_vi = f"vào {_day_str_vi} lúc {_time_str}"
                                _ex_sched_en = f"'turn off light on {_day_str_en} at {_time_str}'"
                                _ex_sched_vi = f"'tắt đèn vào {_day_str_vi} lúc {_time_str}'"
                            else:
                                _when_en = f"at {_time_str}"
                                _when_vi = f"lúc {_time_str}"
                                _ex_sched_en = f"'turn off light at {_time_str} every day'"
                                _ex_sched_vi = f"'tắt đèn lúc {_time_str} mỗi ngày'"
                            return _reply(_l(
                                f"Thưa Ngài, tôi hiểu Ngài muốn '{_activity}' {_when_vi}. "
                                f"Ngài muốn tôi điều khiển thiết bị nào vào lúc đó? "
                                f"Ví dụ: {_ex_sched_vi}, 'tắt quạt {_when_vi}'.\n"
                                f"Thiết bị hiện có: {_ex_devs}.",
                                f"Sir, I understand you want '{_activity}' {_when_en}. "
                                f"Which device should I control at that time? "
                                f"For example: {_ex_sched_en}, 'turn off fan {_when_en}'.\n"
                                f"Available devices: {_ex_devs}."
                            ))
            except Exception as _life_exc:
                logger.debug("lifestyle_schedule error (non-fatal): %s", _life_exc)

        # ══════════════════════════════════════════
        # BƯỚC A: Câu hỏi thông tin (không điều khiển)
        # ══════════════════════════════════════════
        INFO_KW   = ["có gì", "có các", "có thiết bị", "thiết bị gì", "what", "have",
                     "devices", "liệt kê", "cho biết", "nào", "gì"]
        FLOOR_KW  = ["có các phòng", "có mấy phòng", "các phòng", "mấy phòng", "phòng nào",
                     "có phòng", "rooms", "floors"]

        is_info = any(w in msg_lower for w in INFO_KW) and not has_ctrl

        if is_info:
            is_english = (lang == "en")

            # Hỏi phòng của tầng
            for fl in floors:
                fname = fl.get("name", "").lower()
                fname_norm = _norm(fname)
                if fname and (fname in msg_lower or fname_norm in msg_norm) and any(w in msg_lower for w in FLOOR_KW):
                    rnames = fl.get("room_names", [])
                    if rnames:
                        return _reply(f"Thưa Ngài, {fl['name']} có {len(rnames)} phòng: {', '.join(rnames)}.")
                    return _reply(f"Thưa Ngài, {fl['name']} chưa có phòng nào.")

            # Hỏi thiết bị của phòng
            for room in rooms:
                rname = room.get("name", "").lower()
                if rname and rname in tokens:
                    devs = self._find_devices_in_room(house, room["name"])
                    dev_names = [d["name"] for d in devs]
                    if dev_names:
                        reply_text = (f"Sir, room {room['name']} has: {', '.join(dev_names)}."
                                      if is_english else
                                      f"Thưa Ngài, phòng {room['name']} có: {', '.join(dev_names)}.")
                        return _reply(reply_text)
                    else:
                        reply_text = (f"Sir, room {room['name']} has no devices."
                                      if is_english else
                                      f"Thưa Ngài, phòng {room['name']} chưa có thiết bị nào.")
                        return _reply(reply_text)

            # Hỏi thiết bị của tầng
            for fl in floors:
                fname = fl.get("name", "").lower()
                fname_norm = _norm(fname)
                if fname and (fname in msg_lower or fname_norm in msg_norm):
                    fl_rooms = [r for r in rooms if r.get("floor", "").lower() == fname
                                or r.get("name", "") in fl.get("room_names", [])]
                    all_fl_devs = []
                    for r in fl_rooms:
                        all_fl_devs.extend(self._find_devices_in_room(house, r["name"]))
                    if all_fl_devs:
                        parts = []
                        for r in fl_rooms:
                            devs = self._find_devices_in_room(house, r["name"])
                            if devs:
                                parts.append(f"phòng {r['name']}: {', '.join(d['name'] for d in devs)}")
                        return _reply(f"Thưa Ngài, {fl['name']} có: {'; '.join(parts)}.")
                    return _reply(f"Thưa Ngài, {fl['name']} chưa có thiết bị nào.")

        # ══════════════════════════════════════════
        # BƯỚC B: Điều khiển thiết bị (real-time lookup)
        # ══════════════════════════════════════════
        if has_ctrl and self.device_usecase:

            # Xác định phòng target từ message
            target_rooms = [r for r in rooms if r.get("name", "").lower() in tokens]
            owner_room_obj = _resolve_owner_room_obj()
            if not target_rooms and _is_this_room_phrase() and owner_room_obj:
                target_rooms = [owner_room_obj]

            # ── B1: Bật/tắt TẤT CẢ thiết bị trong phòng ──
            ALL_KW = ["hết", "tất cả", "all", "toàn bộ", "các thiết bị"]
            if any(w in msg_lower for w in ALL_KW) and target_rooms:
                results, controlled = [], []
                for room in target_rooms:
                    devs = self._find_devices_in_room(house, room["name"])
                    plan = [{"dev": d, "action": action_val, "value": None,
                             "msg": f"{verb} {d['name']}"} for d in devs]
                    r, c = self._execute_plan(plan, user_id=user_id)
                    results.extend(r)
                    controlled.extend(c)
                if results:
                    rnames = ", ".join(r["name"] for r in target_rooms)
                    return _reply(_l(
                        f"Thưa Ngài, {verb} tất cả thiết bị phòng {rnames}: {', '.join(results)}.",
                        f"Sir, {verb} all devices in room {rnames}: {', '.join(results)}."
                    ), controlled)
                return _reply(_l(
                    "Thưa Ngài, không tìm thấy thiết bị trong phòng đã chọn.",
                    "Sir, no devices were found in the selected room."
                ))

            # ── B2: Bật/tắt thiết bị cụ thể theo tên/code ──
            # Nếu có phòng target → chỉ tìm trong phòng đó
            if target_rooms:
                candidates = []
                for room in target_rooms:
                    candidates.extend(self._find_devices_in_room(house, room["name"]))
            elif owner_room_obj:
                # Không chỉ rõ phòng: ưu tiên phòng hiện tại theo owner marker.
                candidates = self._find_devices_in_room(house, owner_room_obj.get("name"))
            else:
                candidates = all_devs

            matched = [d for d in candidates
                       if d.get("code", "").lower() in tokens
                       or d.get("name", "").lower() in tokens]

            if matched:
                plan = [{"dev": d, "action": action_val, "value": None,
                         "msg": f"{verb} {d['name']}"} for d in matched]
                results, controlled = self._execute_plan(plan, user_id=user_id)
                if results:
                    return _reply(_l(
                        f"Thưa Ngài, {', '.join(results)}.",
                        f"Sir, {', '.join(results)}."
                    ), controlled)
                return _reply(_l(
                    "Thưa Ngài, không thể thực hiện lệnh với thiết bị đã chọn.",
                    "Sir, I could not execute the command for the selected devices."
                ))

        # ══════════════════════════════════════════
        # BƯỚC C0: Chào hỏi / small-talk — chạy trước mood, mọi mode
        # ══════════════════════════════════════════
        if not has_ctrl:
            from datetime import datetime as _dt

            # Force language from UI setting to avoid mixed-language replies.
            _is_english = (lang == "en")

            _GREET_KW = ["xin chào", "chào bạn", "good morning", "good afternoon",
                         "good evening", "good night", "howdy"]
            _is_bare_greet = msg_lower in ("hello", "hi", "hey", "chào", "alo")
            _is_greet = _is_bare_greet or any(w in msg_lower for w in _GREET_KW)

            _HOW_KW = ["how are you", "how r u", "bạn khỏe", "bạn thế nào",
                       "khỏe không", "dạo này sao", "ổn không", "are you ok"]
            _is_how  = any(w in msg_lower for w in _HOW_KW)

            _THANKS_KW = ["cảm ơn", "thank you", "thanks", "tks", "camon", "cam on"]
            _is_thanks = any(w in msg_lower for w in _THANKS_KW)

            _WHERE_AM_I_KW = [
                "toi dang o dau", "toi o dau", "o dau", "vi tri cua toi",
                "where am i", "my location",
            ]
            _WHERE_AM_I_RAW_KW = ["tôi đang ở đâu", "tôi ở đâu", "vị trí của tôi"]
            if any(w in msg_norm for w in _WHERE_AM_I_KW) or any(w in msg_lower for w in _WHERE_AM_I_RAW_KW):
                owner_room_obj = _resolve_owner_room_obj()
                if owner_room_obj:
                    return _reply(_l(
                        f"Thưa Ngài, hiện tại marker của Ngài đang ở phòng {owner_room_obj.get('name', 'Unknown')}.",
                        f"Sir, your current marker is in room {owner_room_obj.get('name', 'Unknown')}."
                    ))
                if owner_room_name:
                    return _reply(_l(
                        f"Thưa Ngài, hiện tại marker của Ngài đang ở phòng {owner_room_name}.",
                        f"Sir, your current marker is in room {owner_room_name}."
                    ))
                return _reply(_l(
                    "Thưa Ngài, tôi chưa có vị trí hiện tại. Ngài hãy double-click trên map để đặt marker vị trí.",
                    "Sir, I do not have your current location yet. Please double-click on the map to place your location marker."
                ))

            if _is_greet:
                _h = _dt.now().hour
                if _is_english:
                    _g = "Good morning" if _h < 12 else "Good afternoon" if _h < 18 else "Good evening"
                    return _reply(f"{_g}, Sir. Alfred is always at your service. How may I assist?")
                else:
                    _g = "Chào buổi sáng" if _h < 12 else "Chào buổi chiều" if _h < 18 else "Chào buổi tối"
                    return _reply(f"{_g}, thưa Ngài. Alfred luôn sẵn sàng phục vụ. Ngài cần gì ạ?")

            if _is_how:
                if _is_english:
                    return _reply("I'm doing well, Sir. Always ready to serve. How may I help you?")
                return _reply("Thưa Ngài, Alfred khỏe và luôn sẵn sàng. Cảm ơn Ngài đã hỏi thăm! Ngài cần hỗ trợ gì không?")

            if _is_thanks:
                if _is_english:
                    return _reply("You're most welcome, Sir. That is my duty. 🎩")
                return _reply("Không có gì, thưa Ngài. Đó là nhiệm vụ của tôi. 🎩")

            _LANG_KW = ["english please", "speak english", "in english", "reply in english",
                        "tiếng anh", "nói tiếng anh", "trả lời tiếng anh"]
            if any(w in msg_lower for w in _LANG_KW):
                return _reply(_l(
                    "Vâng, thưa Ngài. Tôi sẽ trả lời bằng tiếng Việt theo nút ngôn ngữ đã chọn.",
                    "Of course, Sir. I shall respond in English from now on. How may I assist you?"
                ))

        # ══════════════════════════════════════════
        # BƯỚC C1: Mood System — detect tâm trạng + đề xuất
        # ══════════════════════════════════════════
        if not has_ctrl:
            try:
                from app.alfred_knowledge import MOOD_PROFILES, ALFRED_SCENARIOS
            except ImportError:
                MOOD_PROFILES, ALFRED_SCENARIOS = {}, {}

            mood_theme_map = {
                "buồn": "meditation",
                "vui": "focus",
                "chán": "vigilant",
                "buồn_ngủ": "meditation",
                "stress": "meditation",
                "bệnh": "medical",
                "lãng_mạn": "meditation",
                "tâm_sự": "meditation",
            }

            # ── Check mood trước scenario ──
            for mood_key, mood in MOOD_PROFILES.items():
                if not any(w in msg_lower for w in mood["keywords"]):
                    continue

                logger.debug("Mood detected: %s", mood_key)

                # Chat mode — chỉ nói chuyện, không control
                if mood.get("chat_mode"):
                    return _reply(mood["companion_msg"] or "Thưa Ngài, tôi đây lắng nghe.")

                # Build suggestion message
                lines = []
                if mood.get("message"):
                    lines.append(mood["message"])

                owner_room = None
                if isinstance(context_data, dict):
                    owner_room = context_data.get("owner_room")

                # Build device plan
                plan = []
                for act in mood.get("device_actions", []):
                    devs = self._find_devices_by_category(house, act["category"])
                    for dev in devs:
                        room_name = next(
                            (r["name"] for r in rooms if dev["name"] in r.get("device_names", [])), "?"
                        )
                        if not any(p["dev"]["code"] == dev["code"] for p in plan):
                            plan.append({"dev": dev, "action": act["action"],
                                         "value": act.get("value"), "room": room_name, "msg": _localize_action_msg(act["msg"])})

                # Movie suggestions
                movies = mood.get("movies", [])
                music  = mood.get("music", [])
                reminders = mood.get("reminders", [])

                # Build full suggestion reply
                suggestion_parts = []
                if plan:
                    action_summary = "; ".join(dict.fromkeys(p["msg"] for p in plan))
                    suggestion_parts.append(f"🏠 Thiết bị: {action_summary}")
                if movies:
                    movie_list = ", ".join(f"{m['title']}" for m in movies[:2])
                    suggestion_parts.append(f"🎬 Phim đề xuất: {movie_list}")
                if music:
                    suggestion_parts.append(f"🎵 Nhạc: {music[0]}")
                if reminders:
                    suggestion_parts.append("⚠️ " + " | ".join(reminders))

                # Companion message nếu có
                companion = mood.get("companion_msg")

                # If multiple rooms are affected, prefer owner's room from map context.
                plan_rooms = sorted(set(p.get("room") for p in plan if p.get("room") and p.get("room") != "?"))
                if plan and len(plan_rooms) > 1:
                    if owner_room and any(owner_room.lower() == r.lower() for r in plan_rooms):
                        plan = [p for p in plan if p.get("room", "").lower() == owner_room.lower()]
                        suggestion_parts.append(f"📍 Ưu tiên phòng của Ngài: {owner_room}")
                    else:
                        self._set_pending_action({
                            "plan": plan,
                            "need_room": True,
                            "mood": mood_key,
                            "movies": movies,
                            "music": music,
                        }, user_id=user_id)
                        opts = ", ".join(f"phòng {r}" for r in plan_rooms)
                        reply_text = (mood.get("message") or f"Thưa Ngài, tôi phát hiện Ngài đang {mood_key}.")
                        if suggestion_parts:
                            reply_text += "\n\nĐề xuất của tôi:\n" + "\n".join(suggestion_parts)
                        reply_text += f"\n\nTôi nên thực hiện ở phòng nào? ({opts})"
                        if companion:
                            reply_text += f"\n\n💬 {companion}"
                        return _reply(reply_text, mood_data={
                            "mood": mood_key,
                            "movies": movies,
                            "music": music,
                            "reminders": mood.get("reminders", []),
                            "has_plan": bool(plan),
                            "suggested_theme": mood_theme_map.get(mood_key, "vigilant"),
                        })

                # Lưu pending
                if plan:
                    self._set_pending_action({
                        "plan": plan, "need_room": False,
                        "mood": mood_key,
                        "movies": movies, "music": music,
                        "reminders": mood.get("reminders", []),
                    }, user_id=user_id)
                else:
                    self._set_pending_action({
                        "plan": [], "need_room": False,
                        "mood_only": True,
                        "mood": mood_key,
                        "movies": movies,
                        "music": music,
                        "reminders": mood.get("reminders", []),
                    }, user_id=user_id)

                reply_text = (mood.get("message") or f"Thưa Ngài, tôi phát hiện Ngài đang {mood_key}.")
                if suggestion_parts:
                    reply_text += "\n\nĐề xuất của tôi:\n" + "\n".join(suggestion_parts)
                if plan:
                    reply_text += "\n\nNgài có muốn tôi thực hiện không?"
                else:
                    reply_text += "\n\nTôi có thể đổi theme và đề xuất nội dung ngay bây giờ; điều khiển thiết bị tự động cần thiết bị đúng loại trong phòng của Ngài."
                if companion:
                    reply_text += f"\n\n💬 {companion}"

                return _reply(reply_text, mood_data={
                    "mood": mood_key,
                    "movies": movies,
                    "music": music,
                    "reminders": mood.get("reminders", []),
                    "has_plan": bool(plan),
                    "suggested_theme": mood_theme_map.get(mood_key, "vigilant"),
                })

        # ── ALFRED_SCENARIOS ──
        if not has_ctrl:
            try:
                from app.alfred_knowledge import ALFRED_SCENARIOS
            except ImportError:
                ALFRED_SCENARIOS = {}

            # If the message looks like a scheduling/time request skip scenarios —
            # the schedule_intent_parser or lifestyle handler deals with it in BƯỚC 0.5.
            _SCHED_INDICATORS = [
                "every day", "everyday", "daily", "every night", "every morning",
                "mỗi ngày", "hàng ngày", "mỗi tối", "mỗi sáng",
                "at ", "lúc ", "vào lúc ",
                "today", "tonight", "hôm nay", "tối nay", "sáng nay",
                "9h", "10h", "11h", "12h", "13h", "14h", "15h", "16h",
                "17h", "18h", "19h", "20h", "21h", "22h", "23h",
                # Day-of-week names clearly indicate a schedule request
                "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                " mon ", " tue ", " wed ", " thu ", " fri ", " sat ", " sun ",
                "thứ 2", "thứ 3", "thứ 4", "thứ 5", "thứ 6", "thứ 7", "chủ nhật",
            ]
            _scenario_looks_like_schedule = any(ind in msg_lower for ind in _SCHED_INDICATORS)

            for scenario_key, scenario in ALFRED_SCENARIOS.items():
                if not any(w in msg_lower for w in scenario["keywords"]):
                    continue
                # Skip: message is asking to schedule this scenario, not run it now
                if _scenario_looks_like_schedule:
                    continue

                # Build plan từ real-time DB data
                plan = []
                for act in scenario["actions"]:
                    dev_type = act.get("category") or act.get("type", "switch")
                    devs = self._find_devices_by_category(house, dev_type)
                    for dev in devs:
                        # Tìm phòng của device từ rooms context
                        room_name = dev.get("room_name") or "?"
                        for r in rooms:
                            if dev["name"] in r.get("device_names", []):
                                room_name = r.get("name", "?")
                                break
                        # Tránh duplicate
                        if any(p["dev"]["code"] == dev["code"] for p in plan):
                            continue
                        plan.append({
                            "dev":    dev,
                            "action": act["action"],
                            "value":  act.get("value"),
                            "room":   room_name,
                            "msg":    _localize_action_msg(act["msg"]),
                        })

                if not plan:
                    continue

                # Phân nhóm theo phòng — dùng TẤT CẢ phòng có thiết bị (không chỉ trong plan)
                rooms_in_plan = sorted(set(p["room"] for p in plan if p["room"] != "?"))
                all_rooms_with_devs = rooms_in_plan or sorted(r["name"] for r in rooms if r.get("device_names"))

                owner_room_obj = _resolve_owner_room_obj()
                owner_room_name_resolved = owner_room_obj.get("name") if owner_room_obj else owner_room_name

                # Always ask for confirmation — never execute silently.
                if owner_room_name_resolved and len(all_rooms_with_devs) > 1:
                    # Owner room known + multiple rooms → pre-select owner room, still confirm
                    owner_plan = [p for p in plan if _same_room_name(p.get("room"), owner_room_name_resolved)]
                    if owner_plan:
                        self._set_pending_action({
                            "plan":      owner_plan,
                            "need_room": False,
                        }, user_id=user_id)
                        action_summary = "; ".join(dict.fromkeys(p["msg"] for p in owner_plan))
                        return _reply(_l(
                            f"{scenario['reply_suggest']} Tôi sẽ thực hiện tại phòng {owner_room_name_resolved}: {action_summary}. Ngài có đồng ý không?",
                            f"{scenario['reply_suggest']} I'll do this in room {owner_room_name_resolved}: {action_summary}. Do you confirm?"
                        ))

                if len(all_rooms_with_devs) > 1:
                    # Multiple rooms, owner unknown → ask which room
                    self._set_pending_action({
                        "plan":           plan,
                        "need_room":      True,
                        "scenario_key":   scenario_key,
                        "scenario":       scenario,
                        "all_rooms":      rooms,
                        "house":          house,
                    }, user_id=user_id)
                    opts = ", ".join(_l(f"phòng {r}", f"room {r}") for r in all_rooms_with_devs)
                    action_summary = "; ".join(dict.fromkeys(p["msg"] for p in plan))
                    return _reply(_l(
                        f"{scenario['reply_suggest']} Cụ thể: {action_summary}. Ngài đang ở phòng nào? ({opts})",
                        f"{scenario['reply_suggest']} Specifically: {action_summary}. Which room are you in? ({opts})"
                    ))
                elif rooms_in_plan:
                    # Single room → confirm before executing
                    self._set_pending_action({
                        "plan":      plan,
                        "need_room": False,
                    }, user_id=user_id)
                    action_summary = "; ".join(dict.fromkeys(p["msg"] for p in plan))
                    return _reply(_l(
                        f"{scenario['reply_suggest']} Cụ thể: {action_summary}. Ngài có đồng ý không?",
                        f"{scenario['reply_suggest']} Specifically: {action_summary}. Do you confirm?"
                    ))

        # ── Guard: thuần confirm phrase mà không có pending → không gọi LLM ──
        _CONFIRM_ONLY = {"lam di", "thuc hien di", "tien hanh", "dong y",
                         "xac nhan", "confirm", "proceed", "ok lam", "yes lam",
                         "ừ làm đi", "u lam di", "được rồi làm đi"}
        _msg_norm_check = unicodedata.normalize("NFD", msg_lower)
        _msg_norm_check = "".join(c for c in _msg_norm_check if unicodedata.category(c) != "Mn").strip()
        if _msg_norm_check in _CONFIRM_ONLY or any(p in _msg_norm_check for p in ("lam di", "tien hanh", "xac nhan", "confirm")):
            pending_check = self._get_pending_action(user_id=user_id)
            if not pending_check:
                return _reply(_l(
                    "Thưa Ngài, không có hành động nào đang chờ xác nhận.",
                    "Sir, there is no pending action to confirm."
                ))

        # ══════════════════════════════════════════
        # BƯỚC D: Fallback → LLM parse intent → backend execute
        # LLM chỉ parse intent, KHÔNG chọn device
        # ══════════════════════════════════════════
        final_reply       = _l(
            "Thưa Ngài, tôi chưa hiểu yêu cầu. Ngài có thể nói rõ hơn không?",
            "Sir, I could not understand your request. Could you please clarify?"
        )
        devices_changed   = False
        controlled_devices = []

        if not is_llm_mode:
            # Rule-based mode: không gọi LLM, trả fallback nếu không match rule
            return _reply(_smart_not_understood_reply())

        # ── GEMINI: bypass intent parser — safe for health tips & read-only queries ──
        if mode == "gemini":
            if self.alfred_ai_service:
                try:
                    gemini_message = message if lang != "en" else f"Please respond in English only. User message: {message}"
                    sensor_ctx = (
                        f"Nhà có {len(all_devs)} thiết bị. "
                        f"Floors: {[f.get('name') for f in floors]}. "
                        f"Rooms: {[r.get('name') for r in rooms]}."
                    )
                    gemini_result = self.alfred_ai_service.ask_alfred_with_mood(gemini_message, sensor_ctx, username=username)
                    reply_text = gemini_result.get("reply", "")
                    # ask_alfred_with_mood catches its own errors and returns a fallback string;
                    # treat those as failures so we can fall through to the Rule fallback.
                    _GEMINI_ERR = ("I'm having trouble", "GEMINI_API_KEY", "AI configuration is missing", "Apologies, sir")
                    if not reply_text or any(sig in reply_text for sig in _GEMINI_ERR):
                        raise ValueError(f"Gemini returned error reply: {reply_text[:80]}")
                    mood_data = {
                        "detected_mood": gemini_result.get("detected_mood"),
                        "confidence": gemini_result.get("confidence"),
                        "suggestions": gemini_result.get("recommendations"),
                        "suggested_theme": gemini_result.get("suggested_theme")
                    }
                    logger.debug("Gemini reply with mood: %s", reply_text[:80])
                    return _reply(reply_text, mood_data=mood_data)
                except Exception as e:
                    logger.warning("Gemini error, falling back to Rule response: %s", e)
            # Gemini not configured or failed → Rule engine fallback (user chose Gemini mode,
            # not LLM mode; injecting Ollama here would silently change the inference path).
            return _reply(_smart_not_understood_reply())

        # Safety guard: internal system prompts must not be parsed as commands.
        if message.lstrip().startswith("[HEALTH_TIP_ONLY"):
            try:
                ai_response = self.ai_service.ask_alfred(message, house, preferred_language=lang)
                return _reply(ai_response if isinstance(ai_response, str) else str(ai_response))
            except Exception as e:
                logger.error("Health tip Ollama error: %s", e)
                return _reply(_l("Alfred tạm thời không khả dụng.", "Alfred is temporarily unavailable."))

        try:
            # ── D1: LLM parse intent (prompt ngắn ~150 tokens) ──
            intent = self.ai_service.parse_intent(message)
            logger.debug("Intent: %s", intent)

            intent_type = intent.get("intent", "chat")
            action      = (intent.get("action") or "").lower()
            dev_type    = intent.get("device_type")
            room_name   = intent.get("room")
            floor_name  = intent.get("floor")
            llm_reply   = intent.get("reply")

            if room_name:
                room_alias = _norm(str(room_name)).strip().lower()
                if room_alias in {"nay", "phong nay", "here", "this room", "room"} and owner_room_ctx:
                    room_name = owner_room_ctx

            # ── D2: Chat/hội thoại ──
            if intent_type == "chat":
                final_reply = llm_reply or _smart_not_understood_reply()
                return _reply(final_reply)

            # ── D3: Query thông tin ──
            if intent_type == "query":
                # Query theo floor
                if floor_name:
                    fl = next((f for f in floors if floor_name.lower() in f.get("name","").lower()), None)
                    if fl:
                        fl_rooms = [r for r in rooms if r.get("name","") in fl.get("room_names",[])]
                        parts = []
                        for r in fl_rooms:
                            devs = self._find_devices_in_room(house, r["name"])
                            if devs:
                                parts.append(_l(
                                    f"phòng {r['name']}: {', '.join(d['name'] for d in devs)}",
                                    f"room {r['name']}: {', '.join(d['name'] for d in devs)}"
                                ))
                        if parts:
                            return _reply(_l(
                                f"Thưa Ngài, {fl['name']} có: {'; '.join(parts)}.",
                                f"Sir, {fl['name']} has: {'; '.join(parts)}."
                            ))
                        return _reply(_l(
                            f"Thưa Ngài, {fl['name']} chưa có thiết bị nào.",
                            f"Sir, {fl['name']} has no devices yet."
                        ))
                # Query theo room
                if room_name:
                    devs = self._find_devices_in_room(house, room_name)
                    if devs:
                        return _reply(_l(
                            f"Thưa Ngài, phòng {room_name} có: {', '.join(d['name'] for d in devs)}.",
                            f"Sir, room {room_name} has: {', '.join(d['name'] for d in devs)}."
                        ))
                    return _reply(_l(
                        f"Thưa Ngài, phòng {room_name} chưa có thiết bị nào.",
                        f"Sir, room {room_name} has no devices yet."
                    ))
                return _reply(_l(
                    "Thưa Ngài, Ngài muốn hỏi về phòng hay tầng nào?",
                    "Sir, do you want information about a room or a floor?"
                ))

            # ── D4: Control intent → backend query DB chính xác ──
            # ── Add/create device intent ──
            if intent_type == "add" and self.device_usecase:
                dev_name = intent.get("device_name_raw") or intent.get("device_name")
                if not dev_name:
                    return _reply(_l(
                        "Thưa Ngài, Ngài muốn thêm thiết bị tên gì?",
                        "Sir, what device name would you like to add?"
                    ))
                # Tìm room_id nếu có — lookup từ rooms context hoặc room_usecase
                room_id = None
                if room_name:
                    # Thử từ house context (đã merge từ frontend + DB)
                    room_obj = next((r for r in rooms
                                     if r.get("name","").upper() == room_name.upper()), None)
                    if room_obj:
                        room_id = room_obj.get("id")
                    # Fallback: query DB trực tiếp
                    if not room_id and self.room_usecase and hasattr(self.room_usecase, "get_all_rooms"):
                        db_rooms = self.room_usecase.get_all_rooms()
                        db_room = next((r for r in db_rooms
                                        if str(r.get("name","")).upper() == room_name.upper()), None)
                        if db_room:
                            room_id = db_room.get("id")
                    logger.debug("Room lookup: name=%s -> id=%s", room_name, room_id)
                # Detect category từ dev_type
                cat_map = {"light": "light", "fan": "fan", "ac": "ac",
                           "camera": "camera", "sensor": "sensor"}
                category = cat_map.get(dev_type or "", "other")
                icon_map = {"light": "💡", "fan": "🌀", "ac": "❄️",
                            "camera": "📷", "sensor": "🌡️", "other": "🔌"}
                res = self.device_usecase.create_device({
                    "name": dev_name,
                    "icon": icon_map.get(category, "🔌"),
                    "control_types": ["switch"],
                    "category": category,
                    "room_id": room_id,
                })
                if res.get("success"):
                    room_txt = _l(f" phòng {room_name}", f" in room {room_name}") if room_name else ""
                    # Notify frontend reload device list
                    try:
                        if self.realtime and hasattr(self.realtime, "notify_device_list_changed"):
                            self.realtime.notify_device_list_changed()
                    except Exception:
                        pass
                    return _reply(_l(
                        f"Thưa Ngài, đã thêm thiết bị '{res['name']}' (code: {res['code']}){room_txt} vào hệ thống.",
                        f"Sir, device '{res['name']}' (code: {res['code']}) was added to the system{room_txt}."
                    ))
                return _reply(_l(
                    f"Thưa Ngài, không thể thêm thiết bị '{dev_name}': {res.get('message','lỗi không xác định')}.",
                    f"Sir, I could not add device '{dev_name}': {res.get('message','unknown error')}."
                ))

            # ── Delete intent ──
            if intent_type == "delete" and self.device_usecase:
                dev_name_hint  = intent.get("device_name")
                dev_name_raw   = intent.get("device_name_raw", dev_name_hint)
                # Tìm device theo code hoặc tên (thử cả dạng có space và underscore)
                dev = next((d for d in all_devs
                            if d.get("code","").lower() == (dev_name_hint or "")
                            or d.get("name","").lower() == (dev_name_raw or "")
                            or d.get("code","").lower() == (dev_name_raw or "").replace(" ","_")
                            or d.get("name","").lower().replace(" ","") == (dev_name_raw or "").replace(" ","")),
                           None)
                if not dev:
                    codes = [d.get("code") for d in all_devs]
                    return _reply(_l(
                        f"Thưa Ngài, không tìm thấy thiết bị '{dev_name_raw}'. Thiết bị hiện có: {', '.join(str(c) for c in codes)}.",
                        f"Sir, device '{dev_name_raw}' was not found. Available devices: {', '.join(str(c) for c in codes)}."
                    ))
                res = self.device_usecase.delete_device(dev["name"])
                if res.get("success"):
                    try:
                        if self.realtime and hasattr(self.realtime, "notify_device_list_changed"):
                            self.realtime.notify_device_list_changed()
                    except Exception:
                        pass
                    return _reply(_l(
                        f"Thưa Ngài, đã xóa thiết bị '{dev['name']}' khỏi hệ thống.",
                        f"Sir, device '{dev['name']}' was deleted from the system."
                    ))
                return _reply(_l(
                    f"Thưa Ngài, không thể xóa thiết bị '{dev['name']}'.",
                    f"Sir, I could not delete device '{dev['name']}'."
                ))

            if intent_type == "control" and self.device_usecase:
                action_val = "OFF" if action == "off" else "ON"
                verb     = _l("Đã tắt" if action_val == "OFF" else "Đã bật", "Turned off" if action_val == "OFF" else "Turned on")
                verb_ask = _l("tắt" if action_val == "OFF" else "bật", "turn off" if action_val == "OFF" else "turn on")

                # Query candidates từ DB theo room/floor/type/name
                candidates = []
                device_name_hint = intent.get("device_name")
                device_name_raw  = intent.get("device_name_raw", device_name_hint)
                if device_name_hint:
                    # Tìm theo code hoặc tên trực tiếp
                    matched = next((d for d in all_devs
                        if d.get("code","").lower() == device_name_hint
                        or d.get("name","").lower() == device_name_raw
                        or d.get("code","").lower() == (device_name_raw or "").replace(" ","_")
                        or d.get("name","").lower().replace(" ","") == (device_name_raw or "").replace(" ","")), None)
                    if matched:
                        candidates = [matched]
                if not candidates and room_name:
                    candidates = self._find_devices_in_room(house, room_name)
                elif not candidates and floor_name:
                    fl = next((f for f in floors if floor_name.lower() in f.get("name","").lower()), None)
                    if fl:
                        for rname in fl.get("room_names", []):
                            candidates.extend(self._find_devices_in_room(house, rname))
                elif not candidates and owner_room_ctx:
                    # Không chỉ rõ room/floor: dùng phòng hiện tại theo marker.
                    candidates = self._find_devices_in_room(house, owner_room_ctx)
                else:
                    candidates = [d for d in all_devs if d.get("category","") not in ("sensor","camera")]

                # Filter theo device_type nếu có (strict): không fallback sang toàn bộ phòng.
                if dev_type and candidates:
                    filtered = self._find_devices_by_category({"devices": candidates, "rooms": rooms}, dev_type)
                    candidates = filtered

                # Validation
                if not candidates:
                    if room_name:
                        loc = _l(f"phòng {room_name}", f"room {room_name}")
                    elif floor_name:
                        loc = _l(f"tầng {floor_name}", f"floor {floor_name}")
                    elif owner_room_ctx:
                        loc = _l(f"phòng {owner_room_ctx}", f"room {owner_room_ctx}")
                    else:
                        loc = _l("hệ thống", "the system")
                    return _reply(_l(
                        f"Thưa Ngài, không tìm thấy thiết bị phù hợp trong {loc}.",
                        f"Sir, no matching device was found in {loc}."
                    ))

                if len(candidates) > 1 and not room_name and dev_type:
                    # Nhiều thiết bị cùng loại ở nhiều phòng → hỏi phòng nào
                    room_options = []
                    for d in candidates:
                        for r in rooms:
                            if d["name"] in r.get("device_names", []):
                                room_options.append(_l(f"phòng {r['name']} ({d['name']})", f"room {r['name']} ({d['name']})"))
                                break
                    if room_options:
                        self._set_pending_action({
                            "plan": [{"dev": d, "action": action_val, "value": None,
                                      "msg": f"{verb} {d['name']}", "room": next(
                                          (r["name"] for r in rooms if d["name"] in r.get("device_names",[])), "?"
                                      )} for d in candidates],
                            "need_room": True,
                        }, user_id=user_id)
                        return _reply(_l(
                            f"Thưa Ngài, có {len(candidates)} thiết bị phù hợp: {', '.join(room_options)}. Ngài muốn {verb.lower()} ở đâu?",
                            f"Sir, I found {len(candidates)} matching devices: {', '.join(room_options)}. Where should I {verb.lower()}?"
                        ))

                # Store pending and ask confirmation — chatbot never auto-executes
                plan = [{"dev": d, "action": action_val, "value": None,
                         "msg": f"{verb} {d['name']}"} for d in candidates]
                device_list = ", ".join(_l(f"{verb_ask} {d['name']}", f"{verb_ask} {d['name']}") for d in candidates)
                self._set_pending_action({
                    "kind": "control",
                    "plan": plan,
                    "house": house,
                }, user_id=user_id)
                return _reply(_l(
                    f"Thưa Ngài, tôi sẽ {device_list}. Ngài xác nhận không?",
                    f"Sir, I will {device_list}. Shall I proceed?"
                ))

            # ── MODE ROUTING ──────────────────────────────────────────
            # Nếu tới đây = intent là "chat" thuần (không có lệnh thiết bị rõ ràng)

            # mode="llm" or Gemini failed → Ollama
            ai_response = self.ai_service.ask_alfred(message, house, preferred_language=lang)
            final_reply = ai_response if isinstance(ai_response, str) else str(ai_response)

            # Parse JSON nếu AI trả về lệnh điều khiển
            CTRL_KW = ["bật", "tắt", "mở", "đóng", "turn on", "turn off"]
            has_ctrl_intent = any(w in msg_lower for w in CTRL_KW)

            if isinstance(ai_response, str):
                jmatch = re.search(r'(\{.*\})', ai_response, re.DOTALL)
                if jmatch and has_ctrl_intent:
                    cmd    = json.loads(jmatch.group(1))
                    action = cmd.get("action", "")
                    if action == "control" and not cmd.get("target") and cmd.get("targets"):
                        action = "control_many"

                    if action == "control" and self.device_usecase:
                        target = cmd.get("target", "").strip()
                        val    = cmd.get("value", "ON").strip().upper()
                        dev = next((d for d in all_devs if d["code"] == target), None)
                        if dev:
                            verb_done = _l("Đã tắt" if val == "OFF" else "Đã bật", "Turned off" if val == "OFF" else "Turned on")
                            verb_ask  = _l("tắt" if val == "OFF" else "bật", "turn off" if val == "OFF" else "turn on")
                            plan = [{"dev": dev, "action": val, "value": None, "msg": f"{verb_done} {dev['name']}"}]
                            self._set_pending_action({"kind": "control", "plan": plan, "house": house}, user_id=user_id)
                            final_reply = _l(
                                f"Thưa Ngài, tôi sẽ {verb_ask} {dev['name']}. Ngài xác nhận không?",
                                f"Sir, I will {verb_ask} {dev['name']}. Shall I proceed?"
                            )
                        else:
                            final_reply = _l(
                                f"Thưa Ngài, không tìm thấy thiết bị '{target}' trong hệ thống.",
                                f"Sir, device '{target}' was not found in the system."
                            )

                    elif action == "control_many" and self.device_usecase:
                        plan = []
                        ask_parts = []
                        not_found = []
                        for item in cmd.get("targets", []):
                            code = item.get("code", "").strip()
                            val  = item.get("value", "ON").strip().upper()
                            dev  = next((d for d in all_devs if d["code"] == code), None)
                            if dev:
                                verb_done = _l("Đã tắt" if val == "OFF" else "Đã bật", "Turned off" if val == "OFF" else "Turned on")
                                verb_ask  = _l("tắt" if val == "OFF" else "bật", "turn off" if val == "OFF" else "turn on")
                                plan.append({"dev": dev, "action": val, "value": None, "msg": f"{verb_done} {dev['name']}"})
                                ask_parts.append(f"{verb_ask} {dev['name']}")
                            else:
                                not_found.append(code)
                        if plan:
                            device_list = ", ".join(ask_parts)
                            self._set_pending_action({"kind": "control", "plan": plan, "house": house}, user_id=user_id)
                            suffix = _l(f" (không tìm thấy: {', '.join(not_found)})", f" (not found: {', '.join(not_found)})") if not_found else ""
                            final_reply = _l(
                                f"Thưa Ngài, tôi sẽ {device_list}{suffix}. Ngài xác nhận không?",
                                f"Sir, I will {device_list}{suffix}. Shall I proceed?"
                            )
                        else:
                            final_reply = _l(
                                f"Thưa Ngài, không tìm thấy thiết bị nào. Không tìm thấy: {', '.join(not_found)}.",
                                f"Sir, no matching devices found. Not found: {', '.join(not_found)}."
                            )

                elif jmatch and not has_ctrl_intent:
                    try:
                        cmd_preview = json.loads(jmatch.group(1))
                        if cmd_preview.get("reply"):
                            final_reply = cmd_preview["reply"]
                    except Exception:
                        pass

        except Exception as e:
            logger.error("AI Core error: %s", e)
            final_reply = _l("Thưa Ngài, máy chủ AI đang gặp sự cố.", "Sir, the AI server is currently experiencing an issue.")

        # Notify realtime
        try:
            if self.realtime and hasattr(self.realtime, "notify_ai_reply"):
                self.realtime.notify_ai_reply({
                    "user_message": message,
                    "alfred_reply": final_reply,
                    "timestamp":    datetime.now().strftime("%H:%M:%S")
                })
        except Exception as e:
            logger.warning("Realtime notify error: %s", e)

        return {
            "reply":             final_reply,
            "devices_changed":   devices_changed,
            "controlled_devices": controlled_devices,
        }

    def process_sensors(self, context_data: dict):
        try:
            return self.ai_service.predict_all(context_data)
        except Exception:
            return {}


# ─────────────────────────────────────────
# Helper
# ─────────────────────────────────────────
def _reply(text: str, controlled: list = None, mood_data: dict = None) -> dict:
    logging.getLogger(__name__).debug("Alfred reply: %s", text[:120])
    result = {
        "reply":             text,
        "devices_changed":   bool(controlled),
        "controlled_devices": controlled or [],
    }
    if mood_data:
        result["mood_data"] = mood_data
    return result
