import os
import sys
import json
 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from datetime import datetime, timedelta
 
from core.calendar_service import find_all_common_free_slots, choose_slot
from core.calendar_api import get_free_intervals, create_events
 
CALENDAR_ID = "primary"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCH_RESULTS_PATH = os.path.join(BASE_DIR, "data", "output", "match_results.json")

DEFAULT_TEST_EMAIL = "your_test_email@gmail.com"
 
 
def load_matches():
    if not os.path.exists(MATCH_RESULTS_PATH):
        print(f"[!] Không tìm thấy {MATCH_RESULTS_PATH}.")
        print("    Hãy chạy `python main.py` với 1 pitch deck trước để có kết quả match.")
        return []
    with open(MATCH_RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)
 
 
def choose_investor(matches):
    """In danh sách investor phù hợp (đánh số 1->n), cho người dùng chọn."""
    startup_name = matches[0]["startup"]["name"] if matches else "?"
    print(f"\n[*] Danh sách investor phù hợp với '{startup_name}':")
    for i, m in enumerate(matches, start=1):
        print(
            f"    {i}. {m['investor']['name']}  (match score: {m['match_score']})"
        )
 
    while True:
        raw = input(f"\nChọn investor muốn đặt lịch (1-{len(matches)}, hoặc 'q' để huỷ): ").strip()
        if raw.lower() == "q":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(matches):
            return matches[int(raw) - 1]
        print(f"[!] Vui lòng nhập số từ 1 đến {len(matches)} (hoặc 'q' để huỷ).")
 
 
def ask_investor_email(investor_name):
    """
    Dữ liệu investor hiện chưa có field email -> tạm nhập tay mỗi lần đặt lịch.
    Nhấn Enter (để trống) để dùng luôn DEFAULT_TEST_EMAIL, tiện lúc test.
    TODO: nếu muốn tự động hoá, thêm field "contact_email" vào investors_data.json /
    corporates_data.json / universities_data.json / research_institutions_data.json
    rồi đọc thẳng từ đó thay vì hỏi lại mỗi lần.
    """
    while True:
        raw = input(
            f"Nhập email liên hệ của '{investor_name}' "
            f"(Enter để dùng mặc định: {DEFAULT_TEST_EMAIL}): "
        ).strip()
        if raw == "":
            return DEFAULT_TEST_EMAIL
        if "@" in raw and "." in raw:
            return raw
        print("[!] Email không hợp lệ, thử lại.")
 
 
def main():
    matches = load_matches()
    if not matches:
        return
 
    chosen_match = choose_investor(matches)
    if chosen_match is None:
        print("[*] Đã huỷ, không tạo lịch.")
        return
 
    investor_name = chosen_match["investor"]["name"]
    startup_name = chosen_match["startup"]["name"]
    investor_email = ask_investor_email(investor_name)
 
    time_min = datetime.now()
    time_max = time_min + timedelta(days=32)  
 
    print("[*] Đang lấy lịch rảnh thật từ Google Calendar...")
    nic_free = get_free_intervals(CALENDAR_ID, time_min, time_max)
 
    startup_free = [
        (datetime(2026, 8, 3, 14, 0), datetime(2026, 8, 3, 18, 0)),
        (datetime(2026, 8, 5, 8, 0), datetime(2026, 8, 5, 11, 0)),
 
        (datetime(2026, 8, 10, 14, 0), datetime(2026, 8, 10, 18, 0)),
        (datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 11, 0)),
 
        (datetime(2026, 8, 17, 14, 0), datetime(2026, 8, 17, 18, 0)),
        (datetime(2026, 8, 19, 8, 0), datetime(2026, 8, 19, 11, 0)),
 
        (datetime(2026, 8, 24, 14, 0), datetime(2026, 8, 24, 18, 0)),
        (datetime(2026, 8, 26, 8, 0), datetime(2026, 8, 26, 11, 0)),
 
        (datetime(2026, 8, 31, 14, 0), datetime(2026, 8, 31, 18, 0)),
    ]
 
    slots = find_all_common_free_slots(nic_free, startup_free, duration_minutes=60)
 
    if not slots:
        print("[!] Không tìm được khung giờ rảnh chung nào đủ 1 tiếng.")
        return
 
    chosen_slot = choose_slot(slots)
    if chosen_slot is None:
        print("[*] Đã huỷ, không tạo lịch.")
        return
 
    start_time, end_time = chosen_slot
    print(
        f"[*] Đã chọn: {start_time.strftime('%H:%M %d/%m/%Y')} "
        f"- {end_time.strftime('%H:%M')}"
    )
 
    print(f"[*] Đang tạo sự kiện + mời {investor_name} qua Google Calendar...")
    result = create_events(
        summary=f"Buổi trao đổi {startup_name} x {investor_name}",
        start=start_time,
        end=end_time,
        attendee_emails=[investor_email],
        calendar_id=CALENDAR_ID,
        description=(
            f"Lịch hẹn được tạo tự động bởi Deal Connect.\n\n"
            f"Match score: {chosen_match['match_score']}\n"
            f"Lý do match: {chosen_match.get('match_reason', '')}"
        ),
    )
 
    print("[*] Đặt lịch thành công!")
    print(f"    - Link sự kiện: {result['event_link']}")
    print(f"    - Link Google Meet: {result['meet_link']}")
 
 
if __name__ == "__main__":
    main()