"""
tools/evaluate_models.py
========================
Model evaluation script for conference paper (BME11 / ICIT).

Generates a results table with precision, recall, F1, and AUC for:
  1. Anomaly Detection  (Isolation Forest)
  2. Mood Classification (Random Forest)
  3. Automation Prediction (Random Forest)

Also runs the HRV analyzer against a synthetic elderly dataset and
prints HRV summary statistics suitable for a paper results table.

Usage:
    cd backend
    python tools/evaluate_models.py
"""

import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    accuracy_score,
    precision_recall_fscore_support,
)

# ── Standalone constants (no Flask import) ───────────────────────────────────
_AI_DIR      = os.path.join(BASE_DIR, "app", "ai")
MODELS_PATH  = os.path.join(_AI_DIR, "models")
FEATURE_COLUMNS = [
    "heart_rate", "room_temp", "humidity",
    "light_level", "hour", "is_night", "is_dark",
]

from app.ai.services.hrv_analyzer import HRVAnalyzer

# ── colour helpers ────────────────────────────────────────────────────────────
def _h(txt): return f"\033[1;36m{txt}\033[0m"   # cyan bold
def _ok(txt): return f"\033[1;32m{txt}\033[0m"  # green
def _warn(txt): return f"\033[1;33m{txt}\033[0m"
def _err(txt): return f"\033[1;31m{txt}\033[0m"

SEPARATOR = "-" * 70


