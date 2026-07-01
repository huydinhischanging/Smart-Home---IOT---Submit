# app/ai/services/schedule_intent_parser.py
# ============================================================
# Parse time-based scheduling intent from natural language.
# Supports Vietnamese and English, single time + repeat pattern.
#
# Examples handled:
#   "bật quạt lúc 10 giờ tối"      → fan ON 22:00 daily
#   "mỗi tối 22 giờ tắt đèn"       → light OFF 22:00 daily
#   "tắt quạt lúc 23:30 mỗi ngày"  → fan OFF 23:30 daily
#   "turn on fan at 10pm every night" → fan ON 22:00 daily
#   "bật đèn lúc 6 giờ sáng thứ 2-6" → light ON 06:00 weekdays
# ============================================================
import re
import unicodedata


# ── Normalise Vietnamese diacritics ──────────────────────────
def _norm(text: str) -> str:
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


# ── Device category keyword map ──────────────────────────────
_DEVICE_KEYWORDS: dict[str, list[str]] = {
    "fan":    ["quạt", "quat", "fan"],
    "light":  ["đèn", "den", "light", "lamp", "bóng đèn"],
    "ac":     ["điều hòa", "dieu hoa", "ac", "air con", "máy lạnh", "may lanh"],
    "tv":     ["tivi", "tv", "television", "màn hình", "man hinh"],
    "speaker":["loa", "speaker", "âm thanh", "am thanh", "nhạc", "nhac"],
    "outlet": ["ổ cắm", "o cam", "outlet", "socket", "plug"],
}

# ── Time-period modifiers ────────────────────────────────────
# Maps suffix → (add_hours_if_hour_lt, only_if_hour_range)
# Rule:
#   tối / evening  → + 12 when hour 1-9 (e.g. 9 giờ tối = 21:00)
#                    keep when hour 10-12 (10 giờ tối = 22:00, so still +12 if <12)
#   chiều / afternoon → + 12 when hour 1-6 (3 giờ chiều = 15:00)
#   sáng / morning  → keep hour as-is (6 giờ sáng = 06:00)
#   trưa / noon     → 12:00 (override hour to 12)
_PERIOD_MAP = {
    # Vietnamese (with diacritics)
    "tối":     "pm",
    "chiều":   "pm",
    "đêm":     "pm",
    "sáng":    "am",
    "trưa":    "noon",
    # Vietnamese (ASCII-normalised — what _norm() produces)
    "toi":     "pm",
    "chieu":   "pm",
    "dem":     "pm",
    "sang":    "am",
    "trua":    "noon",
    # English
    "night":     "pm",
    "evening":   "pm",
    "afternoon": "pm",
    "morning":   "am",
    "noon":      "noon",
    # Raw am/pm tokens — must resolve to themselves
    "am":  "am",
    "pm":  "pm",
}

# ── Repeat pattern keywords ──────────────────────────────────
_REPEAT_DAILY    = ["mỗi ngày", "moi ngay", "hàng ngày", "hang ngay",
                    "every day", "everyday", "daily", "mỗi tối", "moi toi",
                    "mỗi sáng", "moi sang", "mỗi đêm", "moi dem",
                    "every night", "every morning", "every evening"]
_REPEAT_WEEKDAYS = ["thứ 2-6", "thu 2-6", "thứ hai đến thứ sáu",
                    "weekdays", "weekday", "mon-fri", "monday to friday"]
_REPEAT_WEEKENDS = ["thứ 7 chủ nhật", "cuối tuần", "cuoi tuan",
                    "weekend", "weekends", "sat-sun"]

