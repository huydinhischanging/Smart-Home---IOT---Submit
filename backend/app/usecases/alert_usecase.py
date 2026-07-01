# app/usecases/alert_usecase.py

from datetime import datetime


class AlertUseCase:
    """
    Trách nhiệm: Quản lý logic về thông báo và cảnh báo trong Gotham
    """

    def __init__(self, alert_repo, realtime_notifier):
        self.alert_repo = alert_repo
        self.realtime = realtime_notifier

    # ======================================================
    # CREATE ALERT
    # ======================================================
    def create_alert(self, device_code, message, level, user_id=None):
        """
        Tạo cảnh báo mới:
        - Ghi vào Database (Persistence Layer)
        - Bắn tín hiệu Realtime (Notifier Layer)
        """

        # 🟢 Không commit ở đây (để orchestration layer quản lý)
        alert = self.alert_repo.create(device_code, message, level, user_id=user_id)

        # 🔥 Emit realtime — scoped to user if available
        self.realtime.notify_alert(
            {
                "device_code": device_code,
                "message": message,
                "level": level,
                "created_at": str(datetime.now())
            },
            user_id=user_id,
        )

        return alert

    # ======================================================
    # GET ALL ALERTS
    # ======================================================
    def get_all_alerts(self, user_id=None, limit=50, offset=0, level=None, unread_only=False, device_code=None, query=None, since=None, sort="newest"):
        """Lấy danh sách cảnh báo theo user"""
        alerts = self.alert_repo.get_all(
            user_id=user_id,
            limit=limit,
            offset=offset,
            level=level,
            unread_only=unread_only,
            device_code=device_code,
            query=query,
            since=since,
            sort=sort,
        )

        return [
            {
                "id": a.id,
                "device_code": a.device_code,
                "message": a.message,
                "level": a.level,
                "is_read": a.is_read,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ]

    def mark_alert_read(self, alert_id, user_id):
        """Mark a single alert as read, scoped to user."""
        return self.alert_repo.mark_read(alert_id, user_id)

    def mark_alerts_read(self, alert_ids, user_id):
        """Mark multiple alerts as read, scoped to user."""
        cleaned = []
        seen = set()
        for alert_id in alert_ids or []:
            try:
                value = int(alert_id)
            except (TypeError, ValueError):
                continue
            if value <= 0 or value in seen:
                continue
            seen.add(value)
            cleaned.append(value)
        if not cleaned:
            return 0
        return self.alert_repo.mark_read_many(cleaned, user_id)

    def count_unread(self, user_id):
        return self.alert_repo.count_unread(user_id)

    def count_filtered_alerts(self, user_id=None, level=None, unread_only=False, device_code=None, query=None, since=None):
        return self.alert_repo.count_filtered(
            user_id=user_id,
            level=level,
            unread_only=unread_only,
            device_code=device_code,
            query=query,
            since=since,
        )

    def delete_alert(self, alert_id, user_id):
        """Delete a single alert, scoped to user."""
        return self.alert_repo.delete_one(alert_id, user_id)

    def clear_read_alerts(self, user_id):
        """Delete all read alerts for the user."""
        return self.alert_repo.delete_read_all(user_id)

    def get_filtered_summary(self, user_id=None, level=None, unread_only=False, device_code=None, query=None, since=None):
        total = self.count_filtered_alerts(
            user_id=user_id,
            level=level,
            unread_only=unread_only,
            device_code=device_code,
            query=query,
            since=since,
        )
        unread = self.count_filtered_alerts(
            user_id=user_id,
            level=level,
            unread_only=True,
            device_code=device_code,
            query=query,
            since=since,
        )
        if level in {"info", "warning"}:
            critical = 0
        else:
            critical = self.count_filtered_alerts(
                user_id=user_id,
                level="critical",
                unread_only=unread_only,
                device_code=device_code,
                query=query,
                since=since,
            )
        return {
            "total": total,
            "unread": unread,
            "critical": critical,
        }