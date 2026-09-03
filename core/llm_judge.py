
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.prompts import get_judge_prompt, get_pairwise_judge_prompt
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

def judge_pairwise(startup: dict, investor_a: dict, investor_b: dict,
                    anchor_positive: dict = None, anchor_negative: dict = None) -> dict:
    prompt = get_pairwise_judge_prompt(startup, investor_a, investor_b, anchor_positive, anchor_negative)
    try:
        raw = _call_gemini(prompt, model = MODEL_ID)
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        if result.get("winner") not in ("A","B", "tie"):
            return None
        return result
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"[llm_judge] Không parse được kết quả so sánh: {e}")
        return None
    except Exception as e:
        print(f"[llm_judge] Lỗi khi gọi Gemini: {e}")
        return None
    
def judge_pairwise_consistent(startup: dict, investor_a: dict, investor_b: dict,
                               anchor_positive: dict = None, anchor_negative: dict = None,
                               n_calls: int = 3) -> str | None:
    votes = []
    with ThreadPoolExecutor(max_workers=n_calls) as executor:
        futures = [executor.submit(judge_pairwise, startup, investor_a, investor_b,
                                   anchor_positive, anchor_negative) for _ in range(n_calls)]
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                votes.append(result.get("winner"))
    if len(votes) == 0:
        return None
    tally = Counter(votes)
    winner, count = tally.most_common(1)[0]

    # Không có vote nào chiếm đa số thực sự (vd hòa 1-1-1 khi n_calls=3) -> mơ hồ
    if count <= len(votes) / 2:
        return None

    return winner