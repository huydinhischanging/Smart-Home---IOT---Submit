# ============================================================
# ALFRED KNOWLEDGE BASE — Batcave Smart Home
# Mood System + Device Scenarios + Suggestions
# ============================================================

CATEGORY_MAP = {
    "fan":     ["fan"],
    "ac":      ["ac"],
    "light":   ["light"],
    "switch":  ["switch"],
    "sensor":  ["sensor"],
    "camera":  ["camera"],
    "tv":      ["tv"],
    "speaker": ["speaker"],
}

# ============================================================
# MOOD SYSTEM — detect tâm trạng + đề xuất
# ============================================================
MOOD_PROFILES = {

    "buồn": {
        "keywords": ["buồn", "sad", "chán nản", "không vui", "tệ quá", "tôi thấy tệ",
                     "cô đơn", "lonely", "unhappy", "depressed", "thất vọng",
                     "down", "blue", "upset", "feeling sad", "i'm sad", "i feel sad",
                     "feeling down", "not okay", "feeling low", "heartbroken", "miserable"],
        "device_actions": [
            {"category": "light",   "action": "ON",  "value": 35, "msg": "đèn ấm dịu 35%"},
            {"category": "ac",      "action": "ON",  "value": 26, "msg": "điều hòa 26°C dễ chịu"},
            {"category": "speaker", "action": "ON",  "msg": "nhạc chill/lo-fi"},
        ],
        "movies": [
            {"title": "Her (2013)", "why": "Phim về cô đơn và kết nối — rất chữa lành"},
            {"title": "The Secret Life of Walter Mitty (2013)", "why": "Truyền cảm hứng, nhẹ nhàng"},
            {"title": "Chef (2014)", "why": "Ấm lòng, về việc tìm lại bản thân"},
        ],
        "music": ["Lo-fi Hip Hop", "Chill Acoustic", "Nhạc không lời nhẹ nhàng"],
        "message": "Thưa Ngài, tôi nhận thấy Ngài đang không ổn. Tôi có thể chỉnh đèn dịu, bật nhạc thư giãn và đề xuất phim hay. Ngài có muốn không?",
        "companion_msg": "Thưa Ngài, nếu Ngài muốn tâm sự, tôi luôn ở đây lắng nghe.",
    },

    "vui": {
        "keywords": ["vui", "happy", "phấn khởi", "tuyệt vời", "tốt quá", "great",
                     "excited", "hạnh phúc", "tuyệt", "awesome", "hype",
                     "joyful", "cheerful", "glad", "wonderful", "fantastic",
                     "i'm happy", "feeling great", "great mood", "feeling good",
                     "so happy", "overjoyed", "thrilled", "delighted"],
        "device_actions": [
            {"category": "light",   "action": "ON",  "value": 100, "msg": "đèn sáng rực 100%"},
            {"category": "speaker", "action": "ON",  "msg": "nhạc upbeat/vui nhộn"},
            {"category": "fan",     "action": "ON",  "value": 3,   "msg": "quạt vừa phải"},
        ],
        "movies": [
            {"title": "Guardians of the Galaxy (2014)", "why": "Vui nhộn, hành động, nhạc hay"},
            {"title": "The Grand Budapest Hotel (2014)", "why": "Quirky và đầy màu sắc"},
            {"title": "Paddington 2 (2017)", "why": "Ấm áp và vui vẻ tuyệt đối"},
        ],
        "music": ["Pop Hits", "Dance Music", "Nhạc EDM", "Upbeat Playlist"],
        "message": "Thưa Ngài, tuyệt vời! Tôi có thể bật đèn sáng và nhạc vui nhộn để ăn mừng. Ngài có muốn không?",
        "companion_msg": None,
    },

    "chán": {
        "keywords": ["chán", "bored", "chán quá", "không biết làm gì", "nhàm",
                     "vô vị", "thế này thôi sao", "lười",
                     "boring", "dull", "nothing to do", "meh", "blah",
                     "so bored", "i'm bored", "listless", "lazy", "nothing to do",
                     "monotonous", "tedious", "uneventful"],
        "device_actions": [
            {"category": "light",   "action": "ON",  "value": 60, "msg": "đèn vừa phải 60%"},
            {"category": "tv",      "action": "ON",  "msg": "bật TV"},
            {"category": "ac",      "action": "ON",  "value": 25, "msg": "điều hòa 25°C"},
        ],
        "movies": [
            {"title": "Inception (2010)", "why": "Phim đủ phức tạp để kích thích não"},
            {"title": "The Matrix (1999)", "why": "Kinh điển, luôn hay"},
            {"title": "Interstellar (2014)", "why": "Vũ trụ bao la — không còn chán nữa"},
        ],
        "music": ["Podcast thú vị", "Nhạc Jazz", "Lo-fi Study"],
        "message": "Thưa Ngài, khi chán thì xem phim hay nhất 🎬 Tôi đề xuất bật TV và điều hòa cho thoải mái. Ngài có muốn không?",
        "companion_msg": "Thưa Ngài, nếu muốn thử điều gì đó mới, Ngài cứ nói.",
    },

    "buồn_ngủ": {
        "keywords": ["buồn ngủ", "ngủ gật", "mắt díu lại", "sleepy", "drowsy",
                     "mệt lắm", "cần ngủ", "졸려", "ngủ thôi",
                     "tired", "exhausted", "i'm sleepy", "feeling sleepy",
                     "so tired", "can't keep eyes open", "need sleep", "falling asleep"],
        "device_actions": [
            {"category": "light",   "action": "ON",  "value": 10,  "msg": "đèn rất mờ 10%"},
            {"category": "ac",      "action": "ON",  "value": 27,  "msg": "điều hòa 27°C dễ ngủ"},
            {"category": "tv",      "action": "OFF", "msg": "tắt TV"},
            {"category": "speaker", "action": "ON",  "msg": "white noise/tiếng mưa"},
            {"category": "fan",     "action": "OFF", "msg": "tắt quạt"},
        ],
        "movies": [],  # Không đề xuất phim khi buồn ngủ
        "music": ["White Noise", "Tiếng mưa", "Rain Sound", "Sleep Music"],
        "message": "Thưa Ngài, Ngài cần nghỉ ngơi rồi. Tôi có thể tắt bớt đèn, điều chỉnh điều hòa và bật tiếng mưa để dễ ngủ. Ngài có muốn không?",
        "companion_msg": "Chúc Ngài ngủ ngon. Tôi sẽ giữ yên lặng.",
    },

    "stress": {
        "keywords": ["stress", "áp lực", "căng thẳng", "overwhelmed", "quá tải",
                     "mệt não", "đầu óc trống rỗng", "burnout", "kiệt sức"],
        "device_actions": [
            {"category": "light",   "action": "ON",  "value": 40, "msg": "đèn dịu 40%"},
            {"category": "ac",      "action": "ON",  "value": 25, "msg": "điều hòa 25°C"},
            {"category": "speaker", "action": "ON",  "msg": "nhạc thiền/thư giãn"},
            {"category": "tv",      "action": "OFF", "msg": "tắt TV"},
        ],
        "movies": [
            {"title": "Julie & Julia (2009)", "why": "Nhẹ nhàng, ấm cúng, không cần suy nghĩ nhiều"},
            {"title": "Studio Ghibli films", "why": "Miyazaki luôn chữa lành — thử Spirited Away"},
            {"title": "Chef's Table (series)", "why": "Nghệ thuật ẩm thực thư giãn tâm hồn"},
        ],
        "music": ["Nhạc thiền", "Nature Sounds", "Classical Music", "Ambient"],
        "message": "Thưa Ngài, hãy thở sâu — tôi có thể tạo không gian yên tĩnh, đèn dịu và nhạc thư giãn. Ngài có muốn không?",
        "companion_msg": "Thưa Ngài, đôi khi nghỉ ngơi 10 phút còn hiệu quả hơn làm thêm 2 giờ.",
    },

    "bệnh": {
        "keywords": ["bệnh", "ốm", "sốt", "đau đầu", "sick", "fever", "không khỏe",
                     "cảm cúm", "mệt mỏi", "đau bụng", "bị ho", "ho khan", "sổ mũi"],
        "device_actions": [
            {"category": "ac",      "action": "ON",  "value": 28, "msg": "điều hòa 28°C ấm áp"},
            {"category": "light",   "action": "ON",  "value": 30, "msg": "đèn dịu 30%"},
            {"category": "fan",     "action": "OFF", "msg": "tắt quạt (tránh gió lạnh)"},
            {"category": "tv",      "action": "OFF", "msg": "tắt TV"},
        ],
        "movies": [
            {"title": "Studio Ghibli films", "why": "Nhẹ nhàng, không cần suy nghĩ"},
            {"title": "Friends (series)", "why": "Xem lại để cảm thấy dễ chịu hơn"},
        ],
        "music": ["Nhạc nhẹ", "Acoustic", "Classical"],
        "reminders": [
            "💧 Nhớ uống đủ nước",
            "💊 Nhớ uống thuốc đúng giờ",
            "🛏️ Nghỉ ngơi nhiều hơn",
        ],
        "message": "Thưa Ngài, Ngài cần nghỉ ngơi. Tôi có thể chỉnh nhiệt độ ổn định và tắt bớt thiết bị. Ngài có muốn không?",
        "companion_msg": "Thưa Ngài, đừng quên uống nước và thuốc nhé. Tôi lo lắng cho Ngài.",
    },

    "lãng_mạn": {
        "keywords": ["lãng mạn", "romantic", "hẹn hò", "date", "tình cảm", "người yêu",
                     "valentine", "ấm cúng", "cozy"],
        "device_actions": [
            {"category": "light",   "action": "ON",  "value": 20, "msg": "đèn lãng mạn 20%"},
            {"category": "speaker", "action": "ON",  "msg": "nhạc nhẹ lãng mạn"},
            {"category": "ac",      "action": "ON",  "value": 25, "msg": "điều hòa 25°C dễ chịu"},
            {"category": "tv",      "action": "OFF", "msg": "tắt TV"},
        ],
        "movies": [
            {"title": "La La Land (2016)", "why": "Nhạc tuyệt, hình ảnh đẹp"},
            {"title": "Amélie (2001)", "why": "Lãng mạn, quirky và đáng yêu"},
            {"title": "Before Sunrise (1995)", "why": "Nói chuyện và đi dạo — đơn giản mà sâu sắc"},
        ],
        "music": ["Jazz", "Nhạc Pháp", "Acoustic Love Songs", "Soft R&B"],
        "message": "Thưa Ngài, để tôi tạo không gian ấm cúng — đèn mờ, nhạc nhẹ. Ngài có muốn không?",
        "companion_msg": None,
    },

    "tâm_sự": {
        "keywords": ["tôi muốn tâm sự", "nói chuyện với tôi", "tôi thấy tệ",
                     "bạn có nghe không", "tôi cần ai đó", "listen to me",
                     "talk to me", "tôi muốn chia sẻ"],
        "device_actions": [
            {"category": "light",   "action": "ON",  "value": 40, "msg": "đèn dịu nhẹ"},
            {"category": "speaker", "action": "OFF", "msg": "tắt nhạc để yên tĩnh"},
        ],
        "movies": [],
        "music": [],
        "message": None,  # Không đề xuất device — chỉ chat
        "companion_msg": "Thưa Ngài, tôi đây lắng nghe. Ngài muốn chia sẻ điều gì?",
        "chat_mode": True,  # Chuyển sang chat mode
    },
}

