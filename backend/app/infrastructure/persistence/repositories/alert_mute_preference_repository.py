from app.extensions.database import db
from app.infrastructure.persistence.models.alert_mute_preference_model import AlertMutePreferenceModel


class AlertMutePreferenceRepository:
    def get_by_user_id(self, user_id):
        return AlertMutePreferenceModel.query.filter_by(user_id=user_id).first()

    def upsert(self, user_id, mute_scope, mute_keyword=""):
        pref = self.get_by_user_id(user_id)
        if pref is None:
            pref = AlertMutePreferenceModel(
                user_id=user_id,
                mute_scope=mute_scope,
                mute_keyword=mute_keyword,
            )
            db.session.add(pref)
        else:
            pref.mute_scope = mute_scope
            pref.mute_keyword = mute_keyword
        db.session.flush()
        return pref