# ── Day-of-week name map (normalised → cron DOW number) ──────
# 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
# Longer patterns must come before shorter abbreviations to prevent
# "monday" being double-matched by both "monday" and "mon".
_DOW_PATTERNS: list[tuple[str, int]] = [
    # English (full → short)
    ("monday",    1), ("tuesday",   2), ("wednesday", 3),
    ("thursday",  4), ("friday",    5), ("saturday",  6), ("sunday",    0),
    ("mon",       1), ("tue",       2), ("wed",       3),
    ("thu",       4), ("fri",       5), ("sat",       6), ("sun",       0),
    # Vietnamese normalised (thứ X → thu x, chủ nhật → chu nhat)
    ("thu hai",   1), ("thu ba",    2), ("thu tu",    3),
    ("thu nam",   4), ("thu sau",   5), ("thu bay",   6), ("chu nhat",  0),
    # Short Vietnamese codes
    ("t2",        1), ("t3",        2), ("t4",        3),
    ("t5",        4), ("t6",        5), ("t7",        6), ("cn",        0),
]

# ── Schedule-trigger words ───────────────────────────────────
_SCHEDULE_TRIGGER = [
    "lúc", "luc", "vào lúc", "vao luc", "hẹn", "hen",
    "đặt lịch", "dat lich", "tự động", "tu dong",
    "at", "schedule", "set", "every", "mỗi", "moi", "hàng", "hang",
    "on monday", "on tuesday", "on wednesday", "on thursday",
    "on friday", "on saturday", "on sunday",
    "vao thu", "vào thứ",
]

# ── Action words ─────────────────────────────────────────────
_ON_KW  = ["bật", "bat", "mở", "mo", "turn on", "switch on", "on"]
_OFF_KW = ["tắt", "tat", "khóa", "khoa", "turn off", "switch off", "off"]

# ── Lifestyle activity keywords (no device inferred) ─────────
# When user says "sleep at 9pm" without a device name, we detect the
# activity so the caller can prompt for the desired device instead of
# guessing.  Maps normalised keyword → activity label (English).
_LIFESTYLE_KEYWORDS: dict[str, str] = {
    "sleep":    "Sleep time",
    "bedtime":  "Sleep time",
    "bed time": "Sleep time",
    "ngu":      "Giờ ngủ",      # normalised "ngủ"
    "di ngu":   "Giờ ngủ",      # "đi ngủ"
    "di nghi":  "Giờ ngủ",      # "đi nghỉ"
    "nghi ngu": "Giờ ngủ",
    "wake up":  "Wake-up time",
    "wakeup":   "Wake-up time",
    "thuc day": "Thức dậy",     # "thức dậy"
}


def _detect_device(text_norm: str) -> str | None:
    """Return device category string if found, else None."""
    for cat, kws in _DEVICE_KEYWORDS.items():
        for kw in kws:
            if _norm(kw) in text_norm:
                return cat
    return None


def detect_lifestyle_keyword(text_norm: str) -> str | None:
    """Return activity label if a lifestyle keyword is found, else None."""
    for kw, label in _LIFESTYLE_KEYWORDS.items():
        if _norm(kw) in text_norm:
            return label
    return None


def _detect_action(text: str) -> str | None:
    tl = text.lower()
    # Check OFF first (longer match wins over ON substring)
    for kw in _OFF_KW:
        if kw in tl:
            return "OFF"
    for kw in _ON_KW:
        if kw in tl:
            return "ON"
    return None


def _detect_repeat(text_norm: str) -> str:
    for kw in _REPEAT_WEEKDAYS:
        if _norm(kw) in text_norm:
            return "weekdays"
    for kw in _REPEAT_WEEKENDS:
        if _norm(kw) in text_norm:
            return "weekends"
    # Default daily — any time-based command without explicit repeat = daily
    return "daily"


def _to_24h(hour: int, minute: int, period_raw: str | None) -> tuple[int, int]:
    """Convert to 24-hour clock using the detected period modifier."""
    if period_raw is None:
        # Heuristic: hour < 7 with no modifier → assume PM (night)
        if 1 <= hour <= 6:
            return hour + 12, minute
        return hour, minute

    period = _PERIOD_MAP.get(period_raw, "")
    if period == "noon":
        return 12, minute
    if period == "am":
        if hour == 12:
            return 0, minute
        return hour, minute
    if period == "pm":
        if hour < 12:
            return hour + 12, minute
        return hour, minute
    return hour, minute


