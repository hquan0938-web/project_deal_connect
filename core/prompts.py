# prompts.py

def get_email_prompt(startup, counterpart, match_score, match_reason):
    cp_type = counterpart.get("counterpart_type", "investor")
    role_label = {
        "investor": "quỹ đầu tư",
        "corporation": "tập đoàn",
        "university": "trường đại học",
        "research_institution": "viện nghiên cứu",
    }.get(cp_type, "đối tác")

    goal_label = {
        "investor": "xin một cuộc hẹn gọi vốn 15 phút",
        "corporation": "đề xuất một buổi trao đổi hợp tác chiến lược",
        "university": "đề xuất một buổi trao đổi hợp tác nghiên cứu/thử nghiệm sản phẩm",
        "research_institution": "đề xuất một buổi trao đổi về chuyển giao công nghệ",
    }.get(cp_type, "một cuộc gặp trao đổi")

    thesis_label = {
        "investor": "Luận điểm đầu tư",
        "corporation": "Định hướng hợp tác chiến lược",
        "university": "Định hướng hợp tác nghiên cứu",
        "research_institution": "Định hướng chuyển giao công nghệ",
    }.get(cp_type, "Định hướng hợp tác")

    startup_name = startup.get("name", "[Tên Startup]")
    startup_industry = startup.get("industry", "[Lĩnh vực]")
    counterpart_name = counterpart.get("name", "[Tên Đối tác]")

    return f"""
    Bạn là một trợ lý AI chuyên nghiệp hỗ trợ kết nối khởi nghiệp (Startup) với các đối tác tiềm năng (quỹ đầu tư, tập đoàn, trường đại học, viện nghiên cứu).
    Hãy đóng vai Founder của startup {startup_name} và viết một email giới thiệu (cold email) gửi tới {role_label} {counterpart_name}.

    Dưới đây là các thông tin dữ liệu để viết email:

    **1. Thông tin Hồ sơ Startup (Người gửi):**
    - Tên Startup: {startup_name}
    - Ngành/Lĩnh vực: {startup_industry}

    **2. Thông tin Đối tác (Người nhận):**
    - Tên: {counterpart_name}
    - Loại đối tác: {role_label}

    **3. Phân tích độ phù hợp (AI Match):**
    - Điểm tương thích: {match_score}
    - Cơ sở đánh giá (Lý do match): {match_reason}

    **Yêu cầu viết:**
    - Tiêu đề email (Subject) thật hấp dẫn và đi thẳng vào vấn đề.
    - Giọng văn lịch sự, tự tin, súc tích (khoảng 150 - 250 từ).
    - Phải nhấn mạnh được sự tương đồng giữa "{thesis_label}" của {role_label} và "Giải pháp" của startup.
    - Đưa ra Call-to-action (CTA) rõ ràng ở cuối email: {goal_label}.
      **Định dạng đầu ra (BẮT BUỘC):**
    - CHỈ trả về đúng nội dung email (bắt đầu bằng dòng "Tiêu đề: ..." rồi tới phần thân thư).
    - TUYỆT ĐỐI KHÔNG thêm lời dẫn/lời chào trước email (VD: "Chào bạn, đây là bản thảo...").
    - TUYỆT ĐỐI KHÔNG thêm ghi chú, gợi ý, hoặc phần "lưu ý" sau email.
    - KHÔNG dùng markdown (không in đậm **, không dùng ###, không dùng gạch đầu dòng ở phần thân thư).
    
    """
def get_match_reason_prompt(startup: dict, investor: dict) -> str:
    
    startup_name = startup.get("name", "[Tên Startup]")
    investor_name = investor.get("name", "[Tên Quỹ]")
    technology_score = startup.get("technology", 0)
    problem_score = startup.get("problem", 0)
    thesis_score = startup.get("investment_thesis", 0)
    customer_score = startup.get("customers", 0)
    return f"""Bạn là một chuyên gia phân tích đầu tư lõi lõi tại Trung tâm Đổi mới sáng tạo Quốc gia (NIC).
Nhiệm vụ của bạn là viết MỘT đoạn văn ngắn gọn (khoảng 3-4 câu, dưới 80 từ) giải thích lý do tại sao Startup và Quỹ đầu tư này lại phù hợp với nhau.

THÔNG TIN ĐẦU VÀO:
- Tên Startup: {startup_name}
- Tên Quỹ đầu tư: {investor_name}

ĐIỂM ĐÁNH GIÁ ĐỘ KHỚP THEO TIÊU CHÍ (0.0 đến 1.0):
- Công nghệ (Technology Focus): {technology_score}
- Vấn đề giải quyết (Problem Focus): {problem_score}
- Khẩu vị đầu tư (Investment Thesis): {thesis_score}
- Tệp khách hàng (Customer Focus): {customer_score}

YÊU CẦU BẮT BUỘC (RULE-BASED):
1. Phân tích trọng tâm: Tìm tiêu chí có điểm số cao nhất trong 4 tiêu chí trên và lấy đó làm luận điểm chính để giải thích sự phù hợp.
2. Logic & Chuyên nghiệp: Giọng văn mang tính phân tích sắc bén, thuyết phục, dùng từ ngữ chuyên ngành đầu tư khởi nghiệp.
3. Chống ảo giác (No Hallucination): Ttuyệt đối KHÔNG bịa đặt thêm số liệu tài chính hay thông tin không có trong đầu vào.
4. Định dạng đầu ra: Trả về TRỰC TIẾP đoạn văn phân tích, KHÔNG có lời chào, KHÔNG có tiêu đề, KHÔNG giải thích lôi thôi.
"""
# Thêm vào cuối file prompts.py

