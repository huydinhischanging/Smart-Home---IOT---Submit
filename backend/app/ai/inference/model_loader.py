# app/ai/inference/model_loader.py

import joblib
import logging
import os
from app.ai.config import MODELS_PATH

logger = logging.getLogger(__name__)


class ModelLoader:
    def __init__(self):
        self.models = {}
        self.load()

    def load(self):
        targets = ["anomaly_model", "anomaly_hr_scaler", "automation_model", "mood_model", "scaler"]
        for name in targets:
            path = os.path.join(MODELS_PATH, f"{name}.pkl")

            if os.path.exists(path):
                try:
                    self.models[name] = joblib.load(path)
                    logger.info("Bat-AI: Loaded %s.pkl", name)
                except Exception as e:
                    logger.error("Error loading %s: %s", name, e)
                    self.models[name] = None
            else:
                logger.warning("Bat-AI: %s.pkl not found.", name)
                self.models[name] = None

    # ✅ ĐỔI TÊN HÀM CHO KHỚP AIService
    def get_model(self, name):
        return self.models.get(name)