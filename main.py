import json
import os

from core.matching import (
    precompute_investor_embeddings,
    hard_filter,
    semantic_match,
    reason_generate,
    email_generate,
    convert_match,
)
from core.pdf_extract import process_pitchdeck, extract_startup_with_gemini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INVESTORS_PATH = os.path.join(BASE_DIR, "data", "input", "investors_data.json")
STARTUP_OUTPUT_PATH = os.path.join(BASE_DIR, "data", "output", "startup_data.json")
MATCH_RESULTS_PATH = os.path.join(BASE_DIR, "data", "output", "match_results.json")
TOP_N_MATCHES = 10  # Giới hạn số match tối đa để sinh email, tránh quá tải
MIN_MATCH_SCORE = 0.5
def load_all_counterparts():
    investors = json.load(open(INVESTORS_PATH, encoding="utf-8"))
    corporates = json.load(open(os.path.join(BASE_DIR, "data", "input", "corporates_data.json"), encoding="utf-8"))
    universities = json.load(open(os.path.join(BASE_DIR, "data", "input", "universities_data.json"), encoding="utf-8"))
    research_institutions = json.load(open(os.path.join(BASE_DIR, "data", "input", "research_institutions_data.json"), encoding="utf-8"))

    for inv in investors:
        inv.setdefault("counterpart_type", "investor")

    return investors + corporates + universities + research_institutions


def run(pdf_input_path: str):
    if not os.path.exists(pdf_input_path):
        print(f"[!] Không tìm thấy file PDF tại {pdf_input_path}. Hãy kiểm tra lại.")
        return

    raw_text = process_pitchdeck(pdf_input_path)
    if not raw_text:
        print("[!] Không đọc được nội dung PDF.")
        return

    startup = extract_startup_with_gemini(raw_text)
    if not startup:
        print("[!] Gemini không trích xuất được dữ liệu startup.")
        return

    os.makedirs(os.path.dirname(STARTUP_OUTPUT_PATH), exist_ok=True)
    with open(STARTUP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump([startup], f, ensure_ascii=False, indent=4)
    print("[*] Đã lưu dữ liệu startup trích xuất.")

    counterparts = load_all_counterparts()
    investor_embeddings = precompute_investor_embeddings(counterparts)
    filtered = hard_filter(startup, counterparts)
    matches = semantic_match(startup, filtered, investor_embeddings)
    qualified = [m for m in matches if m["score"] >= MIN_MATCH_SCORE]
    matches = qualified[:TOP_N_MATCHES]
    results = []
    for match in matches:
        match_data = convert_match(match, startup, reason_generate)
        match_data["email"] = email_generate(
            match_data["startup"],
            match_data["investor"],
            match_data["match_score"],
            match_data["match_reason"],
        )
        results.append(match_data)

    with open(MATCH_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"[*] Hoàn tất. Đã ghi {len(results)} kết quả match vào {MATCH_RESULTS_PATH}")


if __name__ == "__main__":
    pdf_input_path = input("Nhập hoặc kéo thả đường dẫn file PDF vào đây: ").strip().strip('"').strip("'")
    run(pdf_input_path)
