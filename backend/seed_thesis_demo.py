#!/usr/bin/env python3
"""
seed_thesis_demo.py  -  iot_smarthome demo data
Account  : demothesisiot / demothesisiot  (role=admin)
Rooms    : Living Room, Bedroom, Kitchen
Devices  : 18 nodes across 3 rooms (ESP32 hardware + virtual demo devices)
Patient  : sample elderly profile

Run:
  cd backend
  python seed_thesis_demo.py
"""

import sys, os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from werkzeug.security import generate_password_hash
from app.config.db_app import create_db_app
from app.extensions.database import db
from app.infrastructure.persistence.models.device_model import Device
from app.infrastructure.persistence.models.device_status_model import DeviceStatus
from app.infrastructure.persistence.models.user_model import UserModel
from app.infrastructure.persistence.models.rooms_model import RoomModel
from app.infrastructure.persistence.models.patient_profile_model import PatientProfileModel

DEMO_USERNAME = "demothesisiot"
DEMO_EMAIL    = "demothesisiot@smarthome.local"
DEMO_PASSWORD = "demothesisiot"
DEMO_ROLE     = "admin"

DEMO_ROOMS = [
    {"name": "Living Room", "color": "rgba(253,185,19,0.22)"},
    {"name": "Bedroom",     "color": "rgba(99,179,237,0.22)"},
    {"name": "Kitchen",     "color": "rgba(154,230,180,0.22)"},
]

# ---------------------------------------------------------------
# Devices per room
# category enum: sensor | actuator | light | fan | ac | camera |
#                lock | switch | tv | speaker | other
# ---------------------------------------------------------------
DEMO_DEVICES_BY_ROOM = {
    "Living Room": [
        # --- ESP32 hardware (GPIO-mapped) ---
        {"code": "den",         "name": "Den Phong Khach", "icon": "💡", "category": "light",  "device_type": "relay",   "control_types": ["switch"], "note": "Relay 1 GPIO17"},
        {"code": "quat",        "name": "Quat Phong Khach","icon": "🌀", "category": "fan",    "device_type": "relay",   "control_types": ["switch"], "note": "Relay 2 GPIO16"},
        {"code": "temperature", "name": "Nhiet Do",        "icon": "🌡", "category": "sensor", "device_type": "dht11",   "control_types": [],         "note": "DHT11 GPIO15"},
        {"code": "humidity",    "name": "Do Am",           "icon": "💧", "category": "sensor", "device_type": "dht11",   "control_types": [],         "note": "DHT11 GPIO15"},
        {"code": "light",       "name": "Anh Sang",        "icon": "🔆", "category": "sensor", "device_type": "ldr",     "control_types": [],         "note": "LDR GPIO32"},
        {"code": "pir",         "name": "Cam Bien Chuyen Dong", "icon": "📡", "category": "sensor", "device_type": "pir", "control_types": [],        "note": "PIR HC-SR501 GPIO33"},
        # --- Virtual demo devices (MQTT-controllable) ---
        {"code": "dieu_hoa",    "name": "Dieu Hoa",        "icon": "❄️", "category": "ac",     "device_type": "ir_blaster", "control_types": ["switch", "temperature"], "note": "IR AC controller"},
        {"code": "tivi",        "name": "Tivi",             "icon": "📺", "category": "tv",     "device_type": "smart_tv",   "control_types": ["switch"],               "note": "Smart TV"},
        {"code": "loa",         "name": "Loa",              "icon": "🔊", "category": "speaker","device_type": "smart_speaker","control_types": ["switch"],             "note": "Smart Speaker"},
        {"code": "camera_pk",   "name": "Camera Phong Khach","icon": "📷","category": "camera", "device_type": "ip_camera",  "control_types": [],                       "note": "IP Camera"},
    ],
    "Bedroom": [
        {"code": "den_phong_ngu",       "name": "Den Phong Ngu",       "icon": "💡", "category": "light",  "device_type": "relay",      "control_types": ["switch"],               "note": "Bedroom light relay"},
        {"code": "quat_phong_ngu",      "name": "Quat Phong Ngu",      "icon": "🌀", "category": "fan",    "device_type": "relay",      "control_types": ["switch"],               "note": "Bedroom fan relay"},
        {"code": "dieu_hoa_phong_ngu",  "name": "Dieu Hoa Phong Ngu",  "icon": "❄️", "category": "ac",     "device_type": "ir_blaster", "control_types": ["switch", "temperature"], "note": "Bedroom AC"},
        {"code": "o_cam_phong_ngu",     "name": "O Cam Thong Minh",    "icon": "🔌", "category": "switch", "device_type": "smart_plug", "control_types": ["switch"],               "note": "Smart plug beside bed"},
        {"code": "cam_bien_giuong",     "name": "Cam Bien Giuong",     "icon": "🛏", "category": "sensor", "device_type": "pressure",   "control_types": [],                       "note": "Bed occupancy sensor (elderly)"},
    ],
    "Kitchen": [
        {"code": "den_bep",     "name": "Den Bep",          "icon": "💡", "category": "light",  "device_type": "relay",      "control_types": ["switch"], "note": "Kitchen light relay"},
        {"code": "bao_khoi",    "name": "Bao Dong Khoi",    "icon": "🚨", "category": "sensor", "device_type": "smoke",      "control_types": [],         "note": "Smoke detector"},
        {"code": "bao_gas",     "name": "Bao Dong Gas",     "icon": "⚠️", "category": "sensor", "device_type": "gas_sensor", "control_types": [],         "note": "Gas leak detector (elderly safety)"},
    ],
}

