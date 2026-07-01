"""
tools/benchmark_latency.py
===========================
End-to-end pipeline latency benchmark for conference paper (BME11 / ICIT).

Measures the time from receiving a BPM reading to completing:
  T1 — Rule-based tier (threshold check)
  T2 — HRV computation  (sliding window)
  T3 — Full ML inference (scaler + anomaly + mood)
  T4 — Total pipeline (T1 + T2 + T3)

Runs N iterations and reports mean ± std, P95, P99, and max latency.

Usage:
    cd backend
    python tools/benchmark_latency.py [--iterations 1000]
"""

import os
import sys
import time
import statistics
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import numpy as np
import pandas as pd
import joblib

# ── Standalone constants (no Flask import) ───────────────────────────────────
_AI_DIR      = os.path.join(BASE_DIR, "app", "ai")
MODELS_PATH  = os.path.join(_AI_DIR, "models")
FEATURE_COLUMNS = [
    "heart_rate", "room_temp", "humidity",
    "light_level", "hour", "is_night", "is_dark",
]

# Import only the pure-Python HRV module (no Flask dependency)
from app.ai.services.hrv_analyzer import HRVAnalyzer

SEPARATOR = "─" * 65


def _h(t):  return f"\033[1;36m{t}\033[0m"
def _ok(t): return f"\033[1;32m{t}\033[0m"


def _stats_row(label, times_us):
    """Pretty-print a latency row (times in microseconds)."""
    m   = statistics.mean(times_us)
    sd  = statistics.stdev(times_us) if len(times_us) > 1 else 0
    p95 = np.percentile(times_us, 95)
    p99 = np.percentile(times_us, 99)
    mx  = max(times_us)
    print(
        f"  {label:<28}  mean={m:>7.1f} µs  "
        f"std={sd:>6.1f}  P95={p95:>7.1f}  P99={p99:>7.1f}  max={mx:>8.1f}"
    )
    return {"mean_us": m, "std_us": sd, "p95_us": p95, "p99_us": p99, "max_us": mx}


