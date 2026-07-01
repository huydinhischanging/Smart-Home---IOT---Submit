# Tong hop module Medicine Reminder

Ngay cap nhat: 2026-05-10
Pham vi: Backend + Mobile + test lien quan den medicine reminder trong project IOT-SMARTHOME-ELDERLY

## 1. Module nay lam gi

Medicine Reminder la module nhac uong thuoc theo gio.

Chuc nang chinh:
- Tao reminder cho tung user.
- Luu thuoc, lieu dung, gio nhac, recurrence va email nhan them.
- Moi 1 phut scheduler quet reminder den han.
- Neu den han thi gui email reminder neu email gateway co cau hinh.
- Dong thoi tao alert trong he thong de hien thi tren UI/lich su canh bao.
- Danh dau da gui trong ngay de tranh gui lap.

## 2. Luong chay tong quan

Luong runtime:

1. User tao reminder tren Mobile/Web qua API /api/reminders.
2. Reminder duoc luu vao bang medicine_reminders trong MySQL.
3. APScheduler chay job medicine_reminder_dispatch moi 1 phut.
4. Job goi MedicineReminderUseCase.dispatch_due_reminders().
5. Use case loc reminder active va den khung gio phu hop.
6. Moi reminder hop le se:
   - resolve danh sach nguoi nhan email
   - gui email reminder
   - tao alert warning trong he thong
   - cap nhat last_sent_on = hom nay
7. UI co the doc danh sach reminder qua API va doc alert qua alert flow rieng.

## 3. Thuat toan duoc dung

Day khong phai machine learning. Day la thuat toan rule-based scheduler + time-window matching.

### 3.1. Y tuong chinh

He thong khong canh tung giay. Thay vao do, scheduler chay moi 1 phut.
De tranh truong hop cron/job lech vai giay va bi miss reminder, code dung cua so thoi gian +-1 phut.

Vi du neu bay gio la 10:00:05 thi tap candidate la:
- 09:59
- 10:00
- 10:01

Reminder co time_of_day nam trong tap nay se duoc xem xet.

### 3.2. Bo loc logic

Sau khi query danh sach candidate, he thong tiep tuc loc:
- reminder phai active
- hom nay chua gui reminder nay
- recurrence phai phu hop voi ngay hien tai:
  - daily: ngay nao cung gui
  - weekday: chi gui thu 2 den thu 6
  - weekend: chi gui thu 7 va chu nhat

### 3.3. Hanh dong sau khi match

Neu reminder hop le, he thong:
- lay email cua user + email phu (notify_email) neu co
- gui email qua EmailNotifier
- tao 1 alert noi bo muc warning
- ghi last_sent_on de khoa duplicate trong ngay

### 3.4. Do phuc tap

Neu goi k la so reminder duoc query trong khung gio hien tai:
- Query DB: da duoc giam tai nho index tren is_active + time_of_day
- Xu ly vong lap: O(k)
- Chi phi lon nhat thuc te la I/O gui email, khong phai CPU

## 4. Pseudo-code ngan gon

```text
every 1 minute:
    now = current time
    candidates = {now - 1 minute, now, now + 1 minute} formatted HH:MM

    due_reminders = query reminders where:
        is_active = true
        time_of_day in candidates

    for each reminder in due_reminders:
        if reminder.last_sent_on == today:
            continue
        if recurrence does not match today:
            continue

        recipients = resolve(user_email, notify_email)
        send email reminder
        create warning alert
        reminder.last_sent_on = today

    commit transaction
```

## 5. Cac file chinh cua module

### 5.1. Wiring / Dependency Injection

File:
- backend/app/wiring.py

Vai tro:
- Dang ky EmailNotifier singleton.
- Dang ky MedicineReminderUseCase singleton.
- Inject email_notifier va alert_usecase vao reminder use case.

Y nghia khi bao ve:
- Day la noi ghep dependency, cho thay module reminder khong hard-code gateway.

### 5.2. Scheduler runtime

File:
- backend/app/scheduler.py

Vai tro:
- Khai bao job medicine_reminder_dispatch.
- Trigger interval 1 minute.
- Goi _dispatch_medicine_reminders(app).
- Trong ham nay se goi container.medicine_reminder_usecase().dispatch_due_reminders().

Y nghia:
- Day la lop scheduler orchestration, khong chua business logic chi tiet.

### 5.3. Business logic chinh

