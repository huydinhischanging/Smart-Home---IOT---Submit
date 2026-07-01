# app/ai/training/dataset_builder.py
import pandas as pd
from app.extensions.database import db
from app.infrastructure.persistence.models import SensorData, ControlLog
from datetime import timedelta
from app.ai.data.feature_engineering import add_time_derived_features, finalize_features


class DatasetBuilder:

    def build_real_dataset(self):
        print("🔍 [Bat-AI] Building alignment-safe dataset...")

        # 1️⃣ Thu thập Sensor Data
        sensors = db.session.query(SensorData).all()
        if not sensors:
            return None

        df_raw = pd.DataFrame([{
            "ts": s.created_at,
            "code": s.device.code,
            "val": float(s.value)
        } for s in sensors])

        # 2️⃣ Time-Series Alignment
        df_raw["ts"] = pd.to_datetime(df_raw["ts"])

        df_pivot = df_raw.pivot_table(
            index="ts",
            columns="code",
            values="val"
        )

        df_pivot = (
            df_pivot
            .sort_index()
            .ffill()
            .resample("5min")
            .mean()
            .dropna()
        )

        # 3️⃣ Thêm Time Features
        df_merged = df_pivot.reset_index()
        df_merged = add_time_derived_features(df_merged, timestamp_col="ts")

        # 4️⃣ Gán nhãn Automation từ Control Log
        logs = db.session.query(ControlLog).all()

        df_merged["action_label"] = "NO_ACTION"

        for l in logs:
            l_ts = pd.to_datetime(l.created_at)

            mask = (
                (df_merged["ts"] >= l_ts - timedelta(minutes=2)) &
                (df_merged["ts"] <= l_ts)
            )

            # ✅ FIX: dùng l.action thay vì l.command
            device_code = l.device.code if l.device else l.device_code

            if device_code:
                df_merged.loc[mask, "action_label"] = f"{device_code}:{l.action}"

        # (Optional) finalize feature alignment nếu pipeline yêu cầu
        # df_merged = finalize_features(df_merged)

        return df_merged