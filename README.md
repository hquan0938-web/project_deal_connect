# DealConnect

DealConnect là hệ thống tự động hoá deal-flow: đọc pitch deck của startup, chấm điểm mức độ phù hợp với các counterpart (nhà đầu tư, tập đoàn, trường đại học, viện nghiên cứu), sinh email tiếp cận cá nhân hoá, và đặt lịch hẹn thật qua Google Calendar với investor được chọn. Dự án khởi đầu từ hackathon, hiện phát triển tiếp như một project cá nhân dài hạn. Hiện tại là ứng dụng **CLI**, chưa có giao diện web.

## Kiến trúc pipeline

```
Pitch deck (PDF)
   │
   ▼
Trích xuất thông tin startup (Gemini 2.5 Flash)
   │
   ▼
Hard filter (funding / ticket size)
   │
   ▼
Semantic matching (sentence-transformers embeddings)
   │
   ▼
Chấm điểm match (Logistic Regression đã train)
   │
   ▼
Sinh lý do match + email tiếp cận (Gemini)
   │
   ▼
data/output/match_results.json
   │
   ▼
Chọn investor phù hợp từ danh sách -> Chọn khung giờ rảnh chung -> Đặt lịch hẹn thật (Google Calendar)
```

Nhánh **đặt lịch hẹn** (OAuth thật với Google Calendar): đọc lịch rảnh của mình (vai trò trung gian/NIC), chọn investor từ kết quả match, tìm khung giờ chung, chọn slot bằng số, tạo sự kiện + mời qua email + tự sinh Google Meet link.

## Cấu trúc thư mục

```
hackathon2026/
├── main.py                          # Entry point: match startup <-> counterpart, sinh email
├── config.py                        # Đọc API key / config từ .env
├── requirements.txt
├── core/
│   ├── pdf_extract.py               # Trích xuất pitch deck qua Gemini
│   ├── matching.py                  # Hard filter, semantic match, sinh reason/email
│   ├── scoring_model.py             # Train & load model Logistic Regression
│   ├── calendar_api.py              # Gọi Google Calendar API thật (freebusy, tạo event)
│   ├── calendar_service.py          # Tìm khung giờ rảnh chung + chọn slot bằng số (dùng chung)
│   ├── llm_service.py / llm_judge.py / llm_logger.py
│   └── prompts.py
├── scripts/
│   ├── calendar_auth_setup.py       # Chạy 1 lần để xác thực OAuth Google Calendar
│   ├── calendartest.py              # Test lấy lịch rảnh thật + tìm slot chung
│   ├── select_and_book_meeting.py   # Chọn investor từ match_results.json -> chọn slot -> đặt lịch
│   ├── bootstrap_labels.py          # Bootstrap nhãn train bằng LLM-as-judge
│   ├── checkmodel.py
│   └── export_emails.py
├── data/
│   ├── input/                       # Dữ liệu counterpart (investors, corporates, universities, ...)
│   ├── models/                      # Model đã train (match_scorer.joblib)
│   ├── training/                    # Nhãn training
│   └── output/                      # Kết quả chạy (match_results.json, tự sinh, không commit)
└── secrets/                         # credentials.json, token.json (KHÔNG commit)
```

## Cài đặt

```bash
git clone <repo-url>
cd hackathon2026
pip install -r requirements.txt
```

Khuyến khích dùng virtual environment (`venv` hoặc `conda`) trước khi cài.

## Cấu hình

### 1. Biến môi trường (`.env`)

Tạo file `.env` ở thư mục gốc project:

```
GEMINI_API_KEY=your_api_key_here
GEMINI_BASE_URL=            # để trống nếu gọi thẳng Google, hoặc điền URL proxy nếu dùng proxy trung gian
```

`GEMINI_API_KEY` là bắt buộc — thiếu sẽ báo lỗi ngay khi chạy.

### 2. Google Calendar API

