import json
from core.prompts import get_judge_prompt
from core.llm_service import _call_gemini, MODEL_ID
def judge_match(starup:dict, investor: dict )-> dict:
    """
    Trả về {"score": 1-5, "reason": "..."} hoặc None nếu parse lỗi
    (không raise để không làm gãy batch bootstrap khi chạy hàng loạt).
    """
    prompt = get_judge_prompt(starup, investor)
    try:
        raw = _call_gemini(prompt, model = MODEL_ID)
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        if "score" not in result or not(1<= result["score"]<= 5):
            return None
        return result
    except(json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"[llm_judge] Không parse được kết quả chấm điểm: {e}")
        return None
    except Exception as e:
        print(f"[llm_judge] Lỗi khi gọi Gemini: {e}")
        return None
def score_to_label(score:int, threshold:int = 4) ->int:
    """Chuyển điểm 1-5 thành nhãn nhị phân 0/1 cho Logistic Regression.
    Mặc định: score >= 4 -> match tốt (1), ngược lại -> không tốt (0).
    """
    return 1 if score >= threshold else 0
