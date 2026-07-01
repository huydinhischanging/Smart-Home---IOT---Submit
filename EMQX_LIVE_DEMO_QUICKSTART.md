# EMQX Live Demo Quickstart

This file is a copy-paste guide for live validation with EMQX, the Flask backend, and one ESP32 board.

## 1. Preconditions

- Backend is running.
- Frontend is reachable.
- You have a valid Bearer token.
- EMQX Cloud WebSocket/TCP console is open.
- Your ESP32 `esp32_secrets.h` matches the device codes/types below.

## 2. Health Checks

Backend health:

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" http://localhost:5000/api/health
```

Device schema:

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" http://localhost:5000/api/devices/schema
```

## 3. Create Demo Devices

Create humidity sensor:

```bash
curl -X POST http://localhost:5000/api/devices \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\"device_name\":\"Do am A1\",\"device_id\":\"do_am_a1\",\"device_type\":\"humidity\",\"category\":\"sensor\",\"room_id\":2,\"metadata\":{\"unit\":\"%\"}}"
```

Create light actuator:

```bash
curl -X POST http://localhost:5000/api/devices \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\"device_name\":\"Den 1\",\"device_id\":\"den1\",\"device_type\":\"light\",\"category\":\"light\",\"room_id\":1,\"metadata\":{\"brand\":\"ESP32 relay\"}}"
```

List devices:

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" http://localhost:5000/api/devices
```

## 4. EMQX Publish Samples

### 4.1 Sensor Ingest

Legacy topic:

- Topic: `home/sensors/do_am_a1`
- Payload: `65.2`

V2 topic:

- Topic: `home/sensors/humidity/do_am_a1`
- Payload: `66.5`

PIR example:

- Topic: `home/sensors/motion/chuyen_dong_a1`
- Payload: `DETECTED`

Light example:

- Topic: `home/sensors/light/anh_sang_a1`
- Payload: `78`

Recommended EMQX publish options:

- QoS: `0`
- Retain: `false` for manual demo publishes

### 4.2 Actuator Control

Legacy control:

- Topic: `home/control/den1`
- Payload: `ON`

V2 control:

- Topic: `home/control/light/den1`
- Payload: `OFF`

Numeric control example:

- Topic: `home/control/light/den1`
- Payload: `100`

## 5. REST Checks After Publish

Sensor detail:

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" http://localhost:5000/api/devices/sensors/humidity/do_am_a1
```

Sensor history:

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" http://localhost:5000/api/devices/sensors/humidity/do_am_a1/history?limit=5
```

Actuator detail:

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" http://localhost:5000/api/devices/actuators/light/den1
```

Actuator control by REST v2:

```bash
curl -X POST http://localhost:5000/api/devices/actuators/light/den1/control \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\"action\":\"ON\"}"
```

Legacy REST control:

```bash
curl -X POST http://localhost:5000/api/devices/control \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\"device_code\":\"den1\",\"action\":\"OFF\"}"
```

## 6. Expected Results

- `GET /api/devices` shows `do_am_a1` with `device_type=humidity`.
- `GET /api/devices/sensors/humidity/do_am_a1/history` returns recent numeric readings.
- `GET /api/devices/actuators/light/den1` reflects `is_on=true/false` after commands.
- Dashboard updates by `device_code`, not by display name.
- ESP32 publishes status on both:
  - `home/status/den1`
  - `home/status/light/den1`

## 7. 90-Second Demo Script

1. Show `GET /api/health` and say the backend is healthy.
2. Show `GET /api/devices/schema` and say device creation now supports scalable fields: name, code/id, type, category, location, metadata.
3. Create one humidity sensor `do_am_a1` by REST.
4. In EMQX, publish `66.5` to `home/sensors/humidity/do_am_a1`.
5. Open `GET /api/devices/sensors/humidity/do_am_a1/history?limit=5` and show the new reading.
6. Create one light actuator `den1` by REST.
7. Call `POST /api/devices/actuators/light/den1/control` with `{"action":"ON"}`.
8. Show the relay/UI status changed and mention that legacy topics still work for backward compatibility.

## 8. Suggested Demo Device Map

- `do_am_a1` -> humidity sensor
- `nhiet_do_a1` -> temperature sensor
- `anh_sang_a1` -> light sensor
- `chuyen_dong_a1` -> motion sensor
- `den1` -> light actuator
- `quat1` -> fan actuator

## 9. ESP32 Mapping Reminder

In `esp32_secrets.h`, keep code and type aligned:

```cpp
#define DEVICE_CODE_DEN "den1"
#define DEVICE_TYPE_DEN "light"

#define DEVICE_CODE_QUAT "quat1"
#define DEVICE_TYPE_QUAT "fan"

#define SENSOR_CODE_HUMIDITY "do_am_a1"
#define SENSOR_TYPE_HUMIDITY "humidity"
```

That gives you dual publish support automatically:

- `home/sensors/do_am_a1`
- `home/sensors/humidity/do_am_a1`
- `home/status/den1`
- `home/status/light/den1`