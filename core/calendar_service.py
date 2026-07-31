from datetime import datetime, timedelta
# 1. Dữ liệu cố định: 10 khung giờ RẢNH của NIC (Ví dụ trong 3 ngày)


def find_all_common_free_slots(nic_free, startup_free, duration_minutes=60):
    """
    Tìm TẤT CẢ các khoảng thời gian rảnh chung đủ 1 tiếng.
    """
    if not startup_free:
        common_free_intervals = nic_free
    else:
        # Thuật toán 2 con trỏ tìm giao điểm
        common_free_intervals = []
        i, j = 0, 0
        while i < len(nic_free) and j < len(startup_free):
            start_max = max(nic_free[i][0], startup_free[j][0])
            end_min = min(nic_free[i][1], startup_free[j][1])
            
            if start_max < end_min:
                common_free_intervals.append((start_max, end_min))
            
            if nic_free[i][1] < startup_free[j][1]:
                i += 1
            else:
                j += 1

    # Bóc tách tất cả các slot 1 tiếng
    slots = []
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=30) # Dịch chuyển mỗi 30 phút để tạo nhiều option linh hoạt
    
    for free_start, free_end in common_free_intervals:
        current_time = free_start
        # Bỏ đi điều kiện len(slots) < max_slots để lấy TẤT CẢ
        while current_time + duration <= free_end:
            # Lưu lại cả giờ bắt đầu và giờ kết thúc
            slots.append((current_time, current_time + duration))
            current_time += step 
            
    return slots
def choose_slot(slots):
    """
    In danh sách slot rảnh (đánh số 1->n), cho người dùng nhập số để chọn.
    Dùng chung cho mọi flow đặt lịch (book_meeting.py, select_and_book_meeting.py...).
    Trả về (start, end) đã chọn, hoặc None nếu người dùng huỷ.
    """
    print(f"\n[*] Tìm được {len(slots)} khung giờ rảnh chung:")
    for i, (start, end) in enumerate(slots, start=1):
        print(
            f"    {i}. {start.strftime('%H:%M %d/%m/%Y')} - {end.strftime('%H:%M')}"
        )
 
    while True:
        raw = input(f"\nChọn khung giờ (nhập số 1-{len(slots)}, hoặc 'q' để huỷ): ").strip()
        if raw.lower() == "q":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(slots):
            return slots[int(raw) - 1]
        print(f"[!] Vui lòng nhập số từ 1 đến {len(slots)} (hoặc 'q' để huỷ).")