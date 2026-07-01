# app/ai/training/train_pipeline.py
"""
Training pipeline for Bat-Intelligence models.

This script builds a dataset (real + optional synthetic), then trains:
1) Shared feature scaler
2) Anomaly detector (IsolationForest)
3) Automation classifier (RandomForest)
4) Mood classifier (RandomForest)

Artifacts are saved under MODELS_PATH and loaded at backend startup.
"""

import joblib
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from app.ai.config import MODELS_PATH, FEATURE_COLUMNS, HEART_DISEASE_CSV
from app.ai.training.dataset_builder import DatasetBuilder
from app.ai.data.feature_engineering import finalize_features


def _calc_mood(row):
    # Rule-based pseudo-labeling to create mood targets for training.
    hr  = row.get("heart_rate", 70)
    tmp = row.get("room_temp", 24)
    lux = row.get("light_level", 100)
    ngt = row.get("is_night", 0)

    if hr >= 130:                          return "EMERGENCY"
    if hr >= 100:                          return "ELEVATED"
    if ngt == 1 and hr < 65:              return "SLEEP"
    if ngt == 1 and lux < 20:             return "QUIET"
    if hr < 60 and tmp > 28:              return "REST"
    if hr >= 80 and lux > 60:             return "ACTIVE"
    return "NORMAL"


def _load_heart_disease_data(csv_path: str) -> pd.DataFrame | None:
    """
    Map UCI Heart Disease Dataset (Cleveland 1988) to training schema.

    Key mapping rationale:
      - thalach (max HR achieved during stress test) × 0.60 ≈ resting HR.
        Patients with heart disease (target=1) have elevated resting HR,
        so we apply an additional 10-20% uplift for those rows.
      - room context (temp, humidity, light) is sampled from elderly-appropriate
        distributions since the original dataset has no room sensor columns.
      - target=1 rows function as the "hard anomaly" seed so IsolationForest
        learns a realistic boundary rather than one built purely from random data.

    Returns None when the file is missing or lacks required columns.
    """
    if not os.path.exists(csv_path):
        return None

    try:
        df_raw = pd.read_csv(csv_path)
    except Exception as exc:
        print(f"[heart_disease] Failed to read CSV: {exc}")
        return None

    required = {"thalach", "target", "age"}
    if not required.issubset(df_raw.columns):
        print(f"[heart_disease] Missing required columns. Found: {list(df_raw.columns)}")
        return None

    rng = np.random.default_rng(42)
    rows = []

    for _, r in df_raw.iterrows():
        age     = float(r.get("age", 65))
        thalach = float(r.get("thalach", 140))
        target  = int(r.get("target", 0))

        # thalach is max HR; resting HR ≈ 55-65% of max for adults.
        resting_hr = thalach * rng.uniform(0.55, 0.65)
        # Cardiac patients have higher resting HR than healthy controls.
        if target == 1:
            resting_hr *= rng.uniform(1.10, 1.25)
        resting_hr = float(np.clip(resting_hr, 40.0, 170.0))

        # Elderly prefer warmer, more humid indoor environments.
        is_elderly = age >= 60
        room_temp  = float(rng.uniform(23.0, 28.0) if is_elderly else rng.uniform(20.0, 27.0))
        humidity   = float(rng.uniform(48.0, 65.0))

        hour      = float(rng.integers(0, 24))
        is_night  = 1.0 if hour >= 20 or hour <= 6 else 0.0
        light_lvl = float(
            rng.uniform(80.0, 300.0) if 8 <= int(hour) <= 18
            else rng.uniform(5.0, 60.0)
        )
        is_dark   = 1.0 if light_lvl < 50 else 0.0

        rows.append({
            "heart_rate":   resting_hr,
            "room_temp":    room_temp,
            "humidity":     humidity,
            "light_level":  light_lvl,
            "hour":         hour,
            "is_night":     is_night,
            "is_dark":      is_dark,
            "action_label": "NO_ACTION",
        })

    result = pd.DataFrame(rows)
    print(
        f"[heart_disease] Loaded {len(result)} real patient rows "
        f"(healthy={int((df_raw['target'] == 0).sum())}, "
        f"disease={int((df_raw['target'] == 1).sum())})"
    )
    return result


def _add_synthetic_normals(df, n=300):
    # Add plausible normal samples when real data is still sparse.
    # Night defined as hour >= 20 or hour <= 6; HR ranges match tune_and_retrain values.
    rng = np.random.default_rng(42)
    rows = []
    for _ in range(n):
        hour     = int(rng.integers(0, 24))
        is_night = hour >= 20 or hour <= 6
        hr       = float(rng.integers(50, 75)) if is_night else float(rng.integers(60, 92))
        tmp      = rng.uniform(20, 30)
        hum      = rng.uniform(40, 70)
        lux      = rng.uniform(50, 300)
        rows.append({
            "heart_rate":   hr,
            "room_temp":    tmp,
            "humidity":     hum,
            "light_level":  lux,
            "hour":         float(hour),
            "is_night":     1.0 if is_night else 0.0,
            "is_dark":      1.0 if lux < 50 else 0.0,
            "action_label": "NO_ACTION",
        })
    return pd.concat([df, pd.DataFrame(rows)], ignore_index=True)


def _choose_synthetic_samples(real_count: int) -> tuple[int, str]:
    """
    Decide how many synthetic-normal samples to add based on real-data volume.

    Rationale:
    - Very small real datasets are unstable, so we heavily bootstrap.
    - As real data grows, we reduce synthetic ratio to avoid biasing the models.
    - At large scale, we stop adding synthetic data and rely on real distribution.

    Returns:
    - n_synth: number of synthetic rows to add.
    - stage: human-readable training stage used for logs/monitoring.
    """
    # Stage 1: cold-start, strong bootstrap for model stability.
    if real_count < 10:
        return 300, "bootstrap (<10 real)"
    # Stage 2: early learning, still keep a fixed bootstrap size.
    if real_count < 200:
        return 300, "early (10-199 real)"
    # Stage 3: growth phase, synthetic capped to ~50% of real volume.
    if real_count < 1000:
        return max(120, int(real_count * 0.50)), "growth (200-999 real)"
    # Stage 4: mature phase, synthetic reduced to ~20% of real volume.
    if real_count < 5000:
        return max(40, int(real_count * 0.20)), "mature (1000-4999 real)"
    # Stage 5: real-dominant phase, no synthetic data required.
    return 0, "real-dominant (>=5000 real)"


def run_full_training():
    # Data prep: build dataset from DB and bootstrap when real data is too small.
    print("🎬 [Bat-Intelligence] Start training...")
    builder = DatasetBuilder()
    df = builder.build_real_dataset()

    real_count = 0 if df is None else len(df)
    if df is None or real_count < 10:
        print("⚠️  DB dataset too small — bootstrap with external/synthetic base.")
        df = pd.DataFrame()

    defaults = {
        "heart_rate":   70.0,
        "room_temp":    24.0,
        "humidity":     50.0,
        "light_level":  100.0,
        "hour":         12.0,
        "is_night":     0.0,
        "is_dark":      0.0,
        "action_label": "NO_ACTION",
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    # Data prep: try to load real UCI Heart Disease data before falling back to synthetic.
    hd_df = _load_heart_disease_data(HEART_DISEASE_CSV)
    if hd_df is not None:
        df = pd.concat([df, hd_df], ignore_index=True)
        hd_count = len(hd_df)
        # With real patient data the contamination rate reflects actual elderly cardiac risk.
        contamination_override = 0.10
        print(
            f"[TRAIN] UCI Heart Disease dataset merged: +{hd_count} rows "
            f"(contamination overridden → {contamination_override})"
        )
    else:
        hd_count = 0
        contamination_override = None
        print("[TRAIN] heart_disease.csv not found — using synthetic bootstrap only.")
        print("        → Download from Kaggle and save to backend/data/heart_disease.csv")

    # Data prep: add synthetic normals only when real+UCI data is insufficient.
    effective_real = real_count + hd_count
    n_synth, stage = _choose_synthetic_samples(effective_real)
    if n_synth > 0:
        df = _add_synthetic_normals(df, n=n_synth)
    print(
        f"[TRAIN] stage={stage} | iot_real={real_count} | uci_real={hd_count} "
        f"| synthetic_added={n_synth} | total={len(df)}"
    )

    # Data prep: enforce stable feature schema/order before fitting models.
    X  = finalize_features(df)

    os.makedirs(MODELS_PATH, exist_ok=True)

    # Train 1/4: fit shared scaler for all downstream models.
    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    joblib.dump(scaler, os.path.join(MODELS_PATH, "scaler.pkl"))
    print(f"✅ Scaler saved — {len(X)} samples, features: {list(X.columns)}")

    # Train 2/4: train unsupervised anomaly detector.
    # UCI Heart Disease data has ~54% positive rate but for elderly IoT monitoring
    # we expect ~10% of readings to be anomalous — use that when real data is present.
    contamination = contamination_override if contamination_override else float(os.getenv("ANOMALY_CONTAMINATION", "0.020"))
    print(f"🧠 Training Anomaly Engine (contamination={contamination})...")
    anom = IsolationForest(
        contamination=contamination,
        n_estimators=300,
        random_state=42
    ).fit(X_scaled)
    joblib.dump(anom, os.path.join(MODELS_PATH, "anomaly_model.pkl"))
    print("✅ anomaly_model.pkl saved")

    # Train 3/4: train automation action classifier.
    print("🧠 Training Automation Engine...")
    y_auto = df["action_label"]
    auto_model = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=42
    ).fit(X_scaled, y_auto)
    joblib.dump(auto_model, os.path.join(MODELS_PATH, "automation_model.pkl"))
    print("✅ automation_model.pkl saved")

    # Train 4/4: train mood classifier from rule-derived labels.
    print("🧠 Training Mood Engine...")
    y_mood = df.apply(_calc_mood, axis=1)
    print(f"   Mood distribution:\n{y_mood.value_counts().to_string()}")
    mood_model = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=42
    ).fit(X_scaled, y_mood)
    joblib.dump(mood_model, os.path.join(MODELS_PATH, "mood_model.pkl"))
    print("✅ mood_model.pkl saved")

    print(f"\n✅ All models saved to: {MODELS_PATH}")
    print("   → Restart the server to load new models.")


if __name__ == "__main__":
    # DatasetBuilder needs Flask app context for DB access.
    from app.config.db_app import create_db_app
    with create_db_app().app_context():
        run_full_training()