def run_benchmark(n_iterations=1000):
    print(_h("=" * 65))
    print(_h("  IoT Smart Home Elderly — Pipeline Latency Benchmark"))
    print(_h("  Target: BME11 / ICIT Conference 2026"))
    print(_h("=" * 65))

    # ── Load models (optional — benchmark also runs without them) ────────────
    # If model files are missing, the script still measures rule + HRV path.
    # This helps explain why ML latency rows can be near-zero in some runs.
    def _load(name):
        path = os.path.join(MODELS_PATH, f"{name}.pkl")
        return joblib.load(path) if os.path.exists(path) else None

    scaler           = _load("scaler")
    anomaly_model     = _load("anomaly_model")
    anomaly_hr_scaler = _load("anomaly_hr_scaler")
    mood_model        = _load("mood_model")

    has_ml = (
        scaler is not None
        and anomaly_model is not None
        and anomaly_hr_scaler is not None
        and mood_model is not None
    )
    print(f"\n  ML models loaded : {_ok('YES') if has_ml else '  NO (rule+HRV only)'}")
    print(f"  Iterations       : {n_iterations}")

    # Synthetic BPM stream is used for repeatable benchmark conditions.
    # This is a performance benchmark, not a clinical validation dataset.
    rng = np.random.default_rng(42)
    bpm_stream = rng.integers(40, 160, n_iterations).tolist()

    # Pre-warm HRV window
    hrv_analyzer = HRVAnalyzer(window_size=60)
    for bpm in bpm_stream[:60]:
        hrv_analyzer.add_bpm(bpm)

    t1_times, t2_times, t3_times, t3np_times, t4_times = [], [], [], [], []

    _DEFAULTS = {"room_temp": 24.0, "humidity": 50.0, "light_level": 100.0}

    for bpm in bpm_stream:
        t_start = time.perf_counter()

        # ── T1: Rule-based threshold ─────────────────────────────────────
        # Deterministic branch logic only (no model call).
        t1_s = time.perf_counter()
        risk = "normal"
        if bpm >= 130:   risk = "emergency"
        elif bpm >= 100: risk = "warning_high"
        elif bpm < 50:   risk = "warning_low"
        t1_e = time.perf_counter()
        t1_times.append((t1_e - t1_s) * 1_000_000)

        # ── T2: HRV computation ──────────────────────────────────────────
        # Sliding-window HRV update cost.
        t2_s = time.perf_counter()
        hrv_analyzer.add_bpm(bpm)
        _hrv = hrv_analyzer.compute()
        t2_e = time.perf_counter()
        t2_times.append((t2_e - t2_s) * 1_000_000)

        # ── T3a: ML inference via pandas DataFrame (current prod path) ───
        # Represents current backend path used for feature packaging.
        t3_s = time.perf_counter()
        if has_ml:
            import time as _t
            now      = _t.localtime()
            hour     = now.tm_hour
            is_night = 1 if hour < 6 or hour >= 22 else 0
            is_dark  = 1 if hour < 8 or hour >= 18 else 0
            x_df = pd.DataFrame([[
                float(bpm), _DEFAULTS["room_temp"], _DEFAULTS["humidity"],
                _DEFAULTS["light_level"], float(hour), float(is_night), float(is_dark),
            ]], columns=FEATURE_COLUMNS)
            x_scaled = scaler.transform(x_df)
            # The anomaly model is HR-only in runtime, so benchmark it using
            # the HR feature and the dedicated anomaly_hr_scaler.pkl.
            x_hr = np.array([[float(bpm)]])
            x_hr_scaled = anomaly_hr_scaler.transform(x_hr)
            _is_anomaly = anomaly_model.predict(x_hr_scaled)[0] == -1
            _mood       = mood_model.predict(x_scaled)[0]
        t3_e = time.perf_counter()
        t3_times.append((t3_e - t3_s) * 1_000_000)

        # ── T3b: ML inference via numpy array (optimized path) ───────────
        # Used to estimate possible speedup if DataFrame overhead is removed.
        t3np_s = time.perf_counter()
        if has_ml:
            import numpy as _np
            x_np = _np.array([[
                float(bpm), _DEFAULTS["room_temp"], _DEFAULTS["humidity"],
                _DEFAULTS["light_level"], float(hour), float(is_night), float(is_dark),
            ]])
            x_scaled_np = scaler.transform(x_np)
            x_hr_np = _np.array([[float(bpm)]])
            x_hr_scaled_np = anomaly_hr_scaler.transform(x_hr_np)
            anomaly_model.predict(x_hr_scaled_np)[0]
            mood_model.predict(x_scaled_np)[0]
        t3np_e = time.perf_counter()
        t3np_times.append((t3np_e - t3np_s) * 1_000_000)

        t4_times.append((t3_e - t_start) * 1_000_000)

    # ── Results ──────────────────────────────────────────────────────────────
    print(f"\n  {'Stage':<32}  {'mean':>9}  {'std':>8}  {'P95':>9}  {'P99':>9}  {'max':>10}")
    print(f"  {'-'*32}  {'-'*9}  {'-'*8}  {'-'*9}  {'-'*9}  {'-'*10}")
    r1   = _stats_row("T1 Rule-based threshold",      t1_times)
    r2   = _stats_row("T2 HRV computation",            t2_times)
    r3   = _stats_row("T3 ML inference (DataFrame)",   t3_times)
    r3np = _stats_row("T3 ML inference (numpy array)", t3np_times)
    r4   = _stats_row("T4 Total pipeline",             t4_times)

    print(f"\n  {SEPARATOR}")
    mean_ms  = r4['mean_us'] / 1000
    p99_ms   = r4['p99_us']  / 1000
    tput     = 1_000_000 / r4['mean_us']
    np_ms    = (r1['mean_us'] + r2['mean_us'] + r3np['mean_us']) / 1000
    # NOTE: +5 ms is a fixed LAN overhead assumption for presentation.
    # It is not measured inside this script's local compute loop.
    e2e_ms   = mean_ms + 5
    print(f"  Total pipeline mean latency : {_ok(f'{mean_ms:.3f} ms')}")
    print(f"  P99 latency                 : {p99_ms:.3f} ms")
    print(f"  Throughput (1/mean)         : {_ok(f'{tput:,.0f} readings/s')}")
    print(f"\n  Optimized (numpy) pipeline  : {np_ms:.3f} ms  ({mean_ms/np_ms:.1f}x speedup)")
    # This line documents an architecture-level estimate, not a direct timing
    # from the loop above. Keep this distinction explicit during defense.
    print(f"  IoT-context note: MQTT->Flask network overhead typ. 2-10 ms (LAN)")
    print(f"  Total estimated E2E latency : ~{e2e_ms:.1f} ms (current pipeline + LAN)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline latency benchmark")
    parser.add_argument("--iterations", type=int, default=1000,
                        help="Number of BPM readings to simulate (default 1000)")
    args = parser.parse_args()
    run_benchmark(n_iterations=args.iterations)
