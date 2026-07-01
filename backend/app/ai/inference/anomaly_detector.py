# app/ai/inference/anomaly_detector.py
import numpy as np


class AnomalyDetector:
    def __init__(self, loader):
        self.loader = loader

    def detect(self, X_scaled):
        model = self.loader.get_model("anomaly_model")
        if not model:
            return False

        # anomaly_model is HR-only (1 feature).
        # X_scaled is the full 7-feature vector; extract the HR column (index 0),
        # unscale it with the full scaler, then re-scale with the HR-only scaler.
        full_scaler = self.loader.get_model("scaler")
        hr_scaler   = self.loader.get_model("anomaly_hr_scaler")

        hr_col = np.asarray(X_scaled)[:, 0]
        hr_raw = (hr_col * full_scaler.scale_[0] + full_scaler.mean_[0]) if full_scaler else hr_col
        X_input = hr_scaler.transform(hr_raw.reshape(-1, 1)) if hr_scaler else hr_raw.reshape(-1, 1)

        return model.predict(X_input)[0] == -1