File:
- backend/app/usecases/medicine_reminder_usecase.py

Vai tro:
- serialize reminder
- list_for_user
- create_for_user
- set_taken
- delete
- dispatch_due_reminders
- _matches_recurrence

Y nghia:
- Day la file quan trong nhat cua module medicine reminder.
- Chua validation input va toan bo thuat toan dispatch.

### 5.4. Email gateway

File:
- backend/app/gateways/email_notifier.py

Vai tro:
- Parse recipient list
- Resolve recipients tu user_email + extra email
- Gui mail qua SMTP hoac Brevo
- Bao trang thai sent / reason / recipients

Y nghia:
- Reminder module tach business logic va email transport.
- Neu email chua cau hinh, reminder van tao alert noi bo.

### 5.5. Data model / bang database

File:
- backend/app/infrastructure/persistence/models/medicine_reminder_model.py

Vai tro:
- Dinh nghia bang medicine_reminders
- Cac cot chinh:
  - user_id
  - medicine_name
  - dosage
  - time_of_day
  - recurrence
  - notify_email
  - is_active
  - last_sent_on
  - last_taken_on
- Tao index idx_med_reminder_time tren (is_active, time_of_day)

Y nghia:
- Ho tro query nhanh khi scheduler quet reminder den han.

### 5.6. API layer

File:
- backend/app/presentation/api/reminder_api.py

Vai tro:
- GET /api/reminders: list reminder theo user dang login
- POST /api/reminders: tao reminder moi
- PATCH /api/reminders/<id>/taken: danh dau da uong
- DELETE /api/reminders/<id>: xoa reminder

Y nghia:
- Day la lop presentation / HTTP endpoint cho mobile va frontend.

## 6. Cac file UI lien quan

### 6.1. Mobile provider

File:
- MOBILE/lib/modules/automation/automation_provider.dart

Vai tro:
- Goi API /api/reminders
- createReminder()
- loadReminders()
- markReminderTaken()
- deleteReminder()

### 6.2. Mobile screen

File:
- MOBILE/lib/screens/routine_screen.dart

Vai tro:
- Hien thi danh sach medicine reminders
- Mo sheet tao reminder moi
- Cho phep mark taken va xoa reminder

Luu y:
- Mobile screen khong tu dispatch reminder.
- Dispatch that su xay ra o backend scheduler.

## 7. Cac file test quan trong

File:
- backend/tests/test_medicine_reminder_usecase.py
- backend/tests/test_scheduler.py
- backend/tests/test_integration_flow.py
- backend/tests/test_notification_delivery.py

Noi dung test quan trong:
- tao va list reminder
- validate time HH:MM
- validate recurrence
- delete dung/sai user
- dispatch gui reminder khi den gio
- skip neu da gui trong ngay
- cua so -1 phut va +1 phut
- scheduler goi dung use case

Y nghia khi bao ve:
- Chung minh module reminder da duoc test cho ca business logic va scheduler integration.

## 8. Cau tra loi ngan gon de bao ve

### 8.1. Tra loi bang tieng Viet

Medicine reminder trong de tai duoc trien khai theo co che rule-based scheduler. APScheduler chay moi 1 phut, sau do goi medicine reminder use case de query cac reminder active trong cua so thoi gian +-1 phut quanh thoi diem hien tai. He thong tiep tuc loc theo recurrence daily, weekday, weekend va kiem tra last_sent_on de tranh gui lap trong cung mot ngay. Neu reminder hop le, backend se gui email neu email gateway da cau hinh, dong thoi tao alert warning trong he thong va cap nhat last_sent_on.

### 8.2. Tra loi bang tieng Anh

The medicine reminder module uses a rule-based scheduler rather than machine learning. APScheduler runs every minute and calls the medicine reminder use case. That use case queries active reminders within a +-1 minute time window around the current time, then filters them by recurrence rule and by last_sent_on to avoid duplicate sends on the same day. If a reminder is valid, the backend sends an email if the email gateway is configured, creates an internal warning alert, and updates last_sent_on.

## 9. Diem can nho khi hoi sau

- Algorithm: rule-based scheduling, not AI/ML.
- Reliability trick: time window +-1 minute.
- Duplicate prevention: last_sent_on.
- Recurrence logic: daily / weekday / weekend.
- Transport layer: EmailNotifier.
- UI chi tao/xem reminder; backend moi la noi dispatch that su.