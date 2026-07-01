# app/infrastructure/config/file_config_repo.py
import json
import logging
import os

logger = logging.getLogger(__name__)


class FileConfigRepository:
    """
    Infrastructure adapter
    Đọc / ghi broker_config.json từ filesystem
    """

    def __init__(self, base_dir: str):
        self.config_path = os.path.join(base_dir, "broker_config.json")

    def load(self) -> dict | None:
        if not os.path.exists(self.config_path):
            return None

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("ConfigRepo load error: %s", e)
            return None

    def save(self, data: dict) -> bool:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            logger.error("ConfigRepo save error: %s", e)
            return False
