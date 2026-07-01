"""
coospo_reader.py — Coospo H6 Heart Rate Monitor → EMQX MQTT
============================================================
Chạy song song với Flask trên Windows:
    python coospo_reader.py

Yêu cầu:
    pip install bleak paho-mqtt certifi
"""

import sys
import io
import logging

# Fix Unicode output on Windows terminal
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import asyncio
from typing import Optional
import json
import os
import ssl
import struct
import time
import threading
from collections import deque
import socket

from bleak import BleakClient, BleakScanner
import paho.mqtt.client as mqtt

# ✅ Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "broker_config.json")


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        return {
            "host":     cfg.get("url", "127.0.0.1"),
            "port":     int(cfg.get("port", 1883)),
            "username": cfg.get("username"),
            "password": cfg.get("password"),
            "tls":      cfg.get("use_tls", False),
            "ca_cert":  cfg.get("ca_cert"),
        }
    except Exception as e:
        logger.warning(f"Cannot read broker_config.json: {e}")
        return {"host": "127.0.0.1", "port": 1883, "username": None,
                "password": None, "tls": False, "ca_cert": None}


HR_SERVICE_UUID    = "0000180d-0000-1000-8000-00805f9b34fb"
HR_CHAR_UUID       = "00002a37-0000-1000-8000-00805f9b34fb"
DEVICE_NAME_FILTER = ["Coospo", "H6", "HRM", "Heart Rate", "H6M", "CooSpo"]
DEVICE_MAC_HINT    = ""


class MQTTPublisher:
    def __init__(self):
        cfg = load_config()
        self.host      = cfg["host"]
        self.port      = cfg["port"]
        # Build unique client_id to avoid broker kicking sessions with duplicated IDs.
        host_tag = socket.gethostname().replace(" ", "_")[:16]
        self.client_id = f"coospo_{host_tag}_{os.getpid()}"
        # Prefer callback API v2 on paho-mqtt>=2 while remaining compatible.
        try:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.client_id,
            )
        except Exception:
            self.client = mqtt.Client(client_id=self.client_id)
        self.connected = False
        self._stop_requested = False
        self._pending = deque(maxlen=200)

        if cfg["username"]:
            self.client.username_pw_set(cfg["username"], cfg["password"])

        if cfg["tls"]:
            ca_cert = cfg.get("ca_cert")
            if ca_cert:
                ca_path = os.path.join(BASE_DIR, ca_cert)
                if os.path.exists(ca_path):
                    self.client.tls_set(ca_certs=ca_path, tls_version=ssl.PROTOCOL_TLS)
                else:
                    print(f"Warning: CA cert not found at {ca_path}, using certifi")
                    import certifi
                    self.client.tls_set(ca_certs=certifi.where(), tls_version=ssl.PROTOCOL_TLS)
            else:
                # No CA cert specified — use TLS but skip verification.
                # Matches the same patch applied in app/extensions/mqtt.py for
                # EMQX Cloud certs whose Basic Constraints is not marked critical.
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                self.client.tls_set_context(ctx)

        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        # paho-mqtt v2 passes ReasonCode object; v1 passes integer — handle both
        rc_val = rc.value if hasattr(rc, 'value') else rc
        if rc_val == 0:
            self.connected = True
            print(f"✅ MQTT connected → {self.host}:{self.port} ({self.client_id})")
            self._flush_pending()
        else:
            print(f"❌ MQTT connect failed (rc={rc})")

    def _on_disconnect(self, client, userdata, *args):
        # v1: (rc) ; v2: (disconnect_flags, reason_code, properties)
        if len(args) >= 2:
            rc = args[1]
        elif len(args) == 1:
            rc = args[0]
        else:
            rc = None
        self.connected = False
        if self._stop_requested:
            print("ℹ️  MQTT disconnected (shutdown).")
            return
        print(f"⚠️  MQTT disconnected (rc={rc}) — retrying...")

    def _flush_pending(self):
        if not self.connected or not self._pending:
            return
        flushed = 0
        while self._pending and self.connected:
            topic, msg = self._pending.popleft()
            result = self.client.publish(topic, msg, qos=0)
            if result.rc != 0:
                # Put back to queue head and stop flushing for now.
                self._pending.appendleft((topic, msg))
                break
            flushed += 1
        if flushed:
            print(f"📤 MQTT flushed {flushed} queued messages")

    def start(self):
        try:
            self._stop_requested = False
            self.client.connect_async(self.host, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"❌ MQTT start error: {e}")

    def publish(self, topic: str, payload):
        """Publish message to MQTT topic. Queue briefly while reconnecting."""
        msg = json.dumps(payload) if isinstance(payload, dict) else str(payload)
        if not self.connected:
            self._pending.append((topic, msg))
            print(f"⚠️  MQTT not connected — queued: {topic} (queue={len(self._pending)})")
            return
        try:
            result = self.client.publish(topic, msg, qos=0)
            if result.rc != 0:
                self._pending.append((topic, msg))
                print(f"⚠️  MQTT publish failed (rc={result.rc}) — queued: {topic}")
        except Exception as e:
            self._pending.append((topic, msg))
            print(f"❌ MQTT publish error on {topic}: {e}")

    def stop(self):
        self._stop_requested = True
        self.client.loop_stop()
        self.client.disconnect()


