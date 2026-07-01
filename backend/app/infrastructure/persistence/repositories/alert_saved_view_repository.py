import json

from app.extensions.database import db
from app.infrastructure.persistence.models.alert_saved_view_model import AlertSavedViewModel
from app.infrastructure.persistence.models.user_model import UserModel


class AlertSavedViewRepository:
    def _get_record(self, user_id):
        return AlertSavedViewModel.query.filter_by(user_id=user_id).first()

    def get_views(self, user_id):
        record = self._get_record(user_id)
        if not record or not record.views_json:
            return []
        try:
            payload = json.loads(record.views_json)
        except (TypeError, ValueError):
            return []
        return payload if isinstance(payload, list) else []

    def replace_views(self, user_id, views):
        record = self._get_record(user_id)
        payload = json.dumps(views, ensure_ascii=True, separators=(",", ":"))
        if record is None:
            record = AlertSavedViewModel(user_id=user_id, views_json=payload)
            db.session.add(record)
        else:
            record.views_json = payload
        db.session.flush()
        return views

    def get_stats(self, limit=10):
        rows = (
            db.session.query(AlertSavedViewModel, UserModel)
            .join(UserModel, UserModel.id == AlertSavedViewModel.user_id)
            .order_by(AlertSavedViewModel.updated_at.desc(), AlertSavedViewModel.id.desc())
            .all()
        )

        total_views = 0
        total_pinned = 0
        recent_users = []

        for record, user in rows[: max(0, int(limit) or 0) or 10]:
            try:
                views = json.loads(record.views_json or "[]")
            except (TypeError, ValueError):
                views = []
            if not isinstance(views, list):
                views = []
            view_count = len(views)
            pinned_count = sum(1 for view in views if isinstance(view, dict) and view.get("pinned"))
            total_views += view_count
            total_pinned += pinned_count
            recent_users.append({
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "view_count": view_count,
                "pinned_count": pinned_count,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            })

        if len(rows) > len(recent_users):
            for record, _user in rows[len(recent_users):]:
                try:
                    views = json.loads(record.views_json or "[]")
                except (TypeError, ValueError):
                    views = []
                if not isinstance(views, list):
                    views = []
                total_views += len(views)
                total_pinned += sum(1 for view in views if isinstance(view, dict) and view.get("pinned"))

        return {
            "total_configs": len(rows),
            "total_saved_views": total_views,
            "total_pinned_views": total_pinned,
            "recent_users": recent_users,
        }