DEMO_PATIENT = {
    "patient_name": "Nguyen Van A (Demo)", "age": 72, "gender": "Male",
    "baseline_hr_rest": 72.0, "baseline_hr_min": 55.0, "baseline_hr_max": 100.0,
    "diagnosis_notes": "Demo patient for thesis presentation. Simulated elderly profile.",
    "medications": "None (demo)",
}


def _upsert_device(d, user_id, room_id):
    existing = Device.query.filter_by(code=d["code"], user_id=user_id, is_deleted=False).first()
    if existing:
        changed = False
        if existing.room_id != room_id:
            existing.room_id = room_id
            changed = True
        if changed:
            db.session.flush()
            return existing, "fix"
        return existing, "skip"

    device = Device(
        name=d["name"], code=d["code"], icon=d["icon"],
        category=d["category"], device_type=d["device_type"],
        user_id=user_id, room_id=room_id, is_deleted=False,
    )
    device.types_list = d["control_types"]
    db.session.add(device)
    db.session.flush()
    db.session.add(DeviceStatus(device_id=device.id, is_on=False, value="OFF"))
    return device, "new"


def seed():
    app = create_db_app()
    with app.app_context():

        # 1. User
        print("-" * 60)
        user = UserModel.query.filter_by(username=DEMO_USERNAME).first()
        if user:
            print(f"[SKIP] User '{DEMO_USERNAME}' (id={user.id})")
            if user.role != DEMO_ROLE:
                user.role = DEMO_ROLE
                db.session.flush()
                print(f"[FIX]  Role -> {DEMO_ROLE}")
        else:
            user = UserModel(
                username=DEMO_USERNAME, email=DEMO_EMAIL,
                password=generate_password_hash(DEMO_PASSWORD),
                role=DEMO_ROLE, is_active=True,
            )
            db.session.add(user)
            db.session.flush()
            print(f"[OK]   Created '{DEMO_USERNAME}' / '{DEMO_PASSWORD}'  role={DEMO_ROLE}")
        user_id = user.id

        # 2. Rooms + Devices
        room_ids = {}
        for room_def in DEMO_ROOMS:
            print("-" * 60)
            room = RoomModel.query.filter_by(user_id=user_id, name=room_def["name"]).first()
            if room:
                print(f"[SKIP] Room '{room_def['name']}' (id={room.id})")
            else:
                room = RoomModel(
                    user_id=user_id, name=room_def["name"],
                    color=room_def["color"], polygon_data=[],
                )
                db.session.add(room)
                db.session.flush()
                print(f"[OK]   Room '{room_def['name']}' (id={room.id})")
            room_ids[room_def["name"]] = room.id

            devs = DEMO_DEVICES_BY_ROOM.get(room_def["name"], [])
            created = fixed = skipped = 0
            for d in devs:
                _, status = _upsert_device(d, user_id, room.id)
                if status == "new":
                    print(f"  [OK]   {d['code']:28s} '{d['name']}'")
                    created += 1
                elif status == "fix":
                    print(f"  [FIX]  {d['code']:28s} -> room updated")
                    fixed += 1
                else:
                    skipped += 1
            print(f"  -> {created} new, {fixed} fixed, {skipped} skipped")

        # 3. Patient profile
        print("-" * 60)
        profile = PatientProfileModel.query.filter_by(user_id=user_id).first()
        if profile:
            print(f"[SKIP] Patient profile (id={profile.id})")
        else:
            profile = PatientProfileModel(
                user_id=user_id,
                patient_name=DEMO_PATIENT["patient_name"],
                age=DEMO_PATIENT["age"],
                gender=DEMO_PATIENT["gender"],
                baseline_hr_rest=DEMO_PATIENT["baseline_hr_rest"],
                baseline_hr_min=DEMO_PATIENT["baseline_hr_min"],
                baseline_hr_max=DEMO_PATIENT["baseline_hr_max"],
                diagnosis_notes=DEMO_PATIENT["diagnosis_notes"],
                medications=DEMO_PATIENT["medications"],
                consent_analytics=True, consent_pdf_export=True,
            )
            db.session.add(profile)
            db.session.flush()
            print(f"[OK]   Patient profile '{DEMO_PATIENT['patient_name']}'")

        db.session.commit()

        # 4. Summary
        print("-" * 60)
        total = sum(len(v) for v in DEMO_DEVICES_BY_ROOM.values())
        print(f"Done. {total} devices across {len(DEMO_ROOMS)} rooms.")
        print(f"  Login : {DEMO_USERNAME} / {DEMO_PASSWORD}  (role={DEMO_ROLE})")
        print()
        print("  Rooms:")
        for r in DEMO_ROOMS:
            n = len(DEMO_DEVICES_BY_ROOM.get(r["name"], []))
            print(f"    {r['name']:15s}  {n} devices")
        print()
        print("  Alfred categories now available:")
        print("    light  -> den, den_phong_ngu, den_bep")
        print("    fan    -> quat, quat_phong_ngu")
        print("    ac     -> dieu_hoa, dieu_hoa_phong_ngu")
        print("    tv     -> tivi")
        print("    speaker-> loa")
        print("    sensor -> temperature, humidity, light, pir, cam_bien_giuong, bao_khoi, bao_gas")
        print("    camera -> camera_pk")


if __name__ == "__main__":
    seed()
