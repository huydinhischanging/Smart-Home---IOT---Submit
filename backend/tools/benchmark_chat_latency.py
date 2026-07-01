"""
tools/benchmark_chat_latency.py
===============================
Chatbot latency benchmark for Alfred (Ollama path).

This script measures runtime decomposition from AIService.ask_alfred_with_timing:
  - prompt_ms
  - llm_ms
  - postprocess_ms
  - total_ms

Important scope:
  - Measures AI service call path directly (no Flask route/auth middleware).
  - LLM round-trip is included (requests to Ollama /api/generate).
  - Useful for slide numbers on chatbot response performance.

Usage:
  cd backend
  python tools/benchmark_chat_latency.py --iterations 20
"""

import argparse
import os
import statistics
import sys
from time import perf_counter

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.ai.inference.model_loader import ModelLoader
from app.ai.services.ai_service import AIService


def _stats_row(label, values_ms):
    if not values_ms:
        print(f"  {label:<24}  no data")
        return {"mean": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

    mean_v = statistics.mean(values_ms)
    p95_v = float(np.percentile(values_ms, 95))
    p99_v = float(np.percentile(values_ms, 99))
    max_v = max(values_ms)

    print(
        f"  {label:<24}  mean={mean_v:>8.2f} ms  "
        f"P95={p95_v:>8.2f}  P99={p99_v:>8.2f}  max={max_v:>8.2f}"
    )
    return {"mean": mean_v, "p95": p95_v, "p99": p99_v, "max": max_v}


def run_benchmark(iterations=20, language="vi"):
    print("=" * 70)
    print(" Alfred Chatbot Latency Benchmark (AIService decomposition)")
    print("=" * 70)

    loader = ModelLoader()
    service = AIService(model_loader=loader)

    house_context = {
        "current_floor": "TANG 1",
        "floors": [
            {"name": "TANG 1", "room_names": ["A", "B"]},
            {"name": "TANG 2", "room_names": ["C"]},
        ],
        "rooms": [
            {"name": "A", "device_names": ["den_a", "quat_a"]},
            {"name": "B", "device_names": ["ac_b"]},
            {"name": "C", "device_names": ["den_c"]},
        ],
        "devices": [
            {"name": "den_a", "code": "LED_A"},
            {"name": "quat_a", "code": "FAN_A"},
            {"name": "ac_b", "code": "AC_B"},
            {"name": "den_c", "code": "LED_C"},
        ],
    }

    messages = [
        "bat den phong A",
        "tat quat phong A",
        "phong B co gi",
        "what devices are in room C",
        "turn off all lights",
    ]

    # Warm-up run to reduce first-call noise.
    _ = service.ask_alfred_with_timing(messages[0], house_context, preferred_language=language)

    prompt_ms, llm_ms, post_ms, total_ms = [], [], [], []
    errors = {}

    print(f"Iterations: {iterations}")
    print(f"Preferred language: {language}")

    for i in range(iterations):
        msg = messages[i % len(messages)]

        t_start = perf_counter()
        result = service.ask_alfred_with_timing(msg, house_context, preferred_language=language)
        outer_total_ms = (perf_counter() - t_start) * 1000

        timings = result.get("timings", {})
        err = timings.get("error")

        if err:
            errors[err] = errors.get(err, 0) + 1

        prompt_ms.append(float(timings.get("prompt_ms", 0.0)))
        llm_ms.append(float(timings.get("llm_ms", 0.0)))
        post_ms.append(float(timings.get("postprocess_ms", 0.0)))
        total_ms.append(float(timings.get("total_ms", outer_total_ms)))

    print("\nLatency decomposition:")
    s_prompt = _stats_row("Prompt build", prompt_ms)
    s_llm = _stats_row("LLM call", llm_ms)
    s_post = _stats_row("Postprocess", post_ms)
    s_total = _stats_row("Total (service)", total_ms)

    backend_overhead = max(s_total["mean"] - s_llm["mean"], 0.0)
    print("\nDerived (mean):")
    print(f"  Backend overhead ~= {backend_overhead:.2f} ms (total - llm)")

    if errors:
        print("\nErrors observed:")
        for key, count in sorted(errors.items()):
            print(f"  - {key}: {count}/{iterations}")
    else:
        print("\nErrors observed: none")

    print("\nNote: This benchmark excludes Flask route/auth/middleware and browser->backend network.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Alfred chatbot latency")
    parser.add_argument("--iterations", type=int, default=20, help="Number of benchmark requests")
    parser.add_argument("--language", type=str, default="vi", help="Preferred language (vi/en/auto)")
    args = parser.parse_args()

    run_benchmark(iterations=args.iterations, language=args.language)