# ─────────────────────────────────────────
# Parse Heart Rate từ BLE notification
# ─────────────────────────────────────────
def parse_heart_rate(data: bytearray) -> dict:
    """
    Parse Heart Rate Measurement characteristic (0x2A37).
    Byte 0: flags
      bit 0: HR format (0=uint8, 1=uint16)
      bit 4: RR-interval present
    """
    flags = data[0]
    hr_format_16 = flags & 0x01
    rr_present   = (flags >> 4) & 0x01

    if hr_format_16:
        bpm = struct.unpack_from("<H", data, 1)[0]
        offset = 3
    else:
        bpm = data[1]
        offset = 2

    rr_intervals = []
    if rr_present:
        while offset + 1 < len(data):
            rr = struct.unpack_from("<H", data, offset)[0]
            rr_intervals.append(round(rr / 1024 * 1000, 1))  # convert to ms
            offset += 2

    return {
        "bpm":          bpm,
        "rr_intervals": rr_intervals,
        "timestamp":    time.strftime("%H:%M:%S"),
    }


# ─────────────────────────────────────────
# BLE Scanner — tìm Coospo H6
# ─────────────────────────────────────────
async def find_coospo() -> "Optional[str]":
    print("🔍 Đang scan BLE... (15 giây)")

    # Nếu biết MAC address → dùng trực tiếp
    if DEVICE_MAC_HINT:
        print(f"📌 Dùng MAC hint: {DEVICE_MAC_HINT}")
        return DEVICE_MAC_HINT

    # Scan 1: tìm theo tên
    devices = await BleakScanner.discover(timeout=15.0)
    print(f"   Tìm thấy {len(devices)} thiết bị BLE:")
    for d in devices:
        name = d.name or ""
        print(f"   📡 '{name}' [{d.address}]")
        if name and any(kw.lower() in name.lower() for kw in DEVICE_NAME_FILTER):
            print(f"✅ Coospo H6 found by name: {name} [{d.address}]")
            return d.address

    # Scan 2: tìm theo Heart Rate Service UUID (thiết bị không broadcast tên)
    print("🔍 Scan theo Heart Rate Service UUID...")
    try:
        hr_devices = await BleakScanner.discover(
            timeout=15.0,
            service_uuids=[HR_SERVICE_UUID]
        )
        for d in hr_devices:
            name = d.name or "Unknown HRM"
            print(f"✅ Heart Rate device found: {name} [{d.address}]")
            return d.address
    except Exception as e:
        print(f"⚠️  UUID scan failed: {e}")

    print("❌ Không tìm thấy Coospo H6.")
    print("   👉 Thử: Ngắt kết nối H6M trên điện thoại trước khi chạy script")
    print("   👉 Hoặc set DEVICE_MAC_HINT = địa chỉ MAC của thiết bị")
    print("      (chạy lần đầu để xem địa chỉ MAC trong danh sách scan trên)")
    return None