def _detect_time(text: str) -> tuple[int, int, str | None] | None:
    """
    Try to extract (hour, minute, period_keyword) from text.
    Returns None if no time found.

    Patterns matched:
      22:30, 22h30, 22 giờ 30, 22 gio 30
      10 giờ tối, 10h tối, 10pm, 10:00pm
      lúc 6h, lúc 6 giờ
    """
    text_lower = text.lower()

    # --- Pattern 1: HH:MM or HH:MM(am/pm) ---
    m = re.search(r'\b(\d{1,2}):(\d{2})\s*(am|pm|sáng|sang|tối|toi|chiều|chieu|đêm|dem)?\b',
                  text_lower)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        period = m.group(3)
        h, mn = _to_24h(h, mn, period)
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return h, mn, period

    # --- Pattern 2: HHh or HHhMM (e.g. 22h, 22h30, 10h30) ---
    m = re.search(r'\b(\d{1,2})h(\d{2})?\s*(am|pm|sáng|sang|tối|toi|chiều|chieu|đêm|dem)?\b',
                  text_lower)
    if m:
        h  = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        period = m.group(3)
        h, mn = _to_24h(h, mn, period)
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return h, mn, period

    # --- Pattern 3: "X giờ Y phút" or "X gio" ---
    m = re.search(
        r'\b(\d{1,2})\s*(?:giờ|gio|giờ|hour|o\'?clock)'
        r'(?:\s*(\d{1,2})\s*(?:phút|phut|minute|min))?'
        r'\s*(sáng|sang|tối|toi|chiều|chieu|đêm|dem|trưa|trua|morning|afternoon|evening|night|noon|am|pm)?',
        text_lower)
    if m:
        h  = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        period = m.group(3)
        h, mn = _to_24h(h, mn, period)
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return h, mn, period

    # --- Pattern 4: "Xpm" / "Xam" stuck together ---
    m = re.search(r'\b(\d{1,2})\s*(am|pm)\b', text_lower)
    if m:
        h = int(m.group(1))
        period = m.group(2)
        h, mn = _to_24h(h, 0, period)
        if 0 <= h <= 23:
            return h, 0, period

    return None


def _detect_specific_days(text_norm: str) -> list[int] | None:
    """
    Return sorted day-of-week numbers if specific day names are found, else None.
    Uses word-boundary matching so 'thu' won't match inside 'thursday'.
    """
    found: set[int] = set()
    for pattern, day_num in _DOW_PATTERNS:
        if re.search(r'(?<![a-z])' + re.escape(pattern) + r'(?![a-z])', text_norm):
            found.add(day_num)
    return sorted(found) if found else None


# Day abbreviations used in labels (index = cron DOW: 0=Sun..6=Sat)
_DOW_LABEL = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _repeat_to_cron(repeat: str, hour: int, minute: int,
                    specific_days: list[int] | None = None) -> str:
    if repeat == "specific" and specific_days:
        days_str = ",".join(str(d) for d in sorted(specific_days))
        return f"{minute} {hour} * * {days_str}"
    if repeat == "weekdays":
        return f"{minute} {hour} * * 1-5"
    if repeat == "weekends":
        return f"{minute} {hour} * * 6,0"
    return f"{minute} {hour} * * *"  # daily


def _has_schedule_trigger(text_lower: str) -> bool:
    return any(t in text_lower for t in _SCHEDULE_TRIGGER)


# ── Delete-schedule trigger words ────────────────────────────
_DELETE_TRIGGER = [
    "xóa lịch", "xoa lich", "hủy lịch", "huy lich", "bỏ lịch", "bo lich",
    "xóa", "xoa",
    "delete schedule", "remove schedule", "cancel schedule",
    "stop schedule",
]

# Standalone delete verbs — only valid when "lịch"/"lich"/"schedule" also present
_DELETE_VERB_ONLY = ["hủy", "huy", "bỏ", "bo", "delete", "remove"]
_SCHEDULE_NOUN   = ["lịch", "lich", "schedule", "cron"]


# ── Public API ────────────────────────────────────────────────

