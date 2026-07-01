# DEFENSE Q&A (Bilingual VI/EN)

Project: IoT Smart Home for Elderly Care  
Version: Updated 2026-05-10  
Usage: You can answer in Vietnamese or English based on the committee question language.

---

## Section A - Overview

### Q1
VI Question: De tai giai quyet van de gi?  
VI Answer: De tai xay dung he thong smart home ho tro nguoi cao tuoi song an toan hon tai nha. He thong giam sat du lieu cam bien, theo doi nhip tim, nhac uong thuoc, va canh bao khan cap cho nguoi cham soc.

EN Question: What problem does this project solve?  
EN Answer: This project builds a smart home system to support safer independent living for elderly people. It monitors sensor data, tracks heart rate, sends medicine reminders, and provides emergency alerts to caregivers.

### Q2
VI Question: Tai sao chon doi tuong nguoi cao tuoi?  
VI Answer: Nguoi cao tuoi co nguy co gap su co suc khoe dot ngot, te nga, quen uong thuoc, va thuong can giam sat lien tuc. Giai phap IoT giup phat hien som va giam thoi gian phan ung.

EN Question: Why did you target elderly users?  
EN Answer: Elderly users are at higher risk of sudden health events, falls, and medication non-adherence. IoT monitoring helps detect risks early and reduces response time.

### Q3
VI Question: Dong gop chinh cua de tai la gi?  
VI Answer: Dong gop chinh gom 3 phan: kien truc hybrid IoT + AI, co che canh bao da tang (rule-based + anomaly detection), va tro ly Alfred ho tro hoi dap/dieu khien thong minh.

EN Question: What are the key contributions of this thesis?  
EN Answer: The key contributions are: a hybrid IoT + AI architecture, a multi-layer alerting mechanism (rule-based plus anomaly detection), and the Alfred assistant for smart Q&A and control.

---

## Section B - System Architecture

### Q4
VI Question: He thong gom nhung thanh phan nao?  
VI Answer: He thong gom ESP32 + sensors, MQTT broker (EMQX), Flask backend, MySQL, Web dashboard (Vite), va Mobile app (Flutter).

EN Question: What are the main system components?  
EN Answer: The system includes ESP32 with sensors, an MQTT broker (EMQX), a Flask backend, MySQL database, a web dashboard (Vite), and a mobile app (Flutter).

### Q5
VI Question: Luong du lieu tu sensor den nguoi dung nhu the nao?  
VI Answer: Sensor -> ESP32 -> MQTT topic -> Flask subscriber -> DB + AI processing -> Socket.IO/REST -> Web/Mobile UI.

EN Question: How does data flow from sensor to user interface?  
EN Answer: Sensor -> ESP32 -> MQTT topic -> Flask subscriber -> database and AI processing -> Socket.IO/REST -> web/mobile UI.

### Q6
VI Question: Tai sao chon Flask thay vi FastAPI hoac Django?  
VI Answer: Flask linh hoat, nhe, phu hop voi Clean Architecture va tich hop on dinh voi MQTT + Socket.IO trong du an hien tai.

EN Question: Why Flask instead of FastAPI or Django?  
EN Answer: Flask is lightweight and flexible, fits Clean Architecture well, and integrates stably with MQTT and Socket.IO in this project.

### Q7
VI Question: Tai sao dung Flutter cho mobile?  
VI Answer: Flutter cho phep mot codebase cho Android/iOS, hieu nang tot, va quy trinh dev nhanh voi hot reload.

EN Question: Why did you choose Flutter for mobile?  
EN Answer: Flutter enables a single codebase for Android/iOS, provides good performance, and supports fast development via hot reload.

---

## Section C - IoT and MQTT

### Q8
VI Question: Tai sao dung MQTT thay vi HTTP polling?  
VI Answer: MQTT co overhead thap, ket noi persistent, va push real-time, phu hop thiet bi IoT tai nguyen han che.

EN Question: Why MQTT instead of HTTP polling?  
EN Answer: MQTT has lower overhead, persistent connections, and real-time push behavior, which is more suitable for resource-constrained IoT devices.

### Q9
VI Question: Topic MQTT duoc to chuc nhu the nao?  
VI Answer: Theo namespace ro rang, vi du home/sensors/{device_code} cho telemetry va home/status/{device_code} cho lenh dieu khien.

