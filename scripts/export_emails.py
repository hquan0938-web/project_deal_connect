import glob
import json
import os
import re
import unicodedata

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCH_RESULTS_PATH = os.path.join(BASE_DIR, "data", "output", "match_results.json")
EMAILS_OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output", "emails")


def slugify(text: str) -> str:
    """Chuyển tên có dấu / khoảng trắng thành tên file an toàn, VD: 'Tập đoàn FPT' -> 'Tap_doan_FPT'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip()
    text = re.sub(r"[\s]+", "_", text)
    return text or "unknown"


def export_emails():
    if not os.path.exists(MATCH_RESULTS_PATH):
        print(f"[!] Không tìm thấy {MATCH_RESULTS_PATH}. Hãy chạy 'python main.py' trước để sinh kết quả match.")
        return

    with open(MATCH_RESULTS_PATH, "r", encoding="utf-8") as f:
        matches = json.load(f)

    if not matches:
        print("[!] File match_results.json rỗng, không có email nào để xuất.")
        return

    os.makedirs(EMAILS_OUTPUT_DIR, exist_ok=True)
      # Xoá hết email .txt cũ trước khi ghi mới, tránh sót file thừa từ lần chạy trước
    old_files = glob.glob(os.path.join(EMAILS_OUTPUT_DIR, "*.txt"))
    for old_file in old_files:
        os.remove(old_file)
    # if old_files:
    #     print(f"[*] Đã xoá {len(old_files)} email cũ.")
    n_written = 0
    for i, match in enumerate(matches, start=1):
        email_content = match.get("email")
        if not email_content:
            print(f"  [SKIP] Match #{i} không có nội dung email.")
            continue

        startup_name = match.get("startup", {}).get("name", "Startup")
        investor_name = match.get("investor", {}).get("name", "DoiTac")
        match_score = match.get("match_score", "")

        filename = f"{i:02d}_{slugify(startup_name)}_x_{slugify(investor_name)}.txt"
        filepath = os.path.join(EMAILS_OUTPUT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Startup: {startup_name}\n")
            f.write(f"Đối tác: {investor_name}\n")
            f.write(f"Điểm match: {match_score}\n")
            f.write("=" * 60 + "\n\n")
            f.write(email_content)

        print(f"  [OK] {filename}")
        n_written += 1

    print(f"\n=== HOÀN TẤT ===")
    print(f"Đã xuất {n_written} email -> {EMAILS_OUTPUT_DIR}")


if __name__ == "__main__":
    export_emails()