1. Vào [Google Cloud Console](https://console.cloud.google.com/) → tạo project → bật **Google Calendar API**.
2. Tạo **OAuth Client ID** loại **Desktop app** → tải file JSON → đổi tên thành `credentials.json` → bỏ vào `secrets/credentials.json`.
3. Nếu app đang ở chế độ Testing, vào **OAuth consent screen → Test users** thêm email Google bạn dùng để đăng nhập.
4. Chạy xác thực (chỉ cần 1 lần, sẽ mở trình duyệt để bạn đăng nhập):

```bash
python scripts/calendar_auth_setup.py
```

Sau khi thành công, `secrets/token.json` sẽ được tạo và tự dùng lại cho các lần chạy sau.

## Cách chạy

### 1. Match startup với counterpart + sinh email

```bash
python main.py
```

Nhập đường dẫn file PDF pitch deck khi được hỏi. Kết quả ghi ra `data/output/match_results.json` — danh sách các counterpart phù hợp kèm `match_score` và lý do match.

### 2. Chọn investor + chọn lịch hẹn thật

```bash
python scripts/select_and_book_meeting.py
```

Luồng:
1. Đọc `data/output/match_results.json` (kết quả bước 1).
2. Hiện danh sách investor phù hợp, đánh số `1, 2, 3, ...` kèm match score.
3. Bạn chọn investor muốn đặt lịch.
4. Nhập email liên hệ của investor — **nhấn Enter để dùng email test mặc định** (`DEFAULT_TEST_EMAIL` khai báo đầu file), tiện lúc test không cần gõ tay mỗi lần.
5. Hệ thống liệt kê các khung giờ rảnh chung, bạn chọn bằng số.
6. Tạo sự kiện thật trên Google Calendar + mời qua email + sinh link Google Meet.

> Trước khi dùng thật, nhớ đổi `DEFAULT_TEST_EMAIL` trong `scripts/select_and_book_meeting.py` thành email thật của investor.

> Lưu ý: hiện chỉ đọc lịch rảnh **thật** của người chạy script (vai trò trung gian/NIC) qua OAuth. Lịch rảnh của startup/investor vẫn đang nhập tay trong code (`startup_free` trong `select_and_book_meeting.py`) vì chưa xin được quyền đọc calendar thật của họ.

## Ghi chú kỹ thuật

- Model chấm điểm là **Logistic Regression**, dùng ngưỡng phân loại đã tinh chỉnh (không phải 0.5 mặc định) để tối ưu F1 cho lớp thiểu số, giải quyết vấn đề mất cân bằng dữ liệu. Không retrain nhiều lần để "chọn bản tốt nhất" — nhiễu do weak supervision dễ khiến việc này gây hiểu nhầm là cải thiện thật.
- Nhãn training được bootstrap bằng Gemini đóng vai LLM-as-judge, sau đó dùng để train model nhỏ hơn — độ chính xác báo cáo (`test_accuracy`, `test_auc`) phản ánh mức đồng thuận với LLM judge, không phải nhãn ground-truth thủ công.
- Gemini API gọi qua proxy trung gian (cấu hình qua `GEMINI_BASE_URL`) — lưu ý một số alias model (VD: `gemini-flash-latest`) không resolve được qua proxy, cần dùng ID cụ thể (VD: `gemini-2.5-flash`).
- Dữ liệu counterpart (`investors_data.json`...) hiện **chưa có field email liên hệ** — đây là lý do `select_and_book_meeting.py` phải hỏi nhập tay mỗi lần. Muốn tự động hoá, thêm field `contact_email` vào các file JSON trong `data/input/`.
- Google Calendar API yêu cầu định dạng thời gian chuẩn RFC3339 có offset múi giờ (VD: `+07:00`) — `core/calendar_api.py` tự xử lý việc này qua hàm `_to_rfc3339()`, không cần tự thêm offset thủ công khi gọi.
- Khoảng thời gian lấy lịch rảnh thật (`time_min` → `time_max`) trong `select_and_book_meeting.py` cần đủ rộng để phủ hết khoảng ngày có trong `startup_free` — nếu mở rộng `startup_free` sang xa hơn, nhớ tăng tương ứng số ngày trong `timedelta(days=...)`, nếu không lịch rảnh thật sẽ không phủ tới, khiến các mốc xa không bao giờ được ghép thành slot chung.

## Không commit

`secrets/`, `.env`, `data/output/`, `data/llm_logs.db`, các file cache `.pkl` — xem chi tiết trong `.gitignore`.