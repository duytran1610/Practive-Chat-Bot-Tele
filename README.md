# Telegram Meal Bot

Bot Telegram hỗ trợ báo cơm theo tuần, lưu dữ liệu trên MongoDB và xử lý tác vụ bất đồng bộ bằng `task_queue` + `worker pool`.

## Mục lục

- [Tổng quan](#tổng-quan)
- [Kiến trúc chính](#kiến-trúc-chính)
- [Từng Bước Khởi Tạo Bot](#từng-bước-khởi-tạo-bot)
- [Kết Nối MongoDB](#kết-nối-mongodb)
- [Cơ Chế Task Queue](#cơ-chế-task-queue)
- [Luồng Xử Lý Một Yêu Cầu](#luồng-xử-lý-một-yêu-cầu)
- [Cấu Trúc Thư Mục](#cấu-trúc-thư-mục)
- [Các Lệnh Telegram](#các-lệnh-telegram)
- [Ghi Chú Vận Hành](#ghi-chú-vận-hành)

## Tổng quan

Project này giải quyết 3 vấn đề chính:

- Tách phần nhận tin nhắn Telegram khỏi phần xử lý nghiệp vụ để bot phản hồi nhanh.
- Gom toàn bộ thao tác cập nhật/xem báo cơm vào worker threads thay vì xử lý nặng ngay trong handler.
- Quản lý dữ liệu báo cơm theo tuần hiện tại, kèm các rule về hạn chót đăng ký.

Stack hiện tại:

- Python 3
- `pyTelegramBotAPI` cho Telegram bot
- MongoDB cho lưu trữ dữ liệu
- `queue.Queue` + `threading` cho hàng đợi tác vụ và worker pool

## Kiến trúc chính

Hệ thống được chia thành 4 lớp:

1. `bot/`
   Nhận command/callback từ Telegram, dựng UI và enqueue task.
2. `task_queue/`
   Quản lý model task, queue runtime, registry và worker pool.
3. `tasks/`
   Chứa business handlers chạy trong worker thread.
4. `db/`
   Quản lý kết nối MongoDB, repository và rule nghiệp vụ báo cơm.

Sơ đồ tổng quát:

```mermaid
flowchart LR
    U[Telegram User] --> B[TeleBot Handlers]
    B --> Q[TaskQueue]
    Q --> W[WorkerPool]
    W --> H[Task Handlers]
    H --> R[MealRepository]
    R --> M[(MongoDB)]
    H --> B2[TeleBot send_message/edit_message]
    B2 --> U
```

## Từng Bước Khởi Tạo Bot

Luồng khởi động chính nằm trong [main.py](/E:/Workspace/Python/BotTele/main.py:19).

### 1. Nạp logging và kiểm tra cấu hình

- Gọi `setup_logging()`
- Gọi `settings.validate()`
- Kiểm tra các biến bắt buộc như:
  - `BOT_TOKEN`
  - `MONGO_URI`
  - `MONGO_DB_NAME`

### 2. Ping MongoDB trước khi chạy

- Gọi `db_ping()`
- Nếu MongoDB không kết nối được, tiến trình dừng ngay bằng `sys.exit(1)`

Mục đích:

- Fail fast
- Tránh để bot chạy polling khi backend dữ liệu chưa sẵn sàng

### 3. Tạo `TaskQueue`

- Tạo instance `TaskQueue(maxsize=settings.QUEUE_MAX_SIZE)`
- Đây là hàng đợi trung tâm nhận tất cả task từ Telegram handlers

### 4. Tạo `TeleBot`

- Gọi `build_bot(task_queue)` trong [bot/dispatcher.py](/E:/Workspace/Python/BotTele/bot/dispatcher.py:42)
- Bên trong bước này:
  - tạo `telebot.TeleBot`
  - bind các handler với `task_queue`
  - đăng ký command list để Telegram gợi ý khi user gõ `/`
  - đăng ký callback handler cho các inline button liên quan đến báo cơm

### 5. Tạo `WorkerPool`

- Tạo `WorkerPool(task_queue, bot, num_workers=settings.NUM_WORKERS)`
- Worker pool dùng chung:
  - cùng hàng đợi
  - cùng `TeleBot` instance
  - nhiều thread xử lý song song

### 6. Đăng ký graceful shutdown

- `SIGINT`
- `SIGTERM`

Khi có tín hiệu dừng:

- `bot.stop_polling()`
- `worker_pool.stop(drain_timeout=30.0)`
- `db_close()`
- thoát tiến trình

### 7. Start worker rồi mới polling

- Gọi `worker_pool.start()`
- Sau đó gọi `bot.infinity_polling(...)`

Thứ tự này quan trọng vì:

- Bot bắt đầu nhận request chỉ khi worker đã sẵn sàng tiêu thụ task

## Kết Nối MongoDB

Phần kết nối database nằm trong [db/connection.py](/E:/Workspace/Python/BotTele/db/connection.py:25).

### 1. Cấu hình trong `.env`

Bot đọc cấu hình MongoDB từ các biến môi trường:

- `MONGO_URI`
- `MONGO_DB_NAME`

Ví dụ với MongoDB Atlas:

```env
MONGO_URI="mongodb+srv://user-for-bot:user-for-bot1@clusterbot.swiyvqw.mongodb.net/"
MONGO_DB_NAME="meal_bot"
```

Nếu dùng MongoDB local:

```env
MONGO_URI="mongodb://localhost:27017"
MONGO_DB_NAME="meal_bot"
```

### 2. Cách app tạo kết nối

Luồng kết nối hiện tại:

1. `config.py` nạp `.env` bằng `load_dotenv()`
2. `settings.MONGO_URI` và `settings.MONGO_DB_NAME` được đưa vào `Settings`
3. `db/connection.py` gọi `MongoClient(settings.MONGO_URI, ...)`
4. `get_db()` trả về database theo tên `settings.MONGO_DB_NAME`

Các hàm chính:

- `get_client()`: tạo MongoDB client dạng singleton bằng `lru_cache`
- `get_db()`: trả về database đang dùng
- `ping()`: kiểm tra khả năng kết nối bằng lệnh `admin.command("ping")`
- `close()`: đóng connection pool khi shutdown

### 3. `db_ping()` được gọi ở đâu

Bot không chờ đến lúc xử lý task mới thử kết nối database.

Ngay trong bước khởi động ở [main.py](/E:/Workspace/Python/BotTele/main.py:30), app gọi:

```python
if not db_ping():
    logger.error("Cannot connect to MongoDB. Check MONGO_URI in .env")
    sys.exit(1)
```

Ý nghĩa:

- kiểm tra DB trước khi bot bắt đầu polling
- tránh chạy bot khi MongoDB chưa sẵn sàng
- giúp phát hiện lỗi cấu hình sớm

### 4. Database được dùng ở đâu

Sau khi kết nối thành công:

- `MealRepository` trong [db/meal_repository.py](/E:/Workspace/Python/BotTele/db/meal_repository.py:33) dùng `get_db()` để lấy collection `meal_reports`
- toàn bộ thao tác đọc/ghi MongoDB đều đi qua repository này

### 5. Log kết nối

App có log MongoDB khi khởi động, nhưng URI trong log đã được che mật khẩu bằng `settings.safe_mongo_uri`.

Ví dụ log:

```text
MongoDB : mongodb+srv://user-for-bot:***@clusterbot.swiyvqw.mongodb.net/ / meal_bot
```

### 6. Lưu ý khi đổi môi trường

Khi chuyển giữa local MongoDB và MongoDB Atlas:

- chỉ cần đổi `MONGO_URI`
- giữ nguyên `MONGO_DB_NAME` nếu muốn dùng cùng tên database
- restart bot để nạp lại cấu hình mới

## Cơ Chế Task Queue

### 1. `Task` là gì

Model task nằm tại [task_queue/models.py](/E:/Workspace/Python/BotTele/task_queue/models.py:36).

Một task gồm:

- `task_type`: loại tác vụ
- `chat_id`: chat cần phản hồi
- `payload`: dữ liệu nghiệp vụ
- `max_retries`: số lần retry tối đa
- `task_id`: UUID duy nhất
- `retry_count`: số lần đã retry
- `created_at`: thời điểm tạo
- `status`: trạng thái runtime

Các trạng thái:

- `pending`
- `processing`
- `success`
- `failed`
- `dead`

### 2. `TaskQueue` làm gì

Code nằm tại [task_queue/producer.py](/E:/Workspace/Python/BotTele/task_queue/producer.py:16).

Chức năng:

- bọc `queue.Queue` của stdlib
- thread-safe
- nhận task bằng `enqueue()`
- lấy task bằng `dequeue()`
- theo dõi số liệu runtime qua `stats`

`TaskQueue.stats` hiện trả về:

- `current_size`
- `max_size`
- `enqueued_total`
- `dropped_total`

### 3. Registry map `TaskType -> handler`

Code nằm tại [task_queue/registry.py](/E:/Workspace/Python/BotTele/task_queue/registry.py:19).

Mục đích:

- tách việc định nghĩa loại task khỏi logic xử lý
- worker chỉ cần gọi `get_handler(task.task_type)`

Các task đang dùng:

- `SLOW_TASK`
- `MEAL_REGISTER`
- `MEAL_DAY`
- `MEAL_ALL`
- `MEAL_VIEW`
- `MEAL_SUMMARY`
- `MEAL_STAFF`

### 4. `WorkerPool` xử lý task như thế nào

Code nằm tại [task_queue/worker.py](/E:/Workspace/Python/BotTele/task_queue/worker.py:104).

Mỗi worker thread chạy vòng lặp:

1. `dequeue()` lấy task từ queue
2. đổi trạng thái task sang `PROCESSING`
3. lấy handler tương ứng từ registry
4. chạy handler
5. nếu thành công:
   - đổi trạng thái sang `SUCCESS`
6. nếu lỗi:
   - log lỗi
   - retry theo exponential backoff
7. nếu hết retry:
   - mark `DEAD`
   - gửi cảnh báo cho admin nếu có `ADMIN_CHAT_ID`
   - gửi thông báo thất bại cho user
8. luôn gọi `task_done()`

### 5. Retry hoạt động ra sao

Trong [task_queue/worker.py](/E:/Workspace/Python/BotTele/task_queue/worker.py:56):

- delay retry = `RETRY_BASE_DELAY * 2^(retry_count - 1)`
- nếu queue đầy ngay lúc retry:
  - task bị mark `DEAD`

Ví dụ với `RETRY_BASE_DELAY = 2.0`:

- retry 1: `2s`
- retry 2: `4s`
- retry 3: `8s`

## Luồng Xử Lý Một Yêu Cầu

Ví dụ user bấm báo cơm cho một ngày:

```mermaid
sequenceDiagram
    participant U as User
    participant B as Telegram Handler
    participant Q as TaskQueue
    participant W as Worker
    participant H as Meal Task Handler
    participant R as MealRepository
    participant DB as MongoDB

    U->>B: Bấm nút /baocom hoặc callback
    B->>Q: enqueue(Task)
    Q-->>B: accepted
    W->>Q: dequeue()
    W->>H: handler(task, bot)
    H->>R: set_meal / set_day / set_all
    R->>DB: find_one_and_update / find / insert
    DB-->>R: document
    R-->>H: kết quả
    H-->>U: send_message / edit_message_text
```

### Trong lớp `bot/`

- Handler chỉ làm việc nhẹ:
  - parse command/callback
  - tạo `Task`
  - enqueue
  - phản hồi tức thời hoặc đổi UI

### Trong lớp `tasks/`

- Handler worker mới làm nghiệp vụ:
  - đọc `payload`
  - gọi repository
  - bắt lỗi nghiệp vụ
  - gửi kết quả về Telegram

### Trong lớp `db/`

- `MealRepository` gom toàn bộ truy vấn MongoDB
- `meal_rules.py` kiểm tra các rule:
  - chỉ trong tuần hiện tại
  - hạn chót trước `16:00` ngày hôm trước

## Cấu Trúc Thư Mục

```text
BotTele/
├─ main.py
├─ config.py
├─ README.md
├─ bot/
│  ├─ __init__.py
│  ├─ dispatcher.py
│  ├─ handlers.py
│  └─ meal_handlers.py
├─ db/
│  ├─ __init__.py
│  ├─ connection.py
│  ├─ meal_repository.py
│  ├─ meal_rules.py
│  └─ models.py
├─ task_queue/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ producer.py
│  ├─ registry.py
│  └─ worker.py
├─ tasks/
│  ├─ __init__.py
│  ├─ handlers.py
│  └─ meal_handlers.py
└─ tests/
```

## Các Lệnh Telegram

Bot hiện hỗ trợ các lệnh chính:

- `/start`: mở menu chính
- `/baocom`: mở giao diện báo cơm
- `/xemcua`: xem báo cơm tuần hiện tại của bạn
- `/dangky`: đăng ký tất cả ngày còn mở
- `/huydangky`: hủy tất cả ngày còn mở
- `/danhsach`: xem danh sách đã báo cơm
- `/tonghop`: tổng hợp tuần, chỉ dành cho admin
- `/status`: xem thống kê queue runtime
- `/slow [seconds]`: task mô phỏng chậm để kiểm tra worker queue

## Ghi Chú Vận Hành

### Cấu hình quan trọng

Các biến môi trường trong `.env`:

- `BOT_TOKEN`
- `MONGO_URI`
- `MONGO_DB_NAME`
- `NUM_WORKERS`
- `QUEUE_MAX_SIZE`
- `MAX_RETRIES`
- `RETRY_BASE_DELAY`
- `MEAL_REGISTRATION_CUTOFF_HOUR`
- `ADMIN_CHAT_ID`

### Khi cần debug queue

- dùng `/status` để xem queue hiện tại
- xem log:
  - `ENQUEUED`
  - `PROCESSING`
  - `SUCCESS`
  - `FAILED`
  - `RETRY`
  - `DEAD`

### Khi thay đổi command list

Nếu sửa danh sách command trong bot:

- restart bot để Telegram cập nhật gợi ý khi gõ `/`

### Khi thêm task mới

Để thêm 1 task mới, cần đi qua đủ các bước:

1. thêm `TaskType` mới trong `task_queue/models.py`
2. viết handler mới trong `tasks/`
3. đăng ký vào `task_queue/registry.py`
4. tạo command/callback trong `bot/`
5. nếu có dữ liệu, tích hợp repository trong `db/`
