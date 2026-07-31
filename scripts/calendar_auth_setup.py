import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_DIR = os.path.join(BASE_DIR, "secrets")
CREDENTIALS_PATH = os.path.join(SECRETS_DIR, "credentials.json")
TOKEN_PATH = os.path.join(SECRETS_DIR, "token.json")

# Quyền đọc + ghi lịch (cần "ghi" để tạo event/mời investor sau này)
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def main():
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"[!] Không tìm thấy {CREDENTIALS_PATH}.")
        print("    Hãy tải OAuth Client ID (Desktop app) từ Google Cloud Console")
        print("    và lưu vào secrets/credentials.json trước khi chạy script này.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)

    os.makedirs(SECRETS_DIR, exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print(f"[*] Xác thực thành công. Đã lưu token vào {TOKEN_PATH}")
    print(f"[debug] os.getcwd() = {os.getcwd()}")
    print(f"[debug] TOKEN_PATH tuyet doi = {os.path.abspath(TOKEN_PATH)}")
    print(f"[debug] File ton tai ngay sau khi ghi? {os.path.exists(TOKEN_PATH)}")
    print(f"[debug] Kich thuoc file = {os.path.getsize(TOKEN_PATH) if os.path.exists(TOKEN_PATH) else 'N/A'} bytes")


if __name__ == "__main__":
    main()