# ============================================================
# ENVIRONMENTAL INTENT MAP
# Maps environmental context keywords → device categories + actions.
# Each category key must match the `category` field stored in the DB
# (set when the device is registered: fan, ac, light, tv, speaker…).
# Alfred uses _find_devices_by_category() to resolve the actual device
# (e.g. "fan1") that belongs to each parent category at runtime.
#
# Sensor-type intents (motion, smoke, gas) are NOT listed here —
# they trigger alerts, not commands, and are handled by the alert pipeline.
# ============================================================
ENVIRONMENTAL_INTENTS = {
    "hot": {
        "keywords": ["nóng", "nực", "oi", "bức", "hot", "warm", "ngột ngạt",
                     "stuffy", "too hot", "burning", "sweating", "sweltering",
                     "it's hot", "so hot", "feel hot", "feeling hot", "boiling",
                     "outside is hot", "it's too hot"],
        "actions": [
            {"category": "fan",   "action": "ON",  "value": 3,  "msg": "bật quạt tốc độ 3"},
            {"category": "ac",    "action": "ON",  "value": 24, "msg": "bật điều hòa 24°C"},
        ],
        "reply_suggest": "Trời nóng — tôi có thể bật điều hòa và quạt.",
    },
    "cold": {
        "keywords": ["lạnh", "rét", "buốt", "cold", "chilly", "freezing", "too cold"],
        "actions": [
            {"category": "ac",  "action": "OFF", "msg": "tắt điều hòa"},
            {"category": "fan", "action": "OFF", "msg": "tắt quạt"},
        ],
        "reply_suggest": "Trời lạnh — tôi có thể tắt điều hòa và quạt.",
    },
    "dark": {
        "keywords": ["tối", "tối quá", "dark", "too dark", "dim", "gloomy", "can't see"],
        "actions": [
            {"category": "light", "action": "ON", "value": 75, "msg": "bật đèn 75%"},
        ],
        "reply_suggest": "Trời tối — tôi có thể bật đèn cho Ngài.",
    },
    "bright": {
        "keywords": ["chói", "sáng quá", "bright", "too bright", "glare", "blinding"],
        "actions": [
            {"category": "light", "action": "ON", "value": 30, "msg": "giảm đèn xuống 30%"},
        ],
        "reply_suggest": "Tôi có thể giảm độ sáng đèn cho Ngài.",
    },
}

