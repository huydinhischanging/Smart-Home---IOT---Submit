# app/infrastructure/persistence/repositories/sensor_repository.py
from app.infrastructure.persistence.models import SensorData # ✅ Chuẩn xác
from app.extensions.database import db

class SensorRepository:
    def save(self, device_id, value):
        data = SensorData(
            device_id=device_id,
            value=str(value)
        )
        db.session.add(data)
        return data

    def get_recent_by_device_id(self, device_id, limit=50):
        return (
            SensorData.query
            .filter(SensorData.device_id == device_id)
            .order_by(SensorData.created_at.desc())
            .limit(limit)
            .all()
        )