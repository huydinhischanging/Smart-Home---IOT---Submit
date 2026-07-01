#app/ai/services/alfred_ai.py
import logging
import os

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Try the new package first, fall back to deprecated one if needed.
try:
    import google.genai as genai
except ImportError:
    import google.generativeai as genai

if load_dotenv is not None:
    load_dotenv()


class AlfredAiService:

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_key:
            logger.warning("Gemini API key is not set. gemini mode will return guidance message.")

        # Use model key from env fallback to present-supported Gemini 2.5 Flash model
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "models/gemini-2.5-flash")

        # New package API (google.genai)
        self.use_genai_client = hasattr(genai, 'Client')
        self.client = None
        if self.use_genai_client and self.gemini_key:
            try:
                self.client = genai.Client(api_key=self.gemini_key)
            except Exception as e:
                logger.warning("Failed to create genai client: %s", e)

        # Legacy package API (google.generativeai)
        self.model = None
        if hasattr(genai, 'GenerativeModel') and self.gemini_key:
            try:
                self.model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction="""
You are Alfred Pennyworth, Batman's intelligent butler.

Personality:
- Calm
- Professional
- Slightly British humor
- Helpful and concise

You assist an elderly homeowner with a smart home system.
You may control lights, fans, doors, and give health advice.
"""
                )
            except Exception as e:
                logger.warning("Failed to initialize generative model: %s", e)

        if hasattr(genai, 'configure') and self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
            except Exception as e:
                logger.warning("Failed to configure genai package: %s", e)

    def ask_alfred(self, user_query, sensor_context=None, username=None):

        context = sensor_context if sensor_context else "No sensor alerts."
        caller = username if username else "Sir"

        prompt = f"""
Home sensor status:
{context}

{caller} says:
{user_query}

Respond as Alfred.
"""

        try:
            if not self.gemini_key:
                return "Gemini mode needs GEMINI_API_KEY; please set environment variable and restart."

            def extract_text(response):
                if response is None:
                    return None
                if isinstance(response, str):
                    return response
                if hasattr(response, 'text') and response.text:
                    return response.text
                if hasattr(response, 'content') and response.content:
                    return response.content
                if hasattr(response, 'candidates') and response.candidates:
                    candidates = response.candidates
                    if isinstance(candidates, (list, tuple)) and len(candidates) > 0:
                        first = candidates[0]
                        if isinstance(first, dict):
                            return first.get('text') or first.get('content')
                        if hasattr(first, 'text'):
                            return first.text
                return None

            if self.client is not None:
                # New-style API (google.genai.Client)
                if hasattr(self.client, 'models') and hasattr(self.client.models, 'generate_content'):
                    response = self.client.models.generate_content(model=self.model_name, contents=prompt)
                    text = extract_text(response)
                    if text:
                        return str(text).strip()

                # Some older versions may expose generate_text directly on client
                if hasattr(self.client, 'generate_text'):
                    response = self.client.generate_text(model=self.model_name, prompt=prompt)
                    text = extract_text(response)
                    if text:
                        return str(text).strip()

            if self.model is not None:
                # Legacy API (google.generativeai.GenerativeModel)
                response = self.model.generate_content(prompt)
                text = extract_text(response)
                if text:
                    return str(text).strip()

            # Additional fallback for strange old API with top-level generate function
            if hasattr(genai, 'generate'):
                response = genai.generate(model=self.model_name, prompt=prompt)
                text = extract_text(response)
                if text:
                    return str(text).strip()

            if hasattr(genai, 'generate_text'):
                response = genai.generate_text(model=self.model_name, prompt=prompt)
                text = extract_text(response)
                if text:
                    return str(text).strip()

            return "Apologies, sir. AI configuration is missing."

        except Exception as e:
            logger.warning("Gemini ask_alfred exception: %s", e)
            raise

    # =====================================================
    # 😊 MOOD DETECTION & RECOMMENDATIONS
    # =====================================================

    def detect_mood_from_text(self, message: str) -> dict:
        """
        Detect user mood from text (both English & Vietnamese).
        Returns: {"mood": "happy|sad|angry|anxious|calm|stressed", "confidence": 0.0-1.0, "keywords": [...]}
        """
        msg_lower = message.lower().strip()

        # Vietnamese mood keywords
        mood_keywords = {
            "happy": {
                "keywords": ["vui", "hạnh phúc", "tuyệt vời", "đẹp lắm", "tốt lắm", "yay", "😊", "😃", 
                           "happy", "joyful", "excited", "great", "wonderful", "awesome", "excellent"],
                "keywords_vn": ["vui", "hạnh phúc", "vui vẻ", "tuyệt", "ok", "tốt", "đẹp", "tuyệt vời"]
            },
            "sad": {
                "keywords": ["buồn", "tâm trạng", "khó chịu", "tệ", "tồi tệ", "sad", "unhappy", "depressed",
                           "down", "upset", "bad", "terrible", "awful", "😢", "😞"],
                "keywords_vn": ["buồn", "tâm trạng", "khó chịu", "tệ", "tồi", "chán", "nản", "thất vọng"]
            },
            "angry": {
                "keywords": ["tức giận", "giận", "bực", "bực mình", "phẫn nộ", "angry", "furious", "upset",
                           "mad", "annoyed", "irritated", "🤬", "😠"],
                "keywords_vn": ["tức", "giận", "bực", "bực mình", "phẫn", "chán"]
            },
            "anxious": {
                "keywords": ["lo lắng", "sợ", "hồi hộp", "vô cùng", "worried", "nervous", "anxious",
                           "scared", "afraid", "stressed", "😰", "😟"],
                "keywords_vn": ["lo", "sợ", "hồi hộp", "lo lắng", "căng thẳng", "stress"]
            },
            "calm": {
                "keywords": ["bình tĩnh", "yên tĩnh", "thư giãn", "thoải mái", "calm", "relaxed",
                           "peaceful", "quiet", "ok", "😌", "🧘"],
                "keywords_vn": ["bình tĩnh", "yên", "thư giãn", "thoải mái", "ok"]
            },
            "stressed": {
                "keywords": ["stress", "căng thẳng", "áp lực", "quá tải", "exhausted", "overwhelmed",
                           "pressured", "😫", "😩"],
                "keywords_vn": ["stress", "căng thẳng", "áp lực", "quá tải", "mệt", "mệt mỏi"]
            }
        }

        matched_moods = {}
        for mood, data in mood_keywords.items():
            for kw in data["keywords"]:
                if kw in msg_lower:
                    matched_moods[mood] = matched_moods.get(mood, 0) + 1

        if not matched_moods:
            return {"mood": "normal", "confidence": 0.0, "keywords": []}

        best_mood = max(matched_moods, key=matched_moods.get)
        confidence = min(1.0, matched_moods[best_mood] / 3.0)

        return {
            "mood": best_mood,
            "confidence": confidence,
            "keywords": list(mood_keywords[best_mood]["keywords"][:3])
        }

    def get_recommendations(self, detected_mood: dict, context: dict = None) -> dict:
        """
        Get recommendations based on detected mood.
        Returns: {"theme": "...", "music": "...", "suggestion": "...", "action": "..."}
        """
        mood = detected_mood.get("mood", "normal")

        recommendations = {
            "happy": {
                "theme": "focus",  # Green theme
                "music": "upbeat|pop|dance",
                "suggestion": "🎵 Enjoy some upbeat music! 🎶",
                "action": "play_happy_playlist",
                "message_vn": "🎵 Nghe nhạc sôi động nhé! 🎶"
            },
            "sad": {
                "theme": "meditation",  # Blue theme
                "music": "relaxing|ambient|jazz",
                "suggestion": "🎶 Let's listen to calming music. 💙",
                "action": "play_calm_playlist",
                "message_vn": "🎶 Nghe nhạc thư giãn nhé. 💙"
            },
            "angry": {
                "theme": "focus",  # Green theme (energetic)
                "music": "workout|rock|energetic",
                "suggestion": "💪 Time to channel that energy! Let's exercise.",
                "action": "play_workout_playlist",
                "message_vn": "💪 Hãy chuyển hóa cảm xúc thành năng lượng!"
            },
            "anxious": {
                "theme": "meditation",  # Blue theme
                "music": "breathing_exercises|nature_sounds|meditation",
                "suggestion": "🧘 Take a deep breath. Let's meditate together.",
                "action": "play_meditation",
                "message_vn": "🧘 Hãy thở sâu. Cùng thiền nhé."
            },
            "calm": {
                "theme": "meditation",  # Blue theme
                "music": "peaceful|instrumental",
                "suggestion": "☀️ Enjoy this peaceful moment.",
                "action": "maintain_calm",
                "message_vn": "☀️ Hưởng thụ giây phút yên bình này."
            },
            "stressed": {
                "theme": "meditation",  # Blue theme
                "music": "spa|nature|soft_lofi",
                "suggestion": "🌿 Let's reduce stress with some relaxation.",
                "action": "play_relaxation",
                "message_vn": "🌿 Hãy thư giãn và giảm căng thẳng."
            },
            "normal": {
                "theme": "vigilant",  # Yellow theme (default)
                "music": None,
                "suggestion": "How can I assist you today?",
                "action": None,
                "message_vn": "Tôi có thể giúp gì cho bạn hôm nay?"
            }
        }

        return recommendations.get(mood, recommendations["normal"])

    def ask_alfred_with_mood(self, user_query: str, sensor_context=None, username=None):
        """
        Enhanced ask_alfred with mood detection & recommendations.
        Returns: {
            "reply": "...",
            "detected_mood": "happy",
            "confidence": 0.8,
            "recommendations": {...},
            "suggested_theme": "meditation"
        }
        """
        # Detect mood
        mood_info = self.detect_mood_from_text(user_query)

        # Get AI response
        try:
            reply = self.ask_alfred(user_query, sensor_context, username)
        except Exception as e:
            logger.warning("ask_alfred failed: %s", e)
            reply = "I'm having trouble processing that. Please try again, sir."

        # Get recommendations
        recommendations = self.get_recommendations(mood_info)

        return {
            "reply": reply,
            "detected_mood": mood_info["mood"],
            "confidence": mood_info["confidence"],
            "recommendations": recommendations,
            "suggested_theme": recommendations["theme"]
        }