EN Question: How are MQTT topics organized?  
EN Answer: Topics follow a clear namespace, such as home/sensors/{device_code} for telemetry and home/status/{device_code} for control commands.

### Q10
VI Question: Neu ESP32 mat ket noi thi sao?  
VI Answer: ESP32 thuc hien reconnect dinh ky. Khi ket noi lai, no tiep tuc publish trang thai hien tai de dong bo backend va giao dien.

EN Question: What happens if ESP32 disconnects?  
EN Answer: ESP32 performs periodic reconnection. After reconnecting, it republishes current states so the backend and UI can synchronize.

### Q11
VI Question: Co dam bao thong diep khong bi mat khong?  
VI Answer: He thong uu tien real-time. Co the nang cap them QoS phu hop tung topic, retained message, va persistent session de tang do tin cay.

EN Question: How do you ensure messages are not lost?  
EN Answer: The current design prioritizes real-time behavior. Reliability can be strengthened further using appropriate QoS, retained messages, and persistent sessions.

---

## Section D - Data and Backend

### Q12
VI Question: Backend ap dung kien truc gi?  
VI Answer: Backend theo Clean Architecture voi cac layer presentation, usecase, domain ports, infrastructure, va gateways.

EN Question: Which architecture does the backend use?  
EN Answer: The backend follows Clean Architecture with presentation, use cases, domain ports, infrastructure, and gateway layers.

### Q13
VI Question: Loi ich cua Clean Architecture trong de tai nay?  
VI Answer: De test don vi, de mock phu thuoc, de thay doi DB/gateway ma it anh huong business logic.

EN Question: What are the benefits of Clean Architecture here?  
EN Answer: It improves unit testing, dependency mocking, and replacement of DB/gateways with minimal impact on business logic.

### Q14
VI Question: Du lieu duoc luu o dau?  
VI Answer: Du lieu duoc luu tren MySQL qua SQLAlchemy, gom users, devices, sensor_data, alerts, reminders, va patient heart-rate records.

EN Question: Where is data stored?  
EN Answer: Data is stored in MySQL via SQLAlchemy, including users, devices, sensor data, alerts, reminders, and patient heart-rate records.

### Q15
VI Question: He thong co da tenant hay khong?  
VI Answer: Co huong ho tro multi-tenant qua migration va tach du lieu theo user/family context. Muc do khai thac phu thuoc cau hinh deployment.

EN Question: Does the system support multi-tenancy?  
EN Answer: The codebase includes a multi-tenant direction through migrations and data separation by user/family context. Full behavior depends on deployment configuration.

---

## Section E - AI and Health Analytics

### Q16
VI Question: AI duoc dat o dau trong he thong?  
VI Answer: AI xuat hien trong Alfred Assistant (NLP/intents), trong module danh gia nhip tim, va trong anomaly detection cho du lieu sinh ton va moi truong.

EN Question: Where is AI used in the system?  
EN Answer: AI is used in the Alfred Assistant (NLP/intents), while anomaly detection for vital and environmental data is handled by the detection algorithm. The heart-rate risk evaluation also uses its own rule/model logic.

### Q17
VI Question: Muc dich cua rule-based heart rate tier la gi?  
VI Answer: Day la lop phan ung nhanh, xep muc nguy co theo nguong BPM de sinh canh bao ngay ca khi model ML chua du dieu kien.

EN Question: What is the purpose of the rule-based heart-rate tier?  
EN Answer: It is a fast-response safety layer that classifies risk by BPM thresholds, even when ML confidence or context is limited.

### Q18
VI Question: Muc dich cua anomaly detection (Isolation Forest) la gi?  
VI Answer: Muc dich la phat hien mau du lieu bat thuong khong can nhan truoc, bo sung cho rule-based de giam bo sot tinh huong la.

EN Question: Why use Isolation Forest anomaly detection?  
EN Answer: It detects unusual patterns without labeled anomalies and complements rule-based logic to reduce missed abnormal situations.

### Q19
VI Question: Tai sao can HRV thay vi chi xem BPM?  
VI Answer: BPM chi la gia tri tuc thoi. HRV phan anh bien thien nhip tim theo cua so thoi gian, huu ich cho danh gia trang thai tim mach tong quan.

EN Question: Why use HRV instead of only BPM?  
EN Answer: BPM is an instantaneous value, while HRV captures heart-rate variability over time and provides richer cardiovascular context.