def get_time_extraction_prompt(reply_text: str) -> str:
    """
    Prompt dành cho AI Agent bóc tách thời gian chốt lịch từ email phản hồi của Startup.
    """
    return f"""
    Bạn là một AI Agent chuyên phân tích dữ liệu lịch trình.
    Một Startup vừa phản hồi lại email để chốt lịch họp với quỹ đầu tư. Hãy đọc nội dung email phản hồi dưới đây và trích xuất ra thời gian bắt đầu và kết thúc (mặc định cuộc họp kéo dài 1 tiếng).
    
    Lưu ý: 
    - Năm hiện tại là 2026. 
    - Múi giờ là Giờ Việt Nam (+07:00).
    
    Nội dung email phản hồi (Email Response):
    "{reply_text}"
    
    BẮT BUỘC trả về CHỈ một chuỗi JSON chuẩn xác, không có thêm ký tự markdown (như ```json), theo đúng định dạng sau:
    {{
        "start_time_iso": "YYYY-MM-DDTHH:MM:00+07:00",
        "end_time_iso": "YYYY-MM-DDTHH:MM:00+07:00"
    }}
    """

# def get_mock_startup_reply_prompt(start_time_str: str, end_time_str: str, date_str: str) -> str:
#     """
#     (Tùy chọn) Prompt để AI tự động đóng vai Startup viết email phản hồi một cách tự nhiên.
#     """
#     return f"""
#     Bạn đang đóng vai là Founder của một Startup. Quỹ đầu tư NIC vừa gửi email ngỏ ý muốn họp với bạn.
#     Bạn đã xem lịch và quyết định chọn khung giờ: Từ {start_time_str} đến {end_time_str}, ngày {date_str}.
    
#     Hãy viết MỘT CÂU phản hồi email ngắn gọn, lịch sự, tự nhiên để xác nhận lịch họp này với quỹ NIC. 
#     Chỉ viết nội dung câu trả lời, không cần chủ đề (Subject) hay các định dạng thư từ rườm rà.
#     """


def get_judge_prompt(startup: dict, investor: dict) -> str:
    """
    Prompt cho LLM-as-judge: chấm điểm 1-5 độ phù hợp giữa startup và investor,
    dùng để bootstrap nhãn training cho scoring_model (thay cho nhãn người tự chấm tay).

    Lưu ý: đây là nhãn TẠM, có nhiễu — không dùng thay thế hoàn toàn cho nhãn thật/outcome thật.
    """
    startup_name = startup.get("name", "[Không rõ tên]")
    investor_name = investor.get("name", "[Không rõ tên]")
    return f"""Bạn là một chuyên gia thẩm định đầu tư (investment analyst) độc lập, có nhiệm vụ CHẤM ĐIỂM khách quan độ phù hợp giữa một startup và một quỹ đầu tư, dựa THUẦN TÚY trên dữ liệu được cung cấp dưới đây.

HỒ SƠ STARTUP:
- Tên: {startup_name}
- Ngành: {startup.get("industry", "N/A")}
- Giai đoạn: {startup.get("stage", "N/A")}
- Công nghệ: {startup.get("technology", "N/A")}
- Vấn đề giải quyết: {startup.get("problem", "N/A")}
- Giải pháp: {startup.get("solution", "N/A")}
- Khách hàng mục tiêu: {startup.get("customers", "N/A")}

HỒ SƠ QUỸ ĐẦU TƯ:
- Tên: {investor_name}
- Ngành ưu tiên: {investor.get("target_industries", "N/A")}
- Giai đoạn ưu tiên: {investor.get("target_stages", "N/A")}
- Trọng tâm công nghệ: {investor.get("technology_focus", "N/A")}
- Trọng tâm vấn đề: {investor.get("problem_focus", "N/A")}
- Luận điểm đầu tư: {investor.get("investment_thesis", "N/A")}
- Trọng tâm khách hàng: {investor.get("customer_focus", "N/A")}

QUY TẮC CHẤM ĐIỂM:
1. Chấm điểm từ 1 đến 5, trong đó: 1 = hoàn toàn không phù hợp, 3 = phù hợp một phần, 5 = phù hợp rất cao.
2. CHỈ dựa vào dữ liệu ở trên. TUYỆT ĐỐI KHÔNG suy đoán hay bịa thêm thông tin không có trong hồ sơ.
3. Nếu một hồ sơ thiếu thông tin (N/A) ở tiêu chí nào, không tự suy diễn tốt/xấu cho tiêu chí đó.
4. Đưa ra lý do ngắn gọn (1 câu) giải thích điểm số.

BẮT BUỘC trả về CHỈ một chuỗi JSON, không có markdown, không có chữ nào khác, theo đúng format:
{{
    "score": <số nguyên 1-5>,
    "reason": "<lý do ngắn gọn 1 câu>"
}}
"""