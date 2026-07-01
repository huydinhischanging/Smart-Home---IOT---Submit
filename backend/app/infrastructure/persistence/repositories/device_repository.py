# app/infrastructure/persistence/repositories/device_repository.py
from typing import List, Optional
from sqlalchemy.orm import joinedload
from app.extensions.database import db
from app.infrastructure.persistence.models.device_model import Device
from app.infrastructure.persistence.models.device_status_model import DeviceStatus

class DeviceRepository:
    """Production-ready Device Repository with Room support"""

    def get_all_active(self, user_id=None) -> List[Device]:
        q = (
            Device.query
            .options(joinedload(Device.status))
            .options(joinedload(Device.room))
            .filter(Device.is_deleted == False)
        )
        if user_id is not None:
            q = q.filter(Device.user_id == user_id)
        return q.all()

    def get_by_id(self, device_id: int, user_id=None) -> Optional[Device]:
        q = (
            Device.query
            .options(joinedload(Device.status))
            .options(joinedload(Device.room))
            .filter(Device.id == device_id, Device.is_deleted == False)
        )
        if user_id is not None:
            q = q.filter(Device.user_id == user_id)
        return q.first()

    def get_by_name(self, name: str, user_id=None) -> Optional[Device]:
        q = (
            Device.query
            .options(joinedload(Device.status))
            .options(joinedload(Device.room))
            .filter(Device.name == name, Device.is_deleted == False)
        )
        if user_id is not None:
            q = q.filter(Device.user_id == user_id)
        return q.first()

    def get_by_code(self, code: str, user_id=None) -> Optional[Device]:
        q = (
            Device.query
            .options(joinedload(Device.status))
            .options(joinedload(Device.room))
            .filter(Device.code == code, Device.is_deleted == False)
        )
        if user_id is not None:
            q = q.filter(Device.user_id == user_id)
        return q.first()

    def get_all_by_code(self, code: str) -> List[Device]:
        """Return ALL active devices matching ``code`` across all tenants.

        Used by MQTT handlers that have no user context — ensures every tenant
        whose physical device reports that code receives the update.
        """
        return (
            Device.query
            .options(joinedload(Device.status))
            .options(joinedload(Device.room))
            .filter(Device.code == code, Device.is_deleted == False)
            .all()
        )

    def exists_by_name(self, name: str, user_id=None) -> bool:
        # ✅ Chỉ check active devices — bỏ qua đã xóa
        q = db.session.query(Device.id).filter(
            Device.name == name,
            Device.is_deleted == False
        )
        if user_id is not None:
            q = q.filter(Device.user_id == user_id)
        return q.first() is not None

    def exists_by_code(self, code: str, user_id=None) -> bool:
        # ✅ FIXED: Device.code scoped per user (not globally unique)
        # This prevents multi-tenant isolation issues in MQTT and API
        q = db.session.query(Device.id).filter(
            Device.code == code,
            Device.is_deleted == False
        )
        if user_id is not None:
            q = q.filter(Device.user_id == user_id)
        return q.first() is not None

    def create(self, name: str, code: str, control_types: list, icon: str = "💡", category: str = "sensor",
               device_type: str | None = None, metadata_json: dict | None = None,
               map_x=None, map_y=None, room_id=None, user_id=None) -> Device:
        device = Device(name=name, code=code, icon=icon, category=category, device_type=device_type,
                        metadata_json=metadata_json or {}, map_x=map_x, map_y=map_y,
                        room_id=room_id, user_id=user_id, is_deleted=False)
        device.types_list = control_types
        db.session.add(device)
        db.session.flush()
        status = DeviceStatus(device_id=device.id, is_on=False, value="OFF")
        db.session.add(status)
        return device

    def delete(self, device: Device) -> None:
        # ✅ Soft-delete + đổi code/name để giải phóng UNIQUE constraint
        # và cho phép tạo lại cùng tên sau này.
        original_code = device.code
        original_name = device.name
        device.soft_delete()
        device.code = f"{original_code}_del_{device.id}"
        device.name = f"{original_name}_del_{device.id}"
        device.room_id = None
        device.map_x = None
        device.map_y = None
        db.session.add(device)