### Q20
VI Question: Co so y hoc cua nguong canh bao la gi?  
VI Answer: Nguong duoc dat theo huong an toan cho monitoring tai nha, ket hop tham khao chuyen mon va practical tuning trong boi canh demo/deployment.

EN Question: What is the medical basis for alert thresholds?  
EN Answer: Thresholds are set conservatively for home monitoring, combining domain references with practical tuning for demo/deployment context.

### Q21
VI Question: Du lieu train anomaly model den tu dau?  
VI Answer: Hien tai chu yeu tu bo synthetic data cho huan luyen va danh gia ky thuat. Day la han che da duoc neu ro trong tai lieu.

EN Question: Where does anomaly training data come from?  
EN Answer: At this stage, training/evaluation mainly uses synthetic data. This limitation is explicitly documented in the project notes.

### Q22
VI Question: Chi so danh gia model bao gom gi?  
VI Answer: Co su dung confusion matrix va cac chi so nhu recall, precision de danh gia kha nang phat hien bat thuong va muc false alarm.

EN Question: Which metrics are used to evaluate the model?  
EN Answer: The project uses confusion matrix-based metrics such as recall and precision to evaluate anomaly detection and false-alarm behavior.

---

## Section F - Security and Reliability

### Q23
VI Question: He thong xac thuc nguoi dung nhu the nao?  
VI Answer: Backend dung token-based authentication va phan quyen theo user context de bao ve API.

EN Question: How does user authentication work?  
EN Answer: The backend uses token-based authentication and user-context authorization to secure API access.

### Q24
VI Question: Lam sao tranh dieu khien nham thiet bi?  
VI Answer: Alfred ap dung co che pending confirmation. Cac tu xac nhan mo ho bi han che; can cum tu ro nghia nhu confirm/proceed/deploy action.

EN Question: How do you prevent accidental device control?  
EN Answer: Alfred uses a pending-confirmation mechanism. Ambiguous confirmations are restricted; explicit confirmations like confirm or proceed are required.

### Q25
VI Question: Co ma hoa ket noi khong?  
VI Answer: Co the trien khai TLS cho MQTT va HTTPS cho API trong moi truong production. Trong demo local co the dung plain mode de de phat trien.

EN Question: Is communication encrypted?  
EN Answer: MQTT over TLS and HTTPS can be enabled for production. Local demo setups may use plain mode for development simplicity.

### Q26
VI Question: Neu backend dung thi sao?  
VI Answer: Du lieu realtime se gian doan tam thoi, nhung du lieu da luu van con trong DB. Co the nang cap high availability bang container orchestration va health checks.

EN Question: What if the backend service goes down?  
EN Answer: Real-time features are temporarily interrupted, but persisted data remains in the database. High availability can be improved with orchestration and health checks.

---

## Section G - Testing and Validation

### Q27
VI Question: Ban da kiem thu nhu the nao?  
VI Answer: Kiem thu gom unit test, integration test, va scenario test cho language lock, control flow, alert generation, va API behavior.

EN Question: How did you test the system?  
EN Answer: Testing includes unit, integration, and scenario-based tests for language lock, control flow, alert generation, and API behavior.

### Q28
VI Question: Ket qua test language lock ra sao?  
VI Answer: Cac kich ban VI/EN dat ket qua pass trong bo test da bao cao, cho thay co che khoa ngon ngu hoat dong on dinh.

EN Question: What were the language-lock test results?  
EN Answer: Reported VI/EN scenarios passed in the test suite, indicating stable language-lock behavior.

### Q29
VI Question: Lam sao ban do chinh xac cua canh bao?  
VI Answer: Do chinh xac duoc danh gia bang confusion matrix tren tap test va theo doi false positives trong cac kich ban mo phong.

EN Question: How do you validate alert accuracy?  
EN Answer: Accuracy is evaluated using confusion-matrix metrics on test data and by monitoring false positives in simulation scenarios.

---

## Section H - Deployment and Operation

### Q30
VI Question: He thong co the trien khai thuc te khong?  
VI Answer: Co. Kien truc da tach thanh cac thanh phan ro rang, ho tro docker-compose, va co tai lieu deployment cho backend.

EN Question: Can this system be deployed in real settings?  
EN Answer: Yes. The architecture is modular, supports docker-compose, and includes backend deployment documentation.

