"""
manage.py — Unified database management CLI.

Usage:
    python manage.py init                   # Khởi tạo database lần đầu (db.create_all)
    python manage.py migrate                # Chạy tất cả legacy migration scripts
    python manage.py migrate hrv            # Chỉ chạy migration cụ thể
    python manage.py seed                   # Seed dữ liệu demo

    # Alembic / Flask-Migrate commands
    python manage.py db upgrade             # Áp dụng tất cả pending migrations
    python manage.py db upgrade <rev>       # Áp dụng lên đến revision cụ thể
    python manage.py db downgrade -1        # Rollback 1 bước
    python manage.py db migrate -m "msg"    # Autogenerate migration từ model changes
    python manage.py db current             # Hiện revision đang active
    python manage.py db history             # Danh sách tất cả revisions
    python manage.py db stamp head          # Đánh dấu DB là current (sau db.create_all)
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


MIGRATIONS = [
    ("multi_tenant",       "migrate_multi_tenant",       "run"),
    ("hrv",                "migrate_hrv",                "run"),
    ("alert_saved_views",  "migrate_alert_saved_views",  "run"),
    ("alerts_user_id",     "migrate_alerts_user_id",     "run"),
]


def cmd_init():
    from init_db import init
    init()


def cmd_migrate(target: str | None = None):
    import importlib

    to_run = MIGRATIONS
    if target:
        to_run = [(name, mod, fn) for name, mod, fn in MIGRATIONS if name == target]
        if not to_run:
            print(f"❌ Không tìm thấy migration '{target}'.")
            print(f"   Có sẵn: {', '.join(n for n, _, _ in MIGRATIONS)}")
            sys.exit(1)

    for name, module_name, func_name in to_run:
        print(f"\n▶ Chạy migration: {name}")
        mod = importlib.import_module(module_name)
        getattr(mod, func_name)()

    print("\n✅ Tất cả migration đã hoàn thành.")


def cmd_migrate_sqlite_to_mysql():
    from migrate_db import migrate
    migrate()


def cmd_seed():
    import subprocess
    scripts = ["seed_rooms.py", "seed_demo_devices.py"]
    for script in scripts:
        path = os.path.join(BASE_DIR, script)
        if os.path.exists(path):
            print(f"\n▶ Chạy: {script}")
            subprocess.run([sys.executable, path], check=True)
        else:
            print(f"  ⚠ Không tìm thấy: {script}")


def cmd_db(db_args: list[str]):
    """
    Proxy to Flask-Migrate (Alembic) commands via the Flask app context.

    Examples:
        python manage.py db upgrade
        python manage.py db downgrade -1
        python manage.py db migrate -m "add column foo"
        python manage.py db current
        python manage.py db history
        python manage.py db stamp head
    """
    if not db_args:
        print("Usage: python manage.py db <alembic-command> [args...]")
        print("       e.g.  python manage.py db upgrade")
        sys.exit(1)

    os.environ.setdefault("FLASK_APP", os.path.join(BASE_DIR, "run.py"))

    # Build the flask CLI command: flask db <args>
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "flask", "db"] + db_args,
        cwd=BASE_DIR,
        env={**os.environ, "PYTHONPATH": BASE_DIR},
    )
    sys.exit(result.returncode)


def _print_help():
    print(__doc__)


COMMANDS = {
    "init":     cmd_init,
    "migrate":  lambda: cmd_migrate(sys.argv[2] if len(sys.argv) > 2 else None),
    # "import":   cmd_migrate_sqlite_to_mysql,  # Removed cmd_migrate_sqlite_to_mysql
    "seed":     cmd_seed,
    "db":       lambda: cmd_db(sys.argv[2:]),
    "help":     _print_help,
}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    handler = COMMANDS.get(cmd)
    if handler is None:
        print(f"❌ Lệnh không hợp lệ: '{cmd}'")
        _print_help()
        sys.exit(1)
    handler()
