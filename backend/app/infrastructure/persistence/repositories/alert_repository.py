# app/infrastructure/persistence/repositories/alert_repository.py
from sqlalchemy import or_

from app.infrastructure.persistence.models import AlertModel # ✅ Chuẩn xác
from app.extensions.database import db

class AlertRepository:
    def create(self, device_code, message, level, user_id=None):
        alert = AlertModel(
            device_code=device_code,
            message=message,
            level=level,
            user_id=user_id,
        )
        db.session.add(alert)
        return alert

    def _build_query(self, user_id=None, level=None, unread_only=False, device_code=None, query=None, since=None):
        q = AlertModel.query
        if user_id is not None:
            q = q.filter(AlertModel.user_id == user_id)
        if level:
            q = q.filter(AlertModel.level == level)
        if unread_only:
            q = q.filter(AlertModel.is_read.is_(False))
        if device_code:
            q = q.filter(AlertModel.device_code == device_code)
        if query:
            like_value = f"%{query}%"
            q = q.filter(
                or_(
                    AlertModel.device_code.ilike(like_value),
                    AlertModel.message.ilike(like_value),
                )
            )
        if since is not None:
            q = q.filter(AlertModel.created_at >= since)
        return q

    def get_all(self, user_id=None, limit=50, offset=0, level=None, unread_only=False, device_code=None, query=None, since=None, sort="newest"):
        q = self._build_query(
            user_id=user_id,
            level=level,
            unread_only=unread_only,
            device_code=device_code,
            query=query,
            since=since,
        )
        if sort == "oldest":
            q = q.order_by(AlertModel.created_at.asc())
        else:
            q = q.order_by(AlertModel.created_at.desc())
        return q.offset(offset).limit(limit).all()

    def count_filtered(self, user_id=None, level=None, unread_only=False, device_code=None, query=None, since=None):
        return self._build_query(
            user_id=user_id,
            level=level,
            unread_only=unread_only,
            device_code=device_code,
            query=query,
            since=since,
        ).count()

    def mark_read(self, alert_id, user_id):
        alert = AlertModel.query.filter_by(id=alert_id, user_id=user_id).first()
        if not alert:
            return False
        alert.is_read = True
        db.session.commit()
        return True

    def mark_read_many(self, alert_ids, user_id):
        ids = [int(alert_id) for alert_id in alert_ids]
        if not ids:
            return 0
        updated = (
            AlertModel.query
            .filter(AlertModel.user_id == user_id, AlertModel.id.in_(ids), AlertModel.is_read.is_(False))
            .update({AlertModel.is_read: True}, synchronize_session=False)
        )
        db.session.commit()
        return int(updated or 0)

    def count_unread(self, user_id):
        return AlertModel.query.filter_by(user_id=user_id, is_read=False).count()

    def delete_one(self, alert_id, user_id):
        alert = AlertModel.query.filter_by(id=alert_id, user_id=user_id).first()
        if not alert:
            return False
        db.session.delete(alert)
        db.session.commit()
        return True

    def delete_read_all(self, user_id):
        deleted = (
            AlertModel.query
            .filter(AlertModel.user_id == user_id, AlertModel.is_read.is_(True))
            .delete(synchronize_session=False)
        )
        db.session.commit()
        return int(deleted or 0)