### Q31
VI Question: He thong co kha nang mo rong khong?  
VI Answer: Co. Co the them thiet bi moi, sensor moi, room moi, va use case moi ma khong can sua toan bo he thong.

EN Question: Is the system scalable?  
EN Answer: Yes. New devices, sensors, rooms, and use cases can be added without redesigning the entire system.

### Q32
VI Question: Co can internet lien tuc khong?  
VI Answer: Tuy theo cau hinh. Trong LAN noi bo van co the hoat dong nhieu chuc nang. Ket noi internet can cho mot so tinh nang cloud/remote.

EN Question: Does it require constant internet access?  
EN Answer: It depends on deployment. Many functions can run on local LAN; internet is mainly needed for cloud/remote features.

---

## Section I - Limitations and Future Work

### Q33
VI Question: Han che lon nhat hien tai la gi?  
VI Answer: Han che lon la du lieu huan luyen anomaly chua day du du lieu benh nhan thuc te dai han, nen can tiep tuc mo rong du lieu thuc nghiem.

EN Question: What is the biggest current limitation?  
EN Answer: The main limitation is limited long-term real patient data for anomaly training; broader real-world datasets are needed.

### Q34
VI Question: Huong phat trien tiep theo la gi?  
VI Answer: Tich hop them wearables, bo sung mo hinh sequence (LSTM/Transformer), ca nhan hoa nguong theo tung benh nhan, va mo rong dashboard cho bac si.

EN Question: What are the next development steps?  
EN Answer: Next steps include more wearable integrations, sequence models (LSTM/Transformer), per-patient threshold personalization, and clinician-focused dashboards.

### Q35
VI Question: Neu duoc tiep tuc 6 thang nua, ban uu tien gi?  
VI Answer: Uu tien thu thap du lieu thuc te co giam sat, giam false alarm, nang cap security production, va danh gia UAT voi nguoi dung that.

EN Question: If you had 6 more months, what would you prioritize?  
EN Answer: I would prioritize supervised real-world data collection, false-alarm reduction, production-grade security hardening, and user acceptance testing.

---

## Section J - Extra Committee Questions (New)

### Q36
VI Question: Tai sao khong dua tat ca xu ly len cloud?  
VI Answer: Vi edge + local processing giup giam do tre, giam phu thuoc internet, va tang tinh rieng tu cho du lieu nhay cam.

EN Question: Why not move all processing to the cloud?  
EN Answer: Edge and local processing reduce latency, lower internet dependency, and improve privacy for sensitive data.

### Q37
VI Question: Lam sao tranh alert fatigue cho nguoi cham soc?  
VI Answer: Co the ap dung gom canh bao theo muc do, cooldown theo thoi gian, va co che hop nhat nhieu su kien lien quan thanh mot canh bao tong hop.

EN Question: How do you avoid alert fatigue for caregivers?  
EN Answer: Use severity tiers, cooldown windows, and event aggregation so related events are merged into a single actionable alert.

### Q38
VI Question: He thong xu ly quyen rieng tu nhu the nao?  
VI Answer: Tach du lieu theo user context, han che quyen truy cap, co the bo sung ma hoa at-rest va audit log day du cho production.

EN Question: How does the system handle privacy?  
EN Answer: It separates data by user context, limits access permissions, and can be extended with at-rest encryption and full audit logging.

### Q39
VI Question: Neu model AI sai thi co nguy hiem khong?  
VI Answer: He thong khong phu thuoc duy nhat vao model. Con co lop rule-based va co che xac nhan lenh de giam rui ro thao tac sai.

EN Question: Is it dangerous if the AI model is wrong?  
EN Answer: Risk is mitigated because decisions are not model-only; rule-based safety layers and confirmation flows are in place.

### Q40
VI Question: Gia tri thuc tien cua de tai doi voi gia dinh la gi?  
VI Answer: Gia dinh co the theo doi tinh trang nguoi than theo thoi gian thuc, nhan canh bao som, va giam ap luc cham soc hang ngay.

EN Question: What practical value does this project provide to families?  
EN Answer: Families get real-time visibility, earlier alerts, and reduced daily caregiving pressure through proactive monitoring.

### Q41
VI Question: Vai tro cua extensions, gateways, presentation, va usecases la gi?  
VI Answer: extensions la noi khoi tao framework va service ben ngoai nhu MQTT hay limiter; presentation la API/HTTP layer nhan request va tra response; usecases chua nghiep vu chinh; gateways la adapter di ra ngoai nhu email, MQTT publish, socket emit. Kien truc nay giup tach logic nghiep vu khoi framework.

