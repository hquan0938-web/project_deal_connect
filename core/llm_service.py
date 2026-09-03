from google import genai
from google.genai import types
from config import Config
from core.prompts import get_email_prompt, get_match_reason_prompt, get_time_extraction_prompt
from core.llm_logger import logged_llm_call
import json

if Config.GEMINI_BASE_URL:
    client = genai.Client(
        api_key=Config.GEMINI_API_KEY,
        http_options=types.HttpOptions(base_url=Config.GEMINI_BASE_URL),
    )
else:
    client = genai.Client(api_key=Config.GEMINI_API_KEY)
MODEL_ID = 'gemini-2.5-flash'


@logged_llm_call(prompt_type="raw_gemini_call")
def _call_gemini(prompt_text: str, model: str = MODEL_ID) -> str:
    response = client.models.generate_content(model=model, contents=prompt_text)
    return response.text.strip() if response.text else ""


def generate_email_content(startup: dict, investor: dict, match_score: float, match_reason: str) -> str:
    prompt_text = get_email_prompt(startup, investor, match_score, match_reason)
    try:
        return _call_gemini(prompt_text, model=MODEL_ID)
    except Exception as e:
        print(f"Error in calling Gemini (Email): {e}")
        return ""


def generate_match_reason(startup: dict, investor: dict) -> str:
    prompt_text = get_match_reason_prompt(startup, investor)
    try:
        return _call_gemini(prompt_text, model=MODEL_ID)
    except Exception as e:
        print(f"Error in calling Gemini (Reason): {e}")
        return ""


def extract_chosen_time(reply_text: str) -> dict:
    prompt = get_time_extraction_prompt(reply_text)
    try:
        raw = _call_gemini(prompt, model=MODEL_ID)
        clean_json = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except json.JSONDecodeError:
        print("AI không thể bóc tách định dạng thời gian hợp lệ.")
        return None
    except Exception as e:
        print(f"Lỗi khi gọi Gemini (Trích xuất thời gian): {e}")
        return None


def generate_mock_startup_reply(start_time, end_time) -> str:
    start_str = start_time.strftime('%H:%M')
    end_str = end_time.strftime('%H:%M')
    date_str = start_time.strftime('%d/%m/%Y')
    prompt = get_mock_startup_reply_prompt(start_str, end_str, date_str)
    try:
        return _call_gemini(prompt, model=MODEL_ID)
    except Exception as e:
        print(f"Lỗi khi AI tạo mock reply: {e}")
        return f"Chào team NIC, chốt họp từ {start_str} đến {end_str} ngày {date_str} nhé."