# ============================================================
# DEVICE SCENARIOS — điều khiển theo tình huống / hoạt động
# Environmental conditions (hot/cold/dark/bright) are in
# ENVIRONMENTAL_INTENTS above; scenarios here cover activities
# and lifestyle contexts that may combine multiple categories.
# ============================================================
ALFRED_SCENARIOS = {

    # ── Environmental shortcuts (re-export from ENVIRONMENTAL_INTENTS) ──
    "nóng": {**ENVIRONMENTAL_INTENTS["hot"],
             "keywords": ENVIRONMENTAL_INTENTS["hot"]["keywords"]},
    "lạnh": {**ENVIRONMENTAL_INTENTS["cold"],
             "keywords": ENVIRONMENTAL_INTENTS["cold"]["keywords"]},
    "tối":  {**ENVIRONMENTAL_INTENTS["dark"],
             "keywords": ENVIRONMENTAL_INTENTS["dark"]["keywords"]},
    "chói": {**ENVIRONMENTAL_INTENTS["bright"],
             "keywords": ENVIRONMENTAL_INTENTS["bright"]["keywords"]},

    # ── Activity / lifestyle scenarios ──
    "ngủ": {
        "keywords": ["ngủ", "sleep", "đi ngủ", "đi nghỉ", "nghỉ ngơi"],
        "actions": [
            {"category": "light",   "action": "OFF", "msg": "tắt đèn"},
            {"category": "tv",      "action": "OFF", "msg": "tắt TV"},
            {"category": "speaker", "action": "OFF", "msg": "tắt loa"},
            {"category": "ac",      "action": "ON",  "value": 27, "msg": "điều hòa 27°C dễ ngủ"},
        ],
        "reply_suggest": "Tôi có thể tắt đèn, TV và chỉnh điều hòa 27°C dễ ngủ.",
    },

    "làm việc": {
        "keywords": ["làm việc", "học bài", "study", "work", "tập trung", "focus", "đọc sách"],
        "actions": [
            {"category": "light", "action": "ON",  "value": 80, "msg": "đèn sáng 80%"},
            {"category": "ac",    "action": "ON",  "value": 25, "msg": "điều hòa 25°C"},
            {"category": "tv",    "action": "OFF", "msg": "tắt TV"},
        ],
        "reply_suggest": "Tôi có thể bật đèn sáng và điều chỉnh nhiệt độ phù hợp.",
    },

    "xem phim": {
        "keywords": ["xem phim", "movie", "xem tv", "giải trí", "xem video"],
        "actions": [
            {"category": "light",   "action": "ON", "value": 15, "msg": "đèn tối 15%"},
            {"category": "tv",      "action": "ON", "msg": "bật TV"},
            {"category": "ac",      "action": "ON", "value": 25, "msg": "điều hòa 25°C"},
            {"category": "speaker", "action": "ON", "msg": "bật loa"},
        ],
        "reply_suggest": "Tôi có thể bật TV, chỉnh đèn tối và điều hòa.",
    },

    "tập thể dục": {
        "keywords": ["tập thể dục", "gym", "exercise", "workout", "chạy bộ"],
        "actions": [
            {"category": "light",   "action": "ON", "value": 100, "msg": "đèn sáng 100%"},
            {"category": "fan",     "action": "ON", "value": 5,   "msg": "quạt mạnh"},
            {"category": "ac",      "action": "ON", "value": 22,  "msg": "điều hòa mát 22°C"},
            {"category": "speaker", "action": "ON", "msg": "nhạc tập"},
        ],
        "reply_suggest": "Tôi có thể bật đèn sáng, quạt mạnh và nhạc cho buổi tập.",
    },

    "sáng sớm": {
        "keywords": ["ngủ dậy", "mới dậy", "sáng rồi", "good morning", "dậy rồi"],
        "actions": [
            {"category": "light", "action": "ON",  "value": 60, "msg": "đèn vừa 60%"},
            {"category": "ac",    "action": "OFF", "msg": "tắt điều hòa"},
        ],
        "reply_suggest": "Chào buổi sáng — tôi có thể bật đèn và tắt điều hòa.",
    },

    "rời nhà": {
        "keywords": ["ra ngoài", "rời nhà", "đi làm", "đi học", "tắt hết"],
        "actions": [
            {"category": "light",   "action": "OFF", "msg": "tắt tất cả đèn"},
            {"category": "fan",     "action": "OFF", "msg": "tắt tất cả quạt"},
            {"category": "ac",      "action": "OFF", "msg": "tắt điều hòa"},
            {"category": "tv",      "action": "OFF", "msg": "tắt TV"},
            {"category": "speaker", "action": "OFF", "msg": "tắt loa"},
        ],
        "reply_suggest": "Tôi có thể tắt tất cả thiết bị trước khi Ngài ra ngoài.",
    },

    "về nhà": {
        "keywords": ["về nhà", "về rồi", "tôi về", "đã về", "arrived"],
        "actions": [
            {"category": "light", "action": "ON", "value": 70, "msg": "bật đèn 70%"},
            {"category": "ac",    "action": "ON", "value": 26, "msg": "bật điều hòa 26°C"},
        ],
        "reply_suggest": "Chào Ngài về nhà — tôi có thể bật đèn và điều hòa.",
    },
}