EN Question: What are the roles of extensions, gateways, presentation, and use cases?  
EN Answer: extensions initialize framework-level services such as MQTT or rate limiting; presentation is the HTTP/API layer that handles requests and responses; use cases contain the main business logic; gateways are outbound adapters such as email, MQTT publishing, and socket emitting. This structure keeps business rules separate from the framework.

### Q42
VI Question: File extensions/mqtt.py co tac dung gi va vi sao dung connect_async()?  
VI Answer: File nay khoi tao Flask-MQTT theo kieu khong block. Thay vi goi connect() dong bo, no tam thay client.connect bang connect_async() de app van start du broker EMQX chua san sang. loop_start() giup client tu retry trong nen.

EN Question: What does extensions/mqtt.py do and why does it use connect_async()?  
EN Answer: This file initializes Flask-MQTT in a non-blocking way. Instead of calling synchronous connect(), it temporarily replaces client.connect with connect_async() so the app can still start even when the EMQX broker is not ready. loop_start() lets the client retry in the background.

### Q43
VI Question: Nhac thuoc hoat dong theo luong nao?  
VI Answer: Nguoi dung tao nhac thuoc qua API, usecase kiem tra du lieu va luu vao DB. Sau do scheduler chay moi phut goi dispatch_due_reminders(), loc cac nhac thuoc den gio, gui email va tao alert cho he thong.

EN Question: How does the medicine reminder flow work?  
EN Answer: Users create reminders through the API, the use case validates and stores them in the database, and the scheduler runs every minute to call dispatch_due_reminders(). The use case then finds due reminders, sends email, and creates an alert.

### Q44
VI Question: Lam sao tranh gui nhac thuoc trung lap?  
VI Answer: Usecase kiem tra last_sent_on; neu da gui trong ngay hien tai thi bo qua. Ngoai ra, he thong chi lay cac nhac thuoc nam trong cua so ±1 phut de giam nguy co bi lech thoi gian.

EN Question: How do you avoid duplicate medicine reminders?  
EN Answer: The use case checks last_sent_on and skips reminders that were already sent on the current day. The scheduler also uses a ±1 minute time window to reduce misses caused by small timing drift.

### Q45
VI Question: Tai sao scheduler nhac thuoc chay moi 1 phut?  
VI Answer: Vi nhac thuoc can do chinh xac theo phut va khong can qua nang. Chu ky 1 phut la can bang giua do chinh xac, do don gian, va tai he thong.

EN Question: Why does the medicine reminder scheduler run every minute?  
EN Answer: Medicine reminders need minute-level accuracy without being too heavy. A one-minute interval is a practical balance between precision, simplicity, and system load.

### Q46
VI Question: Email notifier dong vai tro gi trong kien truc nay?  
VI Answer: Day la gateway dau ra cho nhac thuoc va canh bao. No tach logic gui email khoi usecase, tu dong loc va loai trung nguoi nhan, ho tro SMTP hoac Brevo, va tra ket qua de usecase ghi log/tao alert.

EN Question: What role does the email notifier play in this architecture?  
EN Answer: It is an outbound gateway for reminders and alerts. It keeps email delivery separate from the use case, resolves and deduplicates recipients, supports SMTP or Brevo, and returns a result so the use case can log or create alerts.

### Q47
VI Question: Tai sao domain va usecase duoc viet bang Python thuong, khong phu thuoc framework?  
VI Answer: De nghiep vu khong bi phu thuoc Flask, SQLAlchemy hay MQTT. Cach nay giup code de test hon, de mock hon, va de thay dong gateway ma khong phai sua logic chinh.

EN Question: Why are the domain and use case layers written as plain Python without framework dependencies?  
EN Answer: To keep business rules independent from Flask, SQLAlchemy, and MQTT. This makes the code easier to test, easier to mock, and easier to keep stable when gateways change.

---

## Quick Response Tips (for oral defense)

- If committee asks in Vietnamese: answer Vietnamese first, then add one short English summary sentence.  
- If committee asks in English: answer English directly first, then add one short Vietnamese summary sentence if needed.  
- Keep each oral answer in 20-40 seconds, then offer deeper details on request.
