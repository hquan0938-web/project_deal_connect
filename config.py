import os
from dotenv import load_dotenv
load_dotenv()
#config of API keys
class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL")  # để trống = dùng endpoint chính chủ Google
    CALENDAR_CREDENTIALS_PATH = os.getenv("CALENDAR_CREDENTIALS_PATH", os.path.join("secrets", "credentials.json"))
    #OUTPUT_EMAIL_FOLDER = "generated_emails/"
if not Config.GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in the environment variables.")