# ── dataset ───────────────────────────────────────────────────────────────────
def _make_eval_dataset(seed=0):
    """
    Build a labelled synthetic evaluation dataset mimicking elderly patients.
    Anomalies: HR < 45 or HR > 115 (conservative elderly thresholds).
    """
    rng = np.random.default_rng(seed)
    n_normal    = 400
    n_anomaly   = 80   # ~17 % contamination → realistic for elderly

    # Normal samples
    hr_n   = rng.integers(55, 100, n_normal).astype(float)
    tmp_n  = rng.uniform(20, 30, n_normal)
    hum_n  = rng.uniform(40, 70, n_normal)
    lux_n  = rng.uniform(50, 300, n_normal)
    hr_n_l = rng.integers(6, 22, n_normal).astype(float)

    # Anomaly samples (bradycardia / tachycardia)
    hr_a  = np.concatenate([
        rng.integers(25, 45, n_anomaly // 2).astype(float),   # bradycardia
        rng.integers(120, 160, n_anomaly // 2).astype(float),  # tachycardia
    ])
    tmp_a = rng.uniform(20, 34, n_anomaly)
    hum_a = rng.uniform(35, 75, n_anomaly)
    lux_a = rng.uniform(10, 350, n_anomaly)
    hr_a_l = rng.integers(0, 24, n_anomaly).astype(float)

    def _df(hr, tmp, hum, lux, hour, label):
        is_night = (hour < 6) | (hour >= 22)
        is_dark  = (hour < 8) | (hour >= 18)
        return pd.DataFrame({
            "heart_rate":   hr,
            "room_temp":    tmp,
            "humidity":     hum,
            "light_level":  lux,
            "hour":         hour,
            "is_night":     is_night.astype(float),
            "is_dark":      is_dark.astype(float),
            "label":        label,
        })

    df = pd.concat([
        _df(hr_n, tmp_n, hum_n, lux_n, hr_n_l, 0),   # 0 = normal
        _df(hr_a, tmp_a, hum_a, lux_a, hr_a_l, 1),   # 1 = anomaly
    ], ignore_index=True).sample(frac=1, random_state=seed)

    return df


def _calc_mood(hr, is_night, lux):
    """Mirror of train_pipeline._calc_mood, applied per sample."""
    moods = []
    for h, n, l in zip(hr, is_night, lux):
        if h >= 130:              moods.append("EMERGENCY")
        elif h >= 100:            moods.append("ELEVATED")
        elif n == 1 and l < 20:   moods.append("QUIET")
        elif n == 1 and h < 65:   moods.append("SLEEP")
        elif h < 60:              moods.append("REST")
        elif h >= 80 and l > 60:  moods.append("ACTIVE")
        else:                     moods.append("NORMAL")
    return moods


# ══════════════════════════════════════════════════════════════════════════════
# 1. ANOMALY DETECTION EVALUATION
# ══════════════════════════════════════════════════════════════════════════════
def evaluate_anomaly(df, scaler, anomaly_model):
    print(_h("\n[1/3] Anomaly Detection  —  Isolation Forest"))
    print(SEPARATOR)

    X = df[FEATURE_COLUMNS]
    y_true = df["label"].values            # 0 = normal, 1 = anomaly
    X_scaled = scaler.transform(X)

    # IsolationForest: -1 = anomaly, +1 = normal
    raw_pred = anomaly_model.predict(X_scaled)
    y_pred   = (raw_pred == -1).astype(int)

    scores = anomaly_model.score_samples(X_scaled)   # lower = more anomalous
    y_score = -scores                                  # flip sign → higher = anomaly

    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    try:
        auc = roc_auc_score(y_true, y_score)
    except Exception:
        auc = float("nan")

    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    print(f"  Accuracy  : {_ok(f'{acc*100:.2f} %')}")
    print(f"  Precision : {prec*100:.2f} %")
    print(f"  Recall    : {rec*100:.2f} %")
    print(f"  F1 Score  : {f1*100:.2f} %")
    print(f"  AUC-ROC   : {auc:.4f}")
    print(f"\n  Confusion Matrix:")
    print(f"              Predicted Normal  Predicted Anomaly")
    print(f"  True Normal :     {tn:>6}              {fp:>6}")
    print(f"  True Anomaly:     {fn:>6}              {tp:>6}")

    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "auc": auc}


# ══════════════════════════════════════════════════════════════════════════════
# 2. MOOD CLASSIFICATION EVALUATION
# ══════════════════════════════════════════════════════════════════════════════
def evaluate_mood(df, scaler, mood_model):
    print(_h("\n[2/3] Mood Classification  —  Random Forest"))
    print(SEPARATOR)

    X = df[FEATURE_COLUMNS]
    X_scaled = scaler.transform(X)
    y_true = _calc_mood(df["heart_rate"], df["is_night"], df["light_level"])
    y_pred = mood_model.predict(X_scaled)

    acc = accuracy_score(y_true, y_pred)
    print(f"  Accuracy  : {_ok(f'{acc*100:.2f} %')}")
    print()
    print(classification_report(y_true, y_pred, zero_division=0))

    return {"accuracy": acc}


# ══════════════════════════════════════════════════════════════════════════════
# 3. HRV EVALUATION (synthetic stream)
# ══════════════════════════════════════════════════════════════════════════════
def evaluate_hrv(df):
    print(_h("\n[3/3] HRV Analysis  —  Sliding Window (RMSSD / SDNN / pNN50)"))
    print(SEPARATOR)

    rng = np.random.default_rng(7)

    def _simulate_stream(base_bpm, noise_std, n=200):
        """Simulate a realistic gradual BPM stream (not random jumps)."""
        bpms = [base_bpm]
        for _ in range(n - 1):
            next_bpm = bpms[-1] + rng.normal(0, noise_std)
            next_bpm = float(np.clip(next_bpm, base_bpm - 15, base_bpm + 15))
            bpms.append(round(next_bpm))
        return bpms

    scenarios = [
        ("Normal elderly (70 BPM)",       _simulate_stream(70,  1.5, 200), "normal"),
        ("Mild tachycardia (105 BPM)",     _simulate_stream(105, 2.0, 200), "warning_high"),
        ("Bradycardia (42 BPM)",           _simulate_stream(42,  1.0, 200), "warning_low"),
        ("Low-variability flat (72 BPM)",  [72] * 200,                       "normal_flat"),
    ]

    all_rmssd, all_sdnn, all_pnn50 = [], [], []
    all_risk_counts = {"normal": 0, "low_hrv": 0, "very_low_hrv": 0}

    for scenario_name, bpm_stream, _ in scenarios:
        analyzer = HRVAnalyzer(window_size=60)
        results  = []
        for bpm in bpm_stream:
            analyzer.add_bpm(int(bpm))
            r = analyzer.compute()
            if r:
                results.append(r)

        if not results:
            continue

        rmssd_v = [r.rmssd  for r in results]
        sdnn_v  = [r.sdnn   for r in results]
        pnn50_v = [r.pnn50  for r in results]

        print(f"\n  Scenario: {scenario_name}")
        print(f"    RMSSD : {np.mean(rmssd_v):6.2f} ± {np.std(rmssd_v):.2f} ms")
        print(f"    SDNN  : {np.mean(sdnn_v):6.2f} ± {np.std(sdnn_v):.2f} ms")
        print(f"    pNN50 : {np.mean(pnn50_v):6.2f} ± {np.std(pnn50_v):.2f} %")
        print(f"    Risk  : {results[-1].risk_level}  — {results[-1].interpretation[:60]}...")

        for r in results:
            all_rmssd.append(r.rmssd)
            all_sdnn.append(r.sdnn)
            all_pnn50.append(r.pnn50)
            all_risk_counts[r.risk_level] = all_risk_counts.get(r.risk_level, 0) + 1

    total = sum(all_risk_counts.values()) or 1
    low_rate = (all_risk_counts.get("low_hrv", 0) + all_risk_counts.get("very_low_hrv", 0)) / total * 100

    print(f"\n  Overall risk distribution (all scenarios):")
    for k, v in all_risk_counts.items():
        bar = "█" * max(1, v // 20)
        print(f"    {k:<18}: {v:>5}  {bar}")
    print(f"\n  Low HRV rate      : {_warn(f'{low_rate:.1f} %')}")

    return {
        "rmssd_mean": float(np.mean(all_rmssd)),
        "sdnn_mean":  float(np.mean(all_sdnn)),
        "pnn50_mean": float(np.mean(all_pnn50)),
        "low_hrv_rate_pct": low_rate,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print(_h("=" * 70))
    print(_h("  IoT Smart Home Elderly — Model Evaluation Report"))
    print(_h("  Target: BME11 / ICIT Conference 2026"))
    print(_h("=" * 70))

    # Load models
    def _load(name):
        path = os.path.join(MODELS_PATH, f"{name}.pkl")
        if not os.path.exists(path):
            print(_warn(f"  [SKIP] {name}.pkl not found at {path}"))
            return None
        return joblib.load(path)

    scaler        = _load("scaler")
    anomaly_model = _load("anomaly_model")
    mood_model    = _load("mood_model")

    if scaler is None:
        print(_err("\n  Scaler not found — run training first: python run.py (triggers auto-train)"))
        sys.exit(1)

    df = _make_eval_dataset(seed=42)
    print(f"\n  Evaluation dataset: {len(df)} samples "
          f"({(df['label']==0).sum()} normal, {(df['label']==1).sum()} anomaly)")

    results = {}

    if anomaly_model:
        results["anomaly"] = evaluate_anomaly(df, scaler, anomaly_model)
    if mood_model:
        results["mood"] = evaluate_mood(df, scaler, mood_model)

    results["hrv"] = evaluate_hrv(df)

    # ── Paper-ready summary table ──────────────────────────────────────────
    print(_h(f"\n{'═'*70}"))
    print(_h("  SUMMARY TABLE  (copy to paper)"))
    print(_h(f"{'═'*70}"))
    print(f"  {'Module':<28} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>8} {'AUC':>8}")
    print(f"  {'-'*28} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
    if "anomaly" in results:
        a = results["anomaly"]
        print(
            f"  {'Anomaly Detection':<28}"
            f" {a['accuracy']*100:>9.2f}%"
            f" {a['precision']*100:>9.2f}%"
            f" {a['recall']*100:>9.2f}%"
            f" {a['f1']*100:>7.2f}%"
            f" {a['auc']:>8.4f}"
        )
    if "mood" in results:
        m = results["mood"]
        print(
            f"  {'Mood Classification':<28}"
            f" {m['accuracy']*100:>9.2f}%"
            f" {'—':>9}  {'—':>9}  {'—':>7}  {'—':>8}"
        )
    if "hrv" in results and results["hrv"]:
        h = results["hrv"]
        print(f"\n  HRV Metrics (elderly synthetic stream):")
        print(f"    RMSSD mean : {h['rmssd_mean']:.2f} ms")
        print(f"    SDNN  mean : {h['sdnn_mean']:.2f} ms")
        print(f"    pNN50 mean : {h['pnn50_mean']:.2f} %")
        print(f"    Low HRV rate: {h['low_hrv_rate_pct']:.1f} %")
    print()


if __name__ == "__main__":
    main()
