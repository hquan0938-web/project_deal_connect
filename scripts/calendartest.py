import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import json

from core.calendar_service import find_all_common_free_slots
from core.calendar_api import get_free_intervals
from core.matching import (
    precompute_investor_embeddings,
    hard_filter,
    reason_generate,
    semantic_match,
    convert_match,
    email_generate,
)
from core.pdf_extract import process_pitchdeck, extract_startup_with_gemini

# nic_free_intervals
CALENDAR_ID = "primary"  # đổi thành email calendar cụ thể nếu cần
time_min = datetime.now()
time_max = time_min + timedelta(days=7)
nic_free = get_free_intervals(CALENDAR_ID, time_min, time_max)

#mockdata
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

# Tìm slot 1 tiếng (60 phút)
available_slots = find_all_common_free_slots(nic_free, startup_free, duration_minutes=60)

if available_slots:
    formatted_slots = []
    for start_time, end_time in available_slots:
        date_str = start_time.strftime("%d/%m/%Y")
        start_str = start_time.strftime("%H:%M")
        end_str = end_time.strftime("%H:%M")
        formatted_slots.append(f"- {start_str} - {end_str}, Ngày {date_str} (Giờ VN)")
        
    slots_text = "\n".join(formatted_slots)
    print(f"Tìm thấy {len(available_slots)} khung giờ rảnh chung (1 tiếng/slot):\n{slots_text}")
else:
    print(" Không tìm được khoảng thời gian rảnh chung nào đủ 1 tiếng.")
