# app/ai/services/ai_service.py
import logging
import os
import re
import requests
from datetime import datetime
from time import perf_counter

logger = logging.getLogger(__name__)


class AIService:

    def __init__(self, model_loader):
        self.loader = model_loader
        _base = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        self.ollama_url = f"{_base}/api/generate"
        self.model_name = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self._connect_ollama()

    # =========================================
    # INIT
    # =========================================

    def _connect_ollama(self):
        _base = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        try:
            resp = requests.get(f"{_base}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                logger.info("Alfred Bat-Computer Online (Ollama - %s)", self.model_name)
                self._preload_model()
                logger.info("Models available: %s", ', '.join(models))
                if self.model_name not in models:
                    for m in models:
                        if "llama" in m or "gemma" in m or "qwen" in m:
                            self.model_name = m
                            logger.warning("Switched to available model: %s", self.model_name)
            else:
                logger.warning("Ollama running but no models found")
        except Exception as e:
            logger.error("Ollama not reachable: %s", e)
            logger.info("Make sure Ollama is running: ollama serve")

    def _preload_model(self):
        import threading as _threading
        def _do():
            try:
                requests.post(
                    self.ollama_url,
                    json={"model": self.model_name, "prompt": "hi", "stream": False,
                          "keep_alive": "10m", "options": {"num_predict": 1}},
                    timeout=30,
                )
                logger.debug("Model %s pre-loaded into RAM", self.model_name)
            except Exception:
                pass
        _threading.Thread(target=_do, daemon=True).start()

    # =========================================
    # INTENT PARSING
    # =========================================

    def parse_intent(self, message: str) -> dict:
        """LLM chỉ parse intent — không chọn device, không ra lệnh."""
        import json as _json
        DEFAULT = {"intent": "chat", "action": None, "device_type": None,
                   "room": None, "floor": None, "reply": None}

        result = self._rule_based_intent(message)
        if result is not None:
            return result

        return self._llm_intent(message, DEFAULT, _json)

    def _rule_based_intent(self, message: str) -> dict | None:
        import re as _re
        msg = message.lower().strip()

        CTRL_ON  = ["bật", "bat", "mở", "mo", "turn on"]
        CTRL_OFF = ["tắt", "tat", "đóng", "dong", "turn off"]
        DELETE_KW = ["xóa", "xoá", "delete", "remove", "xóa bỏ"]
        ADD_KW    = ["thêm", "tạo", "add", "create", "thêm mới"]
        QUERY_KW  = ["có gì", "có bao nhiêu", "bao nhiêu", "có các", "có những",
                     "thiết bị gì", "nào", "liệt kê", "cho biết", "what", "how many"]
        LIGHT_KW  = ["đèn", "light", "đèn điện"]
        FAN_KW    = ["quạt", "fan", "quat"]
        AC_KW     = ["điều hòa", "máy lạnh", "aircon", "lanh"]

        is_ctrl_on  = any(w in msg for w in CTRL_ON)
        is_ctrl_off = any(w in msg for w in CTRL_OFF)
        is_delete   = any(w in msg for w in DELETE_KW)
        is_add      = any(w in msg for w in ADD_KW)
        is_query    = any(w in msg for w in QUERY_KW)

        floor_match = _re.search(r'tầng\s*(\d+)|tang\s*(\d+)|floor\s*(\d+)', msg)
        floor_val = (floor_match.group(1) or floor_match.group(2) or floor_match.group(3)) if floor_match else None

        room_match = _re.search(
            r'\bphòng\s+([\w-]+)|\bphong\s+([\w-]+)|\broom\s+([\w-]+)|\bin\s+([\w-]+)|\bat\s+([\w-]+)',
            msg,
        )
        room_val = (
            (room_match.group(1) or room_match.group(2) or room_match.group(3)
             or room_match.group(4) or room_match.group(5)).upper()
            if room_match else None
        )

        dev_type = None
        if any(w in msg for w in LIGHT_KW): dev_type = "light"
        elif any(w in msg for w in FAN_KW): dev_type = "fan"
        elif any(w in msg for w in AC_KW):  dev_type = "ac"

        device_name_hint = None
        device_name_raw  = None
        for kw in CTRL_ON + CTRL_OFF + DELETE_KW:
            if kw in msg:
                after = msg.split(kw, 1)[-1].strip()
                after = _re.sub(
                    r'\bphòng\s+[\w-]+|\bphong\s+[\w-]+|\broom\s+[\w-]+|\bin\s+[\w-]+|\bat\s+[\w-]+|\btầng\s+\w+|\btang\s+\w+|\bfloor\s+\w+',
                    '',
                    after,
                ).strip()
                if after and len(after) >= 2:
                    device_name_raw  = after
                    device_name_hint = after.replace(' ', '_')
                break

        if is_delete and device_name_hint:
            logger.debug("Rule intent: delete, device=%s", device_name_hint)
            return {"intent": "delete", "action": "delete",
                    "device_name": device_name_hint, "device_name_raw": device_name_raw,
                    "device_type": dev_type, "room": room_val, "floor": floor_val, "reply": None}

        if is_add:
            add_name = self._extract_add_name(msg, ADD_KW, _re)
            logger.debug("Rule intent: add, name=%s, room=%s", add_name, room_val)
            return {"intent": "add", "action": "add",
                    "device_name": add_name, "device_name_raw": add_name,
                    "device_type": dev_type, "room": room_val, "floor": floor_val, "reply": None}

        if (is_ctrl_on or is_ctrl_off) and device_name_hint and not dev_type:
            logger.debug("Rule intent: control device=%s", device_name_hint)
            return {"intent": "control", "action": "on" if is_ctrl_on else "off",
                    "device_name": device_name_hint, "device_name_raw": device_name_raw,
                    "device_type": None, "room": room_val, "floor": floor_val, "reply": None}

        if (is_ctrl_on or is_ctrl_off) and (room_val or floor_val or dev_type):
            logger.debug("Rule intent: control type=%s room=%s", dev_type, room_val)
            return {"intent": "control", "action": "on" if is_ctrl_on else "off",
                    "device_type": dev_type, "room": room_val, "floor": floor_val, "reply": None}

        if is_query and (room_val or floor_val):
            logger.debug("Rule intent: query room=%s floor=%s", room_val, floor_val)
            return {"intent": "query", "action": None,
                    "device_type": dev_type, "room": room_val, "floor": floor_val, "reply": None}

        return None

    def _extract_add_name(self, msg: str, add_keywords: list, re_mod) -> str | None:
        for kw in add_keywords:
            if kw in msg:
                after = msg.split(kw, 1)[-1].strip()
                after = re_mod.sub(r'\bvào\s+phòng\s+\w+|\bvao\s+phong\s+\w+|\bin\s+room\s+\w+|\bin\s+\w+', '', after)
                after = re_mod.sub(r'\bphòng\s+\w+|\broom\s+\w+|\bin\s+\w+|\bat\s+\w+|\btầng\s+\w+|\btang\s+\w+|\bfloor\s+\w+', '', after).strip()
                if after and len(after) >= 2:
                    return after.strip()
        return None

    def _llm_intent(self, message: str, default: dict, json_mod) -> dict:
        prompt = (
            f'Bạn là API parser. CHỈ TRẢ JSON HỢP LỆ, không giải thích, không markdown.\n\n'
            f'Format: {{"intent":"control|query|chat","action":"on|off|null",'
            f'"device_type":"light|fan|ac|null","room":null,"floor":null,"reply":null}}\n\n'
            f'intent: control=bật/tắt, query=hỏi thông tin, chat=hội thoại\n'
            f'action: on=bật/mở, off=tắt/đóng, null=không có lệnh\n\n'
            f'Câu: "{message}"\n\nJSON:'
        )
        try:
            resp = requests.post(
                self.ollama_url,
                json={"model": self.model_name, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.0, "num_predict": 100, "num_ctx": 512}},
                timeout=30,
            )
            raw = self._extract_ollama_text(resp.text.strip(), json_mod)
            logger.debug("LLM raw: %s", raw[:200].replace('\n', ' '))
        except Exception as e:
            logger.warning("parse_intent LLM request error: %s", e)
            return default

        obj = self._parse_json_object(raw, json_mod)
        return obj if obj is not None else default

    def _extract_ollama_text(self, raw_response: str, json_mod) -> str:
        try:
            parsed = json_mod.loads(raw_response)
            if isinstance(parsed, dict):
                return str(parsed.get("response", "")).strip() or raw_response
            if isinstance(parsed, list) and parsed:
                first = parsed[0]
                return str(first.get("response", "")).strip() if isinstance(first, dict) else raw_response
        except json_mod.JSONDecodeError:
            m = re.search(r'"response"\s*:\s*"([^"]*)"', raw_response)
            if m:
                return m.group(1).strip()
        return raw_response

    def _parse_json_object(self, text: str, json_mod) -> dict | None:
        def _normalize(obj):
            if isinstance(obj, dict):
                for k in list(obj.keys()):
                    if obj[k] in ("null", "NULL", ""):
                        obj[k] = None
                return obj
            return None

        depth, start = 0, None
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}' and depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        obj = json_mod.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return _normalize(obj)
                    except Exception:
                        pass
                    start = None

        try:
            return _normalize(json_mod.loads(text))
        except Exception:
            return None

    # =========================================
    # ALFRED CHAT
    # =========================================

    def ask_alfred(self, message: str, house_context: dict | None = None, preferred_language: str = "auto"):
        """Backward-compatible chat API: returns only assistant reply text."""
        result = self.ask_alfred_with_timing(
            message=message,
            house_context=house_context,
            preferred_language=preferred_language,
        )
        return result.get("reply", "")

    def ask_alfred_with_timing(self, message: str, house_context: dict | None = None, preferred_language: str = "auto") -> dict:
        """
        Chat API with timing decomposition.
        Returns: {"reply": str, "timings": {prompt_ms, llm_ms, postprocess_ms, total_ms, error}}
        """
        t_total_s = perf_counter()
        timings = {
            "prompt_ms": 0.0,
            "llm_ms": 0.0,
            "postprocess_ms": 0.0,
            "total_ms": 0.0,
            "error": None,
        }

        try:
            devices   = (house_context or {}).get("devices", [])
            ui_floors = (house_context or {}).get("floors", [])
            ui_rooms  = (house_context or {}).get("rooms", [])

            device_by_name = {d.get("name", ""): d for d in devices}

            house_structure = self._build_house_structure(ui_floors, ui_rooms, device_by_name)
            all_codes_str   = self._build_codes_by_category(devices)
            current_floor   = (house_context or {}).get("current_floor", "TẦNG 1")

            t_prompt_s = perf_counter()
            prompt = self._build_alfred_prompt(message, house_structure, all_codes_str, preferred_language)
            timings["prompt_ms"] = (perf_counter() - t_prompt_s) * 1000
            logger.debug("Prompt length: %d chars / ~%d tokens", len(prompt), len(prompt) // 4)

            t_llm_s = perf_counter()
            text = self._call_ollama(prompt)
            timings["llm_ms"] = (perf_counter() - t_llm_s) * 1000
            if text is None:
                reply = "Bat-computer đang bận xử lý, thưa Ngài. Xin thử lại."
                timings["error"] = "ollama_response_none"
                timings["total_ms"] = (perf_counter() - t_total_s) * 1000
                return {"reply": reply, "timings": timings}
            if not text:
                reply = "Bat-computer không phản hồi, thưa Ngài."
                timings["error"] = "ollama_empty"
                timings["total_ms"] = (perf_counter() - t_total_s) * 1000
                return {"reply": reply, "timings": timings}

            t_post_s = perf_counter()
            reply = self._extract_alfred_response(text)
            timings["postprocess_ms"] = (perf_counter() - t_post_s) * 1000
            timings["total_ms"] = (perf_counter() - t_total_s) * 1000

            logger.debug(
                "ask_alfred timing ms: prompt=%.2f llm=%.2f post=%.2f total=%.2f",
                timings["prompt_ms"],
                timings["llm_ms"],
                timings["postprocess_ms"],
                timings["total_ms"],
            )
            return {"reply": reply, "timings": timings}

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama")
            timings["error"] = "connection_error"
            timings["total_ms"] = (perf_counter() - t_total_s) * 1000
            return {
                "reply": "Thưa Ngài, Bat-computer local chưa khởi động. Vui lòng chạy 'ollama serve' trong terminal.",
                "timings": timings,
            }
        except requests.exceptions.Timeout:
            logger.error("Ollama timeout")
            timings["error"] = "timeout"
            timings["total_ms"] = (perf_counter() - t_total_s) * 1000
            return {
                "reply": "Bat-computer đang suy nghĩ hơi lâu, thưa Ngài. Xin thử lại với câu hỏi ngắn hơn.",
                "timings": timings,
            }
        except Exception as e:
            logger.error("Alfred Error: %s", e)
            timings["error"] = "internal_error"
            timings["total_ms"] = (perf_counter() - t_total_s) * 1000
            return {
                "reply": "Có vẻ như hệ thống đang gặp nhiễu sóng neural, tôi sẽ cố gắng khôi phục lại ngay, thưa Ngài.",
                "timings": timings,
            }

    def _build_codes_by_category(self, devices: list) -> str:
        """Group device codes by category so the LLM knows which codes are lights, fans, etc."""
        from collections import defaultdict
        LABELS = {
            "light":    "[đèn/light]",
            "fan":      "[quạt/fan]",
            "ac":       "[điều hòa/ac]",
            "switch":   "[công tắc/switch]",
            "camera":   "[camera]",
            "sensor":   "[cảm biến - CHỈ ĐỌC, không điều khiển]",
            "actuator": "[thiết bị/actuator]",
        }
        grouped = defaultdict(list)
        for d in devices:
            code = d.get("code") or d.get("name", "")
            if not code:
                continue
            cat = (d.get("category") or "actuator").lower()
            grouped[cat].append(code)

        parts = []
        for cat, codes in grouped.items():
            label = LABELS.get(cat, f"[{cat}]")
            parts.append(f"{label}: {', '.join(codes)}")
        return "\n".join(parts) if parts else "chưa có thiết bị"

    def _build_house_structure(self, ui_floors: list, ui_rooms: list, device_by_name: dict) -> str:
        room_lookup = {r.get("name"): r for r in ui_rooms}
        lines = []
        for fl in ui_floors:
            fname = fl.get("name", "")
            lines.append(f"[{fname}]")
            room_names = fl.get("room_names", [])
            if room_names:
                for rname in room_names:
                    room_obj = room_lookup.get(rname)
                    rdevs  = room_obj.get("device_names", []) if room_obj else []
                    codes  = [device_by_name[n].get("code", n) for n in rdevs if n in device_by_name]
                    devs_str = ", ".join(codes) if codes else "chua co thiet bi"
                    lines.append(f"  * Phong {rname} chi co: {devs_str}")
            else:
                lines.append("  (chua co phong)")
        return "\n".join(lines) or "Chua co du lieu"

    def _build_alfred_prompt(self, message: str, house_structure: str, all_codes_str: str, preferred_language: str = "auto") -> str:
        pref = str(preferred_language or "auto").lower()
        if pref.startswith("en"):
            language_policy = (
                "ALWAYS reply in English only. Never use Vietnamese. "
                "Address user as 'Sir'."
            )
        elif pref.startswith("vi"):
            language_policy = (
                "LUÔN trả lời bằng tiếng Việt. Không dùng tiếng Anh trừ tên riêng/kỹ thuật. "
                "Xưng hô 'Thưa Ngài'."
            )
        else:
            language_policy = (
                "Phát hiện ngôn ngữ của tin nhắn người dùng và LUÔN trả lời cùng ngôn ngữ đó. "
                "Nếu tiếng Anh thì xưng 'Sir', nếu tiếng Việt thì xưng 'Thưa Ngài'."
            )

        return f"""Bạn là Alfred, quản gia AI của Batcave Smart Home.
{language_policy}
Trả lời NGẮN GỌN, súc tích. KHÔNG dùng "...".

━━━ HỘI THOẠI THÔNG THƯỜNG → TRẢ TEXT ━━━
Chào hỏi, tin nhắn xã giao, thời gian trong ngày → trả lời bình thường bằng text.
Ví dụ: "hello", "chiều rồi", "bạn khỏe không", "cảm ơn" → KHÔNG điều khiển thiết bị.

━━━ THÔNG TIN CÂU HỎI → TRẢ TEXT NGẮN ━━━
Trả lời 1-2 câu, liệt kê thẳng vào. Ví dụ:
- "tầng 1 có mấy phòng" → "Thưa Ngài, tầng 1 có 3 phòng: A, B, C."
- "thiết bị phòng B" → "Thưa Ngài, phòng B có: maylanh, ac."
- Luôn nêu rõ TÊN PHÒNG khi liệt kê thiết bị theo tầng.

━━━ ĐIỀU KHIỂN → CHỈ TRẢ JSON THUẦN ━━━
Chỉ dùng JSON khi CÓ từ khóa điều khiển RÕ RÀNG: bật/tắt/mở/đóng/turn on/turn off.
KHÔNG điều khiển khi hỏi thông tin.
1 thiết bị:
{{"action":"control","target":"CODE","value":"ON","reply":"Đã bật..."}}

Nhiều thiết bị:
{{"action":"control_many","targets":[{{"code":"CODE1","value":"OFF"}},{{"code":"CODE2","value":"OFF"}}],"reply":"Đã tắt..."}}

⚠️ QUY TẮC BẮT BUỘC:
- PHẢI dùng code CHÍNH XÁC trong danh sách bên dưới
- Cảm biến (loại "chỉ đọc") KHÔNG điều khiển được
- MỖI target PHẢI có đủ "code" VÀ "value"
- "bật/mở/turn on" → value="ON" | "tắt/đóng/turn off" → value="OFF"
- "tắt/bật phòng X" → control_many với TẤT CẢ code của phòng X
- "tắt hết" → control_many với TẤT CẢ code (trừ cảm biến)
- Nếu phòng KHÔNG tồn tại → trả text: "Thưa Ngài, không tìm thấy phòng [tên phòng]."

CẤU TRÚC NHÀ (tầng → phòng → thiết bị):
{house_structure}

TẤT CẢ CODE HỢP LỆ theo loại (chỉ dùng code trong danh sách này):
{all_codes_str}

YÊU CẦU: "{message}"

Trả lời bằng văn xuôi tiếng Việt tự nhiên. JSON nếu điều khiển:"""

    def _call_ollama(self, prompt: str) -> str | None:
        resp = requests.post(
            self.ollama_url,
            json={
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.2,
                    "num_predict": 600,
                    "num_ctx": 2048,
                    "stop": ["\n\n", "YÊU CẦU:"],
                },
            },
            timeout=180,
        )
        if resp.status_code != 200:
            logger.error("Ollama Error: %s - %s", resp.status_code, resp.text)
            return None
        return resp.json().get("response", "").strip()

    def _extract_alfred_response(self, text: str) -> str:
        text_clean = re.sub(r'```(?:json)?\s*', '', text).replace('```', '').strip()
        match = re.search(r'(\{.*\})', text_clean, re.DOTALL)
        if match:
            return match.group(1)
        return text_clean

    # =========================================
    # SENSOR PREDICTION
    # =========================================

    def predict_all(self, raw_data: dict):
        try:
            from app.ai.data.feature_engineering import transform_to_features
            X = transform_to_features(raw_data)
            scaler = self.loader.get_model("scaler")
            if scaler:
                X = scaler.transform(X)
            return {
                "anomaly": self.anomaly_engine.detect(X),
                "mood": self.mood_engine.predict(X),
            }
        except Exception:
            return {}
