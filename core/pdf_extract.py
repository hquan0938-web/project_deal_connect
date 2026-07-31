from google import genai
from config import Config
import pdfplumber
import json
import os
import re
from core.llm_service import _call_gemini, MODEL_ID

# 2. HÀM ĐỌC PDF BẰNG PDFPLUMBER
def process_pitchdeck(pdf_path):
    extracted_text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: extracted_text.append(text)
        return "\n".join(extracted_text)
    except Exception as e:
        print(f"[!] Lỗi đọc PDF: {e}")
        return ""

# 3. HÀM GỌI GEMINI ĐỂ BÓC TÁCH JSON TỪ TEXT
def extract_startup_with_gemini(raw_text):

    prompt = f"""
    Bạn là một chuyên gia phân tích quỹ đầu tư mạo hiểm. Hãy đọc nội dung bản Pitch Deck sau và bóc tách thông tin.
    TRẢ VỀ KẾT QUẢ DUY NHẤT DƯỚI DẠNG CHUẨN JSON CHO TỪNG DOANH NGHIỆP KHÔNG GỘP CHUNG CÁC DOANH NGHIỆP (Không giải thích, không dùng markdown code block ```json).
    Trước tiên, xác định loại hồ sơ:
    - Nếu là pitch deck startup (có gọi vốn, giai đoạn đầu tư) -> entity_type = "startup"
    - Nếu là hồ sơ giới thiệu khoa/viện nghiên cứu (không gọi vốn, tập trung nghiên cứu/công bố khoa học) -> entity_type = "university"

    Trả về JSON tương ứng với entity_type đã xác định.
    Cấu trúc JSON bắt buộc:
    {{
        "name": "Tên startup/doanh nghiệp",
        "entity_type": "startup hoặc university",
        "industry": "Lĩnh vực hoạt động chính (VD: EdTech, FinTech, AgriTech...)",
        "stage": "Vòng gọi vốn (VD: Seed, Series A, Pre-Series A...)",
        "funding": "Số tiền gọi vốn (chỉ ghi số, ví dụ: 500000 nếu là 500K USD, hoặc ghi dạng text nếu không tìm thấy)",
        "technology": "Các công nghệ lõi đang sử dụng",
        "problem": "Tóm tắt ngắn gọn vấn đề của thị trường",
        "solution": "Tóm tắt ngắn gọn giải pháp của startup",
        "customers": "Tệp khách hàng mục tiêu",
        "summary": "Tóm tắt dự án trong 1-2 câu"
    }}

    Nội dung Pitch Deck:
    {raw_text}
    """
    
    # response = client.models.generate_content(
    #     model='gemini-flash-latest',
    #     contents=prompt,
    # )
    try:
        raw = _call_gemini(prompt, model=MODEL_ID)
        cleaned_json_text = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_json_text)
    except json.JSONDecodeError:
        print("[!] Lỗi không trả về định dạng JSON chuẩn.")
        return None
    except Exception as e:
        print(f"[!] Lỗi khi gọi Gemini để trích xuất pitch deck: {e}")
        return None