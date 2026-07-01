# Hướng dẫn: Scheduler trong hệ thống Alfred Smart Home

## 1. Tổng quan

Scheduler dùng **APScheduler (BackgroundScheduler)** — chạy ngầm trong background thread
phía server, hoàn toàn độc lập với Flask request và không phụ thuộc vào việc client có
đang mở app hay không.

Scheduler quản lý **3 loại tác vụ** hoàn toàn khác nhau:

| Loại | Trigger | Tần suất kiểm tra |
|------|---------|-------------------|
| Schedule (Calendar) | Theo giờ/ngày (cron) | Reload DB mỗi 5 phút |
| Automation | Điều kiện cảm biến | Mỗi 30 giây |
| Medicine Reminder | Theo giờ uống thuốc | Mỗi 1 phút |

---

## 2. Khởi động Scheduler

Khi Flask app start, hàm `init_scheduler(app)` được gọi một lần duy nhất.
Nó đăng ký 3 job cố định rồi gọi `_reload_schedules()` ngay lập tức để nạp
các schedule từ DB mà không cần chờ 5 phút đầu tiên.

```
Flask app start
    └── init_scheduler(app)
            ├── Đăng ký automation_check       (interval 30s)
            ├── Đăng ký medicine_reminder      (interval 1 phút)
            ├── Đăng ký schedule_reload        (interval 5 phút)
            └── _reload_schedules() ngay lập tức
```

Cấu hình quan trọng:
- `coalesce=True` — nếu server downtime và miss nhiều lần kích hoạt, chỉ chạy 1 lần
  khi phục hồi thay vì chạy bù toàn bộ
- `max_instances=1` — mỗi job chỉ chạy 1 instance cùng lúc
- `timezone="Asia/Ho_Chi_Minh"` — múi giờ Việt Nam

---

## 3. Loại 1 — Schedule (giống Calendar)

### Mục đích
Điều khiển thiết bị theo giờ/ngày cố định.
Ví dụ: "7:00 sáng mỗi ngày → bật đèn phòng ngủ"

### Lưu trữ
Bảng DB: `schedules`
Mỗi row có một `cron_expr` theo cú pháp crontab Linux:

```
"0 7 * * *"     →  7:00 sáng mỗi ngày
"0 22 * * 1-5"  →  22:00 thứ 2 đến thứ 6
"30 6 * * 6,0"  →  6:30 sáng thứ 7 và Chủ nhật
```

### Cách hoạt động

**Mỗi 5 phút** — `_reload_schedules()` chạy:
1. Xóa toàn bộ job có prefix `schedule_*` đang chạy trong APScheduler
2. Query lại toàn bộ `schedules` có `is_active = True` từ DB
3. Đăng ký lại mỗi schedule thành một `CronTrigger`

**Khi đến đúng giờ** — `_execute_schedule(schedule_id)` chạy:
1. Load schedule từ DB, kiểm tra `is_active`
2. Tìm thiết bị cần điều khiển
3. Gửi lệnh MQTT đến ESP32
4. Cập nhật `DeviceStatus` trong DB

### Luồng ví dụ

```
User tạo Schedule "bật đèn lúc 7:00"
    └── DB: schedules { cron_expr="0 7 * * *", device_id=3, action={is_on: true} }
            └── (tối đa 5 phút) _reload_schedules() nạp vào APScheduler
                    └── 7:00 sáng → _execute_schedule()
                            ├── MQTT publish → ESP32 bật đèn
                            └── DeviceStatus.is_on = True
```

---

## 4. Loại 2 — Automation (điều kiện cảm biến)

### Mục đích
Tự động kích hoạt thiết bị khi cảm biến đạt ngưỡng.
Ví dụ: "Nhiệt độ > 35°C → bật quạt"

### Lưu trữ
Bảng DB: `automations`
Mỗi row có `trigger_condition` dạng chuỗi:

```
"value > 35"       →  giá trị cảm biến lớn hơn 35
"value == 'ON'"    →  cảm biến đang bật
"is_on == true"    →  thiết bị đang ON
"value <= 20"      →  độ ẩm nhỏ hơn hoặc bằng 20
```

Operators hỗ trợ: `==`, `!=`, `>`, `>=`, `<`, `<=`

### Cách hoạt động

**Mỗi 30 giây** — `_check_automations()` chạy:
1. Query toàn bộ `automations` có `is_active = True`
2. Với mỗi automation:
   - Đọc `DeviceStatus` của thiết bị trigger (cảm biến)
   - Chạy `_eval_condition()` so sánh giá trị hiện tại với điều kiện
   - Nếu thỏa → gửi lệnh MQTT đến thiết bị hành động + cập nhật DB

### An toàn
`_eval_condition()` dùng regex — **không bao giờ dùng `eval()`** trên chuỗi
điều kiện từ user, tránh code injection.

### Luồng ví dụ

```
ESP32 gửi sensor: nhiệt độ = 37°C
    └── DB: DeviceStatus { device_id=2, value="37" }
            └── (tối đa 30s) _check_automations() chạy
                    └── "value > 35" → 37 > 35 → TRUE
                            ├── MQTT publish → ESP32 bật quạt
                            └── DeviceStatus (quạt).is_on = True
```

---

## 5. Loại 3 — Medicine Reminder (nhắc thuốc)

### Mục đích
Nhắc người dùng uống thuốc đúng giờ qua email và alert trong app.

### Lưu trữ
Bảng DB: `medicine_reminders`

