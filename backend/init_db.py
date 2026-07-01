"""
==========================================================
FILE: init_db.py
Chạy file này 1 lần duy nhất để khởi tạo toàn bộ database
==========================================================
Cách dùng:
    python init_db.py

Sẽ tự động:
    1. Tạo database batman_os (nếu chưa có)
    2. Tạo user iot_user (nếu chưa có)
    3. Tạo tất cả bảng
==========================================================
"""

import os
import pymysql

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ENV_FILE_PATH = os.path.join(BASE_DIR, ".env")

if load_dotenv is not None:
    load_dotenv(dotenv_path=ENV_FILE_PATH)

from app.config.db_app import create_db_app
from app.extensions.database import db

# Import tất cả Model để db.create_all() nhận diện
from app.infrastructure.persistence.models.device_model import Device
from app.infrastructure.persistence.models.device_status_model import DeviceStatus
from app.infrastructure.persistence.models.control_log_model import ControlLog
from app.infrastructure.persistence.models.alert_model import AlertModel
from app.infrastructure.persistence.models.sensor_data_model import SensorData
from app.infrastructure.persistence.models.rooms_model import RoomModel
from app.infrastructure.persistence.models.alert_rule_model import AlertRuleModel
from app.infrastructure.persistence.models.alert_saved_view_model import AlertSavedViewModel
from app.infrastructure.persistence.models.alert_mute_preference_model import AlertMutePreferenceModel
from app.infrastructure.persistence.models.user_model import UserModel
from app.infrastructure.persistence.models.schedule_model import ScheduleModel
from app.infrastructure.persistence.models.notification_model import NotificationModel
from app.infrastructure.persistence.models.automation_model import AutomationModel
from app.infrastructure.persistence.models.medicine_reminder_model import MedicineReminderModel
from app.infrastructure.persistence.models.password_reset_token_model import PasswordResetTokenModel

# ==========================================================
# CẤU HÌNH — đọc từ .env hoặc biến môi trường
# ==========================================================
ROOT_USER = os.environ.get("DB_ROOT_USER", "root")
ROOT_PASS = os.environ.get("DB_ROOT_PASS", "")   # set DB_ROOT_PASS in .env
DB_HOST   = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT   = int(os.environ.get("DB_PORT", "3306"))
DB_NAME   = os.environ.get("DB_NAME", "batman_os")
DB_USER   = os.environ.get("DB_USER", "iot_user")
DB_PASS   = os.environ.get("DB_PASS", "")

_PLACEHOLDER_VALUES = {
    "",
    "YOUR_SECURE_PASSWORD_HERE",
    "replace-with-secure-db-password",
}


def _truthy_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_sqlite_dev_mode() -> bool:
    return _truthy_env("SQLITE_DEV_MODE", default=False)


def _create_schema_in_configured_database() -> bool:
    app = create_db_app()
    with app.app_context():
        db.create_all()
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        print(f"✅ Tất cả bảng đã được tạo thành công trong: {db_uri}")
    return True


def init():
    print("🚀 Bắt đầu khởi tạo database...")


    if DB_PASS in _PLACEHOLDER_VALUES:
        print("❌ DB_PASS chưa được cấu hình hợp lệ trong môi trường hoặc file .env")
        print("👉 Hãy cập nhật backend/.env trước khi chạy init_db.py")
        return

    # ----------------------------------------------------------
    # BƯỚC 1: Kết nối MySQL bằng root, tạo DB + user
    # ----------------------------------------------------------
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=ROOT_USER,
            password=ROOT_PASS,
            charset="utf8mb4",
        )
        cursor = conn.cursor()

        # Tạo database
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        print(f"✅ Database `{DB_NAME}` đã sẵn sàng.")

        # Tạo user
        cursor.execute(
            f"CREATE USER IF NOT EXISTS '{DB_USER}'@'localhost' "
            f"IDENTIFIED BY '{DB_PASS}';"
        )

        # Cấp quyền
        cursor.execute(
            f"GRANT ALL PRIVILEGES ON `{DB_NAME}`.* "
            f"TO '{DB_USER}'@'localhost';"
        )
        cursor.execute("FLUSH PRIVILEGES;")
        print(f"✅ User `{DB_USER}` đã được cấp quyền.")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Lỗi khi tạo database/user: {str(e)}")
        print("👉 Kiểm tra lại ROOT_PASS trong file init_db.py")
        return

    # ----------------------------------------------------------
    # BƯỚC 2: Tạo tất cả bảng qua SQLAlchemy
    # ----------------------------------------------------------
    try:
        _create_schema_in_configured_database()

    except Exception as e:
        print(f"❌ Lỗi khi tạo bảng: {str(e)}")
        return

    print("\n✨ [DONE] Database đã sẵn sàng! Chạy app bình thường nhé.")


if __name__ == "__main__":
    init()