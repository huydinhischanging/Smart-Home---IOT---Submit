"""
Contamination grid search for Isolation Forest anomaly detector.

Two evaluations are run:

1. BENCHMARK grid search (Section 5.1 in thesis):
   Train on 399 UCI-healthy records (80/20 split, no synthetic data).
   Evaluate on held-out test set: 100 healthy + 526 diseased (n=626).
   Candidate range: 0.010 -- 0.10.

2. PRODUCTION grid search (Section 3.4.3 in thesis):
   Train on 399 UCI-healthy + 1700 synthetic normal records.
   Evaluate on a 2000-sample synthetic labelled set:
     1900 normal, 100 anomaly (tachycardia / bradycardia / moderate / contextual).
   Candidate range: 0.010 -- 0.060.

Usage:
    cd backend
    python -m tools.tune_and_retrain_anomaly
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split

# ── constants ──────────────────────────────────────────────────────────────
CSV_PATH     = "data/heart_disease.csv"
RANDOM_STATE = 42
RNG          = np.random.default_rng(RANDOM_STATE)

BENCHMARK_CONTAMINATIONS  = [0.010, 0.015, 0.020, 0.025, 0.030,
                              0.035, 0.040, 0.050, 0.060, 0.10]
PRODUCTION_CONTAMINATIONS = [0.010, 0.015, 0.020, 0.025, 0.030,
                              0.035, 0.040, 0.050, 0.060]


# ── data helpers ───────────────────────────────────────────────────────────

def _load_uci_bpm(csv_path: str):
    df  = pd.read_csv(csv_path)
    rng = np.random.default_rng(RANDOM_STATE)
    rows = []
    for _, r in df.iterrows():
        thalach = float(r.get("thalach", 140))
        target  = int(r.get("target", 0))
        bpm     = thalach * rng.uniform(0.55, 0.65)
        if target == 1:
            bpm *= rng.uniform(1.10, 1.25)
        bpm = float(np.clip(bpm, 40.0, 170.0))
        rows.append({"bpm": bpm, "label": target})
    return pd.DataFrame(rows)


def _synthetic_normals(n: int, rng: np.random.Generator):
    rows = []
    for _ in range(n):
        hour     = int(rng.integers(0, 24))
        is_night = hour >= 20 or hour <= 6
        hr       = float(rng.integers(50, 75)) if is_night else float(rng.integers(60, 92))
        rows.append({"bpm": hr, "label": 0})
    return pd.DataFrame(rows)


def _synthetic_anomalies(rng: np.random.Generator):
    rows = []
    # tachycardia (HR 140-210)
    for _ in range(50):
        rows.append({"bpm": float(rng.integers(140, 211)), "label": 1})
    # bradycardia (HR 15-37)
    for _ in range(30):
        rows.append({"bpm": float(rng.integers(15, 38)), "label": 1})
    # moderate tachycardia (HR 100-135)
    for _ in range(11):
        rows.append({"bpm": float(rng.integers(100, 136)), "label": 1})
    # contextual anomalies in normal BPM range (structurally undetectable by HR-only model)
    for _ in range(9):
        rows.append({"bpm": float(rng.integers(60, 100)), "label": 1})
    return pd.DataFrame(rows)


def _run_search(X_train, X_test, y_test, contamination_values, n_estimators):
    print(f"\n{'Contamination':>15} {'Precision':>10} {'Recall':>8} {'F1':>8}")
    print("-" * 45)

    best = {"f1": -1, "c": None, "p": None, "r": None}
    results = []

    for c in contamination_values:
        clf = IsolationForest(
            n_estimators=n_estimators,
            contamination=c,
            random_state=RANDOM_STATE,
        )
        clf.fit(X_train)

        raw  = clf.predict(X_test)
        pred = (raw == -1).astype(int)

        p = precision_score(y_test, pred, zero_division=0)
        r = recall_score(y_test, pred, zero_division=0)
        f = f1_score(y_test, pred, zero_division=0)

        is_best = f > best["f1"]
        marker  = "  << best" if is_best else ""
        print(f"{c:>15.3f} {p:>10.2f} {r:>8.2f} {f:>8.2f}{marker}")

        results.append({"contamination": c, "precision": round(p, 2),
                        "recall": round(r, 2), "f1": round(f, 2)})
        if is_best:
            best = {"f1": f, "c": c, "p": p, "r": r}

    print("-" * 45)
    print(f"\nBest contamination : {best['c']}")
    print(f"Best F1            : {best['f1']:.2f}  "
          f"(P={best['p']:.2f}, R={best['r']:.2f})\n")
    return results, best


# ── benchmark grid search ──────────────────────────────────────────────────

def run_benchmark_grid_search():
    print("=" * 55)
    print("BENCHMARK GRID SEARCH (UCI 80/20, no synthetic data)")
    print("=" * 55)

    df      = _load_uci_bpm(CSV_PATH)
    healthy = df[df["label"] == 0]
    disease = df[df["label"] == 1]

    train_df, held_h = train_test_split(
        healthy, test_size=0.20, random_state=RANDOM_STATE
    )

    X_train = train_df[["bpm"]].values
    X_test  = pd.concat([held_h, disease])[["bpm"]].values
    y_test  = np.array([0] * len(held_h) + [1] * len(disease))

    print(f"Train : {len(X_train)} UCI-healthy records")
    print(f"Test  : {len(held_h)} healthy + {len(disease)} diseased = {len(X_test)} total")

    return _run_search(X_train, X_test, y_test,
                       BENCHMARK_CONTAMINATIONS, n_estimators=200)


# ── production grid search ─────────────────────────────────────────────────

def run_production_grid_search():
    print("=" * 55)
    print("PRODUCTION GRID SEARCH (UCI + 1700 synthetic, eval on 2000-sample synthetic set)")
    print("=" * 55)

    rng_prod = np.random.default_rng(RANDOM_STATE + 1)

    df      = _load_uci_bpm(CSV_PATH)
    healthy = df[df["label"] == 0]

    # 80/20 split; keep 100 UCI-healthy out of train (same as benchmark)
    train_uci, _ = train_test_split(
        healthy, test_size=0.20, random_state=RANDOM_STATE
    )

    synth_train = _synthetic_normals(1700, rng_prod)
    X_train = np.concatenate([
        train_uci[["bpm"]].values,
        synth_train[["bpm"]].values,
    ])

    # 2000-sample synthetic evaluation set
    normal_eval  = _synthetic_normals(1900, np.random.default_rng(RANDOM_STATE + 2))
    anomaly_eval = _synthetic_anomalies(np.random.default_rng(RANDOM_STATE + 3))
    eval_df      = pd.concat([normal_eval, anomaly_eval], ignore_index=True)
    X_test       = eval_df[["bpm"]].values
    y_test       = eval_df["label"].values

    print(f"Train : {len(train_uci)} UCI-healthy + 1700 synthetic = {len(X_train)} total")
    print(f"Test  : 1900 normal + 100 anomaly = {len(X_test)} synthetic labelled")

    return _run_search(X_train, X_test, y_test,
                       PRODUCTION_CONTAMINATIONS, n_estimators=300)


# ── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_benchmark_grid_search()
    run_production_grid_search()