| Cột | Kiểu | Ý nghĩa |
|-----|------|---------|
| `medicine_name` | VARCHAR(60) | Tên thuốc |
| `dosage` | VARCHAR(80) | Liều lượng |
| `time_of_day` | VARCHAR(5) | Giờ uống, format "HH:MM" |
| `recurrence` | ENUM | `daily` / `weekday` / `weekend` |
| `is_active` | BOOLEAN | Đang kích hoạt hay không |
| `last_sent_on` | DATE | Ngày gửi gần nhất (tránh gửi 2 lần/ngày) |
| `last_taken_on` | DATE | Ngày user xác nhận đã uống |
| `notify_email` | VARCHAR(255) | Email phụ nhận thông báo |

Index: `(is_active, time_of_day)` để query nhanh.

### Cách hoạt động

**Mỗi 1 phút** — `_dispatch_medicine_reminders()` chạy:

1. Tính cửa sổ thời gian ±1 phút so với giờ hiện tại:
   ```python
   candidates = {"HH:MM-1", "HH:MM", "HH:MM+1"}
   ```
   Cửa sổ ±1 phút để tránh miss khi scheduler bị lệch vài giây.

2. Query DB:
   ```sql
   SELECT * FROM medicine_reminders
   WHERE is_active = 1
     AND time_of_day IN ('HH:MM-1', 'HH:MM', 'HH:MM+1');
   ```

3. Với mỗi reminder khớp, kiểm tra 3 điều kiện:
   - `last_sent_on != hôm nay` — chưa gửi hôm nay
   - `recurrence` phù hợp ngày hiện tại (daily/weekday/weekend)
   - Nếu đủ điều kiện:
     - Gửi email đến user và `notify_email` (nếu có)
     - Tạo Alert trong hệ thống → hiện lên tab Notifications
     - Cập nhật `last_sent_on = hôm nay`

### Luồng ví dụ — Set lịch 9:00 uống thuốc

```
User nhấn lưu trên app
    └── POST /api/reminders { name: "Paracetamol", time: "09:00", days: "daily" }
            └── DB: medicine_reminders { time_of_day="09:00", last_sent_on=NULL }

8:59  Scheduler chạy → window {"08:58", "08:59", "09:00"} → khớp "09:00"
        └── last_sent_on = NULL → chưa gửi hôm nay → GỬI
                ├── Email: "Nhắc uống Paracetamol lúc 09:00"
                ├── Alert tạo trong DB → hiện trên app
                └── last_sent_on = 2026-05-17

9:00  Scheduler chạy → khớp lại → last_sent_on = hôm nay → BỎ QUA
9:01  Tương tự → BỎ QUA

Ngày mai 8:59  last_sent_on = hôm qua ≠ ngày mai → GỬI LẠI
```

### Ví dụ với data thực tế trong DB

```
id=1  user_id=8   aspirin      00:30  daily  → gửi lúc nửa đêm
id=4  user_id=7   thuoctay     17:16  daily  → gửi lúc chiều
id=5  user_id=11  thuoc tim    19:16  daily  → gửi lúc tối
id=6  user_id=11  thuoc tim    14:11  daily  → gửi lúc 2 giờ chiều
```

User 11 có 2 reminder — scheduler gửi riêng từng cái đúng giờ của nó.
Scheduler không cần user đang online — chạy hoàn toàn phía server.

---

## 6. Multi-user

Scheduler xử lý tất cả user cùng lúc, không phân biệt ai đang đăng nhập:

```python
# Không có filter user_id — quét toàn bộ bảng
MedicineReminderModel.query.filter(
    MedicineReminderModel.is_active == True,
    MedicineReminderModel.time_of_day.in_(candidates),
).all()
```

Mở 2 tab, 10 tab, hay không mở tab nào — scheduler vẫn chạy như nhau.

---

## 7. Hiệu năng

Với quy mô hệ thống smart home cá nhân/gia đình:

- Query đơn giản, có index → chưa tới 1ms mỗi lần
- `BackgroundScheduler` chạy thread riêng → không ảnh hưởng Flask API
- Tổng tải: ~3 query/phút + ~2 query/30s → hoàn toàn không đáng kể

Nếu scale lên hàng nghìn user đồng thời, cần chuyển sang Celery Beat + Redis.

---

## 8. Sơ đồ tổng quan

```
                    APScheduler (Background Thread)
                    ┌──────────────────────────────────┐
                    │                                  │
  mỗi 30s ─────────┤─► _check_automations()           │
                    │      └── Query automations        │
                    │      └── Eval condition           │
                    │      └── MQTT publish             │
                    │                                  │
  mỗi 1 phút ──────┤─► _dispatch_medicine_reminders() │
                    │      └── Query time window        │
                    │      └── Send email + Alert       │
                    │                                  │
  mỗi 5 phút ──────┤─► _reload_schedules()            │
                    │      └── Query schedules DB       │
                    │      └── Register CronTriggers    │
                    │                                  │
  đúng giờ cron ───┤─► _execute_schedule(id)          │
                    │      └── MQTT publish             │
                    │      └── Update DeviceStatus      │
                    └──────────────────────────────────┘
                                   │
                              MySQL DB (batman_os)
                    ┌──────────────┬──────────────────┐
                    │  schedules   │  automations      │
                    │  medicine_   │  device_status    │
                    │  reminders   │  alerts           │
                    └──────────────┴──────────────────┘
```
