from typing import Optional

from sqlalchemy import select

from app.extensions.database import db
from app.infrastructure.persistence.models.device_model import Device
from app.infrastructure.persistence.models.device_status_model import DeviceStatus


class DeviceStatusRepository:
    """Repository for DeviceStatus entity"""

    def get_by_device_id(self, device_id: int) -> Optional[DeviceStatus]:
        return DeviceStatus.query.filter_by(device_id=device_id).first()

    def get_or_create(self, device: Device) -> DeviceStatus:
        status = self.get_by_device_id(device.id)

        if not status:
            status = DeviceStatus(
                device_id=device.id,
                is_on=False,
                value="OFF",
            )
            db.session.add(status)

        return status

    def get_or_create_locked(self, device: Device) -> DeviceStatus:
        """Pessimistic lock — dùng khi cần tránh race condition (concurrent control)."""
        status = db.session.execute(
            select(DeviceStatus)
            .filter(DeviceStatus.device_id == device.id)
            .with_for_update()
        ).scalar_one_or_none()

        if not status:
            status = DeviceStatus(device_id=device.id, is_on=False, value="OFF")
            db.session.add(status)

        return status

    def save(self, status: DeviceStatus) -> DeviceStatus:
        db.session.add(status)       # ❌ NO COMMIT
        return status

    def delete(self, status: DeviceStatus) -> None:
        db.session.delete(status)    # ❌ NO COMMIT

    # ✅ FINAL – FIX FK + FIX 500 (BẮT BUỘC)
    def delete_by_device_id(self, device_id: int) -> None:
        (
            DeviceStatus.query
            .filter_by(device_id=device_id)
            .delete(synchronize_session=False)
        )

    # ✅ THÊM HÀM NÀY
    def get_all(self):
        """Lấy toàn bộ trạng thái hiện tại của tất cả thiết bị"""
        return DeviceStatus.query.all()