def parse_delete_schedule_intent(message: str) -> dict | None:
    """
    Detect intent to DELETE an existing schedule.

    Returns dict with optional keys:
        device_category : str | None
        action          : str | None  "ON" | "OFF"
        hour            : int | None
        minute          : int | None
        cron_expr       : str | None
        time_str        : str | None
    or None if the message is not a delete-schedule command.
    """
    text_lower = message.lower()
    text_norm  = _norm(message)

    has_delete = any(_norm(d) in text_norm for d in _DELETE_TRIGGER)
    if not has_delete:
        # Standalone verbs only count when schedule noun also present
        has_verb = any(_norm(v) in text_norm for v in _DELETE_VERB_ONLY)
        has_noun = any(_norm(n) in text_norm for n in _SCHEDULE_NOUN)
        if not (has_verb and has_noun):
            return None

    time_result  = _detect_time(message)
    device_cat   = _detect_device(text_norm)
    action       = _detect_action(message)

    hour   = time_result[0] if time_result else None
    minute = time_result[1] if time_result else None
    cron   = None
    if hour is not None and minute is not None:
        repeat = _detect_repeat(text_norm)
        cron   = _repeat_to_cron(repeat, hour, minute)

    return {
        "device_category": device_cat,
        "action":          action,
        "hour":            hour,
        "minute":          minute,
        "cron_expr":       cron,
        "time_str":        f"{hour:02d}:{minute:02d}" if hour is not None else None,
    }


def parse_schedule_intent(message: str) -> dict | None:
    """
    Parse a scheduling intent from natural language.

    Supported patterns:
      "turn off fan at 10pm every day"
      "bật đèn lúc 7 giờ thứ 2, thứ 5"
      "turn off light on Monday and Thursday at 9pm"

    Returns a dict with keys:
        device_category : str
        action          : str   "ON" | "OFF"
        hour            : int
        minute          : int
        repeat          : str   "daily" | "weekdays" | "weekends" | "specific"
        specific_days   : list[int]   day numbers when repeat=="specific"
        cron_expr       : str
        label           : str
        time_str        : str
    or None if not a scheduling command.
    """
    text_lower = message.lower()
    text_norm  = _norm(message)

    # Detect specific day names early — they imply schedule intent.
    specific_days = _detect_specific_days(text_norm)

    # Must have a schedule trigger OR explicit day names.
    if not _has_schedule_trigger(text_lower) and not specific_days:
        return None

    # Must have a time expression.
    time_result = _detect_time(message)
    if not time_result:
        return None

    hour, minute, _period = time_result

    # Must have an explicit device keyword.
    device_cat = _detect_device(text_norm)
    if not device_cat:
        return None

    # Must have an action; fall back to ON.
    action = _detect_action(message) or "ON"

    # Determine repeat pattern — specific days take priority.
    if specific_days:
        repeat    = "specific"
        cron_expr = _repeat_to_cron("specific", hour, minute, specific_days)
    else:
        repeat    = _detect_repeat(text_norm)
        cron_expr = _repeat_to_cron(repeat, hour, minute)
        specific_days = []

    time_str = f"{hour:02d}:{minute:02d}"

    # Human-readable label
    action_vi = "Bật" if action == "ON" else "Tắt"
    cat_vi = {
        "fan": "quạt", "light": "đèn", "ac": "điều hòa",
        "tv": "TV", "speaker": "loa", "outlet": "ổ cắm",
    }.get(device_cat, device_cat)
    if repeat == "specific":
        repeat_vi = ", ".join(_DOW_LABEL[d] for d in specific_days)
    else:
        repeat_vi = {"daily": "hàng ngày", "weekdays": "T2-T6",
                     "weekends": "cuối tuần"}.get(repeat, "hàng ngày")
    label = f"{action_vi} {cat_vi} lúc {time_str} ({repeat_vi})"

    return {
        "device_category": device_cat,
        "action":          action,
        "hour":            hour,
        "minute":          minute,
        "repeat":          repeat,
        "specific_days":   specific_days,
        "cron_expr":       cron_expr,
        "label":           label,
        "time_str":        time_str,
    }
