from app.extensions.database import db


class AlertMutePreferenceUseCase:
    VALID_SCOPES = {"none", "all", "heart_rate", "light", "fan_ac", "custom", "device_code"}

    def __init__(self, alert_mute_pref_repo):
        self.alert_mute_pref_repo = alert_mute_pref_repo

    def get_preference(self, user_id):
        pref = self.alert_mute_pref_repo.get_by_user_id(user_id)
        if pref is None:
            return {
                "scope": "none",
                "keyword": "",
                "is_active": False,
                "updated_at": None,
            }
        scope = self._normalize_scope(pref.mute_scope)
        keyword = self._normalize_keyword(pref.mute_keyword)
        return {
            "scope": scope,
            "keyword": keyword,
            "is_active": scope != "none",
            "updated_at": pref.updated_at,
        }

    def set_preference(self, user_id, scope, keyword=""):
        normalized_scope = self._normalize_scope(scope)
        normalized_keyword = self._normalize_keyword(keyword)

        if normalized_scope in {"custom", "device_code"} and not normalized_keyword:
            raise ValueError("keyword is required when scope is custom or device_code")

        if normalized_scope == "none":
            normalized_keyword = ""

        pref = self.alert_mute_pref_repo.upsert(
            user_id=user_id,
            mute_scope=normalized_scope,
            mute_keyword=normalized_keyword,
        )
        db.session.commit()
        return {
            "scope": normalized_scope,
            "keyword": normalized_keyword,
            "is_active": normalized_scope != "none",
            "updated_at": pref.updated_at,
        }

    def _normalize_scope(self, scope):
        candidate = str(scope or "none").strip().lower()
        return candidate if candidate in self.VALID_SCOPES else "none"

    def _normalize_keyword(self, keyword):
        return str(keyword or "").strip()[:64]
