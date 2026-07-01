# app/ai/services/hrv_analyzer.py
"""
HRV (Heart Rate Variability) Analyzer for Elderly Monitoring.

Computes standard short-term HRV metrics from consecutive BPM readings:
  - RMSSD : Root Mean Square of Successive Differences (ms)  → parasympathetic tone
  - SDNN  : Standard Deviation of NN intervals (ms)          → overall HRV
  - pNN50 : Proportion of successive NN diffs > 50 ms (%)    → vagal activity
  - Mean RR: Average RR interval (ms)

Reference thresholds for elderly (age ≥ 60):
  RMSSD < 15 ms       → low HRV (autonomic dysfunction risk)
  RMSSD 15–40 ms      → moderate
  RMSSD > 40 ms       → good
  SDNN  < 20 ms       → very low (associated with cardiac events)
  pNN50 < 3 %         → low parasympathetic activity

Reference: Task Force of ESC/NASPE (1996). "Heart rate variability: standards of
measurement, physiological interpretation, and clinical use." Circulation 93(5).
"""

import math
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── sliding-window settings ─────────────────────────────────────────────────
WINDOW_SIZE   = 60   # Keep last N BPM readings (~60 s at 1 Hz)
MIN_SAMPLES   = 5    # Minimum readings before computing HRV

# ── elderly-specific risk thresholds ────────────────────────────────────────
RMSSD_LOW     = 15.0   # ms
RMSSD_VERY_LOW = 10.0  # ms – emergency flag
SDNN_LOW      = 20.0   # ms
PNN50_LOW     = 3.0    # %


@dataclass
class HRVResult:
    mean_rr: float        # ms
    sdnn:    float        # ms
    rmssd:   float        # ms
    pnn50:   float        # %
    n_samples: int
    risk_level: str       # "normal" | "low_hrv" | "very_low_hrv"
    interpretation: str

    def to_dict(self) -> dict:
        return {
            "mean_rr_ms":      round(self.mean_rr, 2),
            "sdnn_ms":         round(self.sdnn, 2),
            "rmssd_ms":        round(self.rmssd, 2),
            "pnn50_pct":       round(self.pnn50, 2),
            "n_samples":       self.n_samples,
            "risk_level":      self.risk_level,
            "interpretation":  self.interpretation,
        }


class HRVAnalyzer:
    """
    Thread-safe sliding-window HRV analyzer.

    Usage:
        analyzer = HRVAnalyzer()
        analyzer.add_bpm(72)
        analyzer.add_bpm(75)
        ...
        result = analyzer.compute()   # HRVResult or None if too few samples
    """

    def __init__(self, window_size: int = WINDOW_SIZE):
        self._bpm_window: deque = deque(maxlen=window_size)
        self._lock = threading.Lock()

    # ── public API ──────────────────────────────────────────────────────────

    def add_bpm(self, bpm: int) -> None:
        """Add a new BPM reading to the sliding window."""
        try:
            bpm = int(bpm)
            if bpm < 20 or bpm > 300:     # physiologically implausible → ignore
                return
        except (ValueError, TypeError):
            return

        with self._lock:
            self._bpm_window.append(bpm)

    def compute(self) -> Optional[HRVResult]:
        """
        Compute HRV metrics from current window.
        Returns None if not enough samples.
        """
        with self._lock:
            bpms = list(self._bpm_window)

        if len(bpms) < MIN_SAMPLES:
            return None

        # Convert BPM → RR intervals (ms): RR = 60 000 / BPM
        rr = [60_000.0 / b for b in bpms]

        mean_rr = sum(rr) / len(rr)

        # SDNN
        variance = sum((x - mean_rr) ** 2 for x in rr) / len(rr)
        sdnn = math.sqrt(variance)

        # RMSSD & pNN50 — computed on successive differences
        diffs = [abs(rr[i + 1] - rr[i]) for i in range(len(rr) - 1)]
        if not diffs:
            return None

        rmssd   = math.sqrt(sum(d ** 2 for d in diffs) / len(diffs))
        pnn50   = (sum(1 for d in diffs if d > 50.0) / len(diffs)) * 100.0

        risk_level, interpretation = _assess_risk(rmssd, sdnn, pnn50)

        result = HRVResult(
            mean_rr=mean_rr,
            sdnn=sdnn,
            rmssd=rmssd,
            pnn50=pnn50,
            n_samples=len(bpms),
            risk_level=risk_level,
            interpretation=interpretation,
        )
        logger.debug(
            "[HRV] RMSSD=%.1f ms, SDNN=%.1f ms, pNN50=%.1f%% → %s",
            rmssd, sdnn, pnn50, risk_level,
        )
        return result

    def reset(self) -> None:
        with self._lock:
            self._bpm_window.clear()


# ── helpers ──────────────────────────────────────────────────────────────────

def _assess_risk(rmssd: float, sdnn: float, pnn50: float):
    if rmssd < RMSSD_VERY_LOW or sdnn < SDNN_LOW:
        return (
            "very_low_hrv",
            "Very low HRV detected — possible autonomic dysfunction. Immediate caregiver notification recommended.",
        )
    if rmssd < RMSSD_LOW or pnn50 < PNN50_LOW:
        return (
            "low_hrv",
            "Low HRV for elderly — reduced parasympathetic activity. Monitor closely.",
        )
    return (
        "normal",
        "HRV within acceptable range for elderly.",
    )
