#!/usr/bin/env python3
"""
run_tests.py — Script chạy toàn bộ test suite và tạo báo cáo HTML + coverage.

Sử dụng:
    python run_tests.py               # Chạy tất cả tests + HTML report
    python run_tests.py --fast        # Không tạo coverage (nhanh hơn)
    python run_tests.py --file auth   # Chỉ chạy test_auth_api.py
    python run_tests.py --open        # Mở báo cáo sau khi chạy xong

Output:
    backend/test_results/report.html       — Báo cáo test HTML
    backend/test_results/coverage_html/    — Báo cáo coverage HTML
"""
import argparse
import os
import subprocess
import sys
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, "..", ".venv", "Scripts", "pytest.exe")
if not os.path.isfile(VENV_PYTHON):
    VENV_PYTHON = os.path.join(BASE_DIR, "..", ".venv", "bin", "pytest")

REPORT_DIR = os.path.join(BASE_DIR, "test_results")
REPORT_HTML = os.path.join(REPORT_DIR, "report.html")
COVERAGE_HTML = os.path.join(REPORT_DIR, "coverage_html", "index.html")


def main():
    parser = argparse.ArgumentParser(description="Alfred Backend Test Runner")
    parser.add_argument("--fast", action="store_true", help="Skip coverage collection")
    parser.add_argument("--file", "-f", type=str, help="Run tests matching this pattern")
    parser.add_argument("--open", "-o", action="store_true", help="Open report in browser after run")
    args = parser.parse_args()

    os.makedirs(REPORT_DIR, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = BASE_DIR
    env["USE_SQLITE_DEV"] = "true"

    cmd = [VENV_PYTHON]

    # Test selection
    if args.file:
        test_path = f"tests/test_{args.file}_api.py" if not args.file.startswith("tests/") else args.file
        if not os.path.isfile(os.path.join(BASE_DIR, test_path)):
            test_path = f"tests/{args.file}"
        cmd.append(test_path)
    else:
        cmd.append("tests")

    # Coverage
    if not args.fast:
        cmd += [
            "--cov=app",
            "--cov-report=term-missing",
            f"--cov-report=html:{os.path.join(REPORT_DIR, 'coverage_html')}",
        ]

    # HTML report
    cmd += [
        f"--html={REPORT_HTML}",
        "--self-contained-html",
        "-v",
    ]

    print(f"\n{'='*60}")
    print("  Alfred Backend Test Suite")
    print(f"{'='*60}")
    print(f"  Command: {' '.join(cmd)}")
    print(f"  Output:  {REPORT_HTML}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=BASE_DIR, env=env)

    print(f"\n{'='*60}")
    if result.returncode == 0:
        print("  RESULT: ALL TESTS PASSED")
    else:
        print(f"  RESULT: SOME TESTS FAILED (exit code {result.returncode})")
    print(f"  Report: {REPORT_HTML}")
    if not args.fast:
        print(f"  Coverage: {COVERAGE_HTML}")
    print(f"{'='*60}\n")

    if args.open and os.path.isfile(REPORT_HTML):
        webbrowser.open(f"file://{REPORT_HTML}")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