# ─────────────────────────────────────────
# BLE Reader — kết nối và stream HR
# ─────────────────────────────────────────
class CoospoReader:
    def __init__(self, mqtt_pub: MQTTPublisher):
        self.mqtt      = mqtt_pub
        self.address   = None
        self.running   = False
        self.last_bpm: int = 0
        self.total_readings: int = 0

    def _on_hr_notification(self, sender, data: bytearray):
        parsed = parse_heart_rate(data)
        bpm    = parsed["bpm"]

        if bpm < 30 or bpm > 220:
            print(f"⚠️  BPM out of range ({bpm}) — skipping")
            return

        self.last_bpm = bpm
        self.total_readings += 1
        status = "NORMAL"
        if bpm > 100:  status = "HIGH"
        elif bpm < 55: status = "LOW"

        print(f"❤️  BPM: {bpm:3d}  [{status}]  {parsed['timestamp']}"
              + (f"  RR: {parsed['rr_intervals']}" if parsed["rr_intervals"] else ""))

        # Publish riêng heart_rate cho frontend
        self.mqtt.publish("home/sensors/heart_rate", bpm)

        # Publish full payload cho sensor_data DB
        self.mqtt.publish("home/sensors/data", {
            "device_code": "coospo_h6",
            "heart_rate":  bpm,
            "rr_ms":       parsed["rr_intervals"],
            "status":      status,
            "timestamp":   parsed["timestamp"],
        })

    async def connect_and_stream(self):
        self.address = await find_coospo()
        if not self.address:
            return

        retry = 0
        MAX_RETRIES = 10
        while retry < MAX_RETRIES:
            try:
                print(f"🔗 Connecting to {self.address}... (attempt {retry+1}/{MAX_RETRIES})")

                def _on_disconnect(client: BleakClient):
                    print(f"⚠️  BLE disconnected from {client.address}")
                    self.running = False

                async with BleakClient(
                    self.address,
                    timeout=15.0,
                    disconnected_callback=_on_disconnect,
                ) as client:
                    print(f"✅ Connected! Streaming heart rate...")
                    retry = 0  # Reset on success
                    self.running = True

                    await client.start_notify(HR_CHAR_UUID, self._on_hr_notification)

                    # Giữ kết nối — thoát loop khi BLE bị ngắt (callback set self.running=False)
                    while client.is_connected and self.running:
                        await asyncio.sleep(1.0)

                    print("⚠️  BLE disconnected")

            except Exception as e:
                retry += 1
                wait = min(5 * retry, 30)
                print(f"❌ BLE error ({retry}/{MAX_RETRIES}): {e} — retry in {wait}s...")
                if retry < MAX_RETRIES:
                    await asyncio.sleep(wait)

            self.running = False
        print(f"❌ Max retries ({MAX_RETRIES}) reached. Giving up.")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
import signal

def _handle_signal(loop, mqtt_pub):
    """Graceful shutdown on Ctrl+C or SIGTERM."""
    print("\n👋 Nhận tín hiệu dừng...")
    mqtt_pub.stop()
    loop.stop()

async def main():
    print("=" * 50)
    print("💓 COOSPO H6 — BATMAN OS HEART RATE BRIDGE")
    print("=" * 50)

    mqtt_pub = MQTTPublisher()
    mqtt_pub.start()

    # Wait a bit for the first TLS connect, but do not exit early.
    # MQTTPublisher already auto-retries and queues messages while offline.
    for _ in range(20):
        if mqtt_pub.connected:
            break
        await asyncio.sleep(0.5)

    if not mqtt_pub.connected:
        print("⚠️  MQTT chưa kết nối trong thời gian chờ ban đầu — vẫn tiếp tục chạy và auto-retry.")

    reader = CoospoReader(mqtt_pub)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal, loop, mqtt_pub)
        except NotImplementedError:
            pass  # Windows không support add_signal_handler — dùng KeyboardInterrupt

    try:
        await reader.connect_and_stream()
    except KeyboardInterrupt:
        print("\n👋 Dừng Coospo reader.")
    finally:
        mqtt_pub.stop()
        print("✅ Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
