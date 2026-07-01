# app/infrastructure/persistence/repositories/log_repository.py

from typing import List, Optional
from app.extensions.database import db
from app.infrastructure.persistence.models.control_log_model import ControlLog


class ControlLogRepository:
    """
    Repository for ControlLog entity.
    ❗ Không commit trong repository.
    Transaction được quản lý ở UseCase layer.
    """

    # ==========================================================
    # CREATE LOG
    # ==========================================================
    def add(
        self,
        device_code: Optional[str],
        action: str,
        device_id: Optional[int] = None,
        source: str = "SYSTEM",
        user_id: Optional[int] = None,
    ) -> ControlLog:
        """
        Thêm log mới (không commit ở đây).
        """
        log = ControlLog(
            device_code=device_code,
            device_id=device_id,
            action=action,
            source=source,
            user_id=user_id,
        )

        db.session.add(log)
        return log

    # ==========================================================
    # GET RECENT LOGS
    # ==========================================================
    def get_recent(self, limit: int = 50) -> List[ControlLog]:
        """
        Lấy danh sách log mới nhất.
        """
        return (
            ControlLog.query
            .order_by(ControlLog.created_at.desc())
            .limit(limit)
            .all()
        )

    # ==========================================================
    # GET BY DEVICE ID
    # ==========================================================
    def get_by_device_id(
        self,
        device_id: int,
        limit: int = 50,
    ) -> List[ControlLog]:
        """
        Lấy log theo device_id ổn định.
        """
        return (
            ControlLog.query
            .filter(ControlLog.device_id == device_id)
            .order_by(ControlLog.created_at.desc())
            .limit(limit)
            .all()
        )

    # ==========================================================
    # DELETE ALL LOGS (OPTIONAL ADMIN TOOL)
    # ==========================================================
    def delete_all(self) -> None:
        """
        Xóa toàn bộ log (không commit ở đây).
        Chỉ dùng cho admin/debug.
        """
        ControlLog.query.delete()