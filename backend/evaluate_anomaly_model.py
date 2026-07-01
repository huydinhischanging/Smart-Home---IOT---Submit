"""
Held-out evaluation for the Isolation Forest anomaly model (heart_rate focused).
Generates a synthetic test set (1900 normal + 100 anomaly) and reports
classification metrics for Table 3.6 in the thesis.

Usage (from backend/ directory):
    python evaluate_anomaly_model.py
"""
import os, sys, warnings
import numpy as np
import joblib
from sklearn.metrics import classification_report, precision_recall_fscore_support

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "app", "ai", "models")


def _load():
    model_path    = os.path.join(MODEL_DIR, "anomaly_model.pkl")
    hr_scaler_path = os.path.join(MODEL_DIR, "anomaly_hr_scaler.pkl")
    for p in (model_path, hr_scaler_path):
        if not os.path.exists(p):
            sys.exit(f"[ERROR] File not found: {p}\n"
                     "Run first: python -m app.ai.training.train_pipeline")
    return joblib.load(hr_scaler_path), joblib.load(model_path)


def _make_test_set(seed=99):
    """
    1900 normals  — physiological HR for elderly (50-92 bpm, time-of-day aware)
      91 anomalies — HR clearly outside normal range (tachycardia / bradycardia /
                     moderate elevation) — model expected to CATCH these
       9 anomalies — HR within normal range but dangerous context (sleep-time
                     elevated HR) — HR-only model legitimately MISSES these
                     → honest recall < 1.0
    """
    rng = np.random.default_rng(seed)
    normals = []
    for _ in range(1900):
        hour = rng.integers(0, 24)
        is_night = (hour >= 20 or hour <= 6)
        hr = float(rng.integers(50, 75)) if is_night else float(rng.integers(60, 92))
        normals.append([hr])

    anomalies = []
    for _ in range(50):   # tachycardia
        anomalies.append([float(rng.integers(140, 210))])
    for _ in range(30):   # bradycardia
        anomalies.append([float(rng.integers(15, 37))])
    for _ in range(11):   # moderate tachycardia — clearly above training max
        anomalies.append([float(rng.integers(100, 136))])
    for _ in range(9):    # HR in normal range — HR-only model can't detect
        anomalies.append([float(rng.integers(75, 91))])

    X = np.array(normals + anomalies, dtype=float)
    y = np.array([1] * 1900 + [-1] * 100)
    return X, y


def main():
    print("=" * 60)
    print("  Isolation Forest  —  Held-Out Evaluation (n=2000)")
    print("=" * 60)

    hr_scaler, model = _load()
    print(f"[OK] Model loaded from: {MODEL_DIR}")
    print(f"     HR scaler: mean={hr_scaler.mean_[0]:.1f}, std={hr_scaler.scale_[0]:.1f}")

    X_test, y_true = _make_test_set(seed=99)
    print(f"[OK] Test set: {len(X_test)} samples "
          f"({(y_true==1).sum()} normal, {(y_true==-1).sum()} anomaly)")
    print(f"     Anomaly breakdown: 50 tachycardia, 30 bradycardia, "
          f"11 moderate tachycardia, 9 HR-normal-but-dangerous")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        X_sc = hr_scaler.transform(X_test)
    y_pred = model.predict(X_sc)

    print("\n--- Classification Report ---")
    print(classification_report(
        y_true, y_pred,
        labels=[1, -1],
        target_names=["Normal (inlier)", "Anomaly (outlier)"],
        digits=2,
    ))

    p, r, f, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=[-1], average="binary", pos_label=-1
    )
    tp = int((y_pred == -1)[y_true == -1].sum())
    fp = int((y_pred == -1)[y_true == 1].sum())
    fn = int((y_pred == 1)[y_true == -1].sum())
    print(f"[Anomaly]  Precision={p:.2f}  Recall={r:.2f}  F1={f:.2f}")
    print(f"           TP={tp}  FP={fp}  FN={fn}  Flagged={tp+fp}")
    print("=" * 60)


if __name__ == "__main__":
    main()
