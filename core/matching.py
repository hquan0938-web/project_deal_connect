import os


os.environ.setdefault("HF_HUB_OFFLINE", "1") 
import re
import hashlib
import pickle
from sentence_transformers import SentenceTransformer, util
from core.scoring_model import predict_score, compute_funding_fit
from core.llm_service import generate_email_content, generate_match_reason

model = SentenceTransformer("BAAI/bge-m3")
EMBEDDING_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "models", "investor_embeddings_cache.pkl"
)

FIELD_MAPPING = [
    ("technology", "technology_focus", 0.35),
    ("problem", "problem_focus", 0.25),
    ("solution", "investment_thesis", 0.25),
    ("customers", "customer_focus", 0.15),
]


def embed_text(text):
    if isinstance(text, list):
        text = ", ".join(text)
    return model.encode(text, normalize_embeddings=True)

def _investors_content_hash(investors):
    """Hash nội dung các field dùng để encode -> phát hiện khi investor data thay đổi."""
    parts = []
    for investor in investors:
        parts.append(str(investor.get("id","")))
        for _ , investor_field, _ in FIELD_MAPPING:
            #second collum in FIELD_MAPPING means investor field
            parts.append(str(investor.get(investor_field, "")))
    return hashlib.md5("||".join(parts).encode("utf-8")).hexdigest()
    #translate resluts into Bytes

def precompute_investor_embeddings(investors, use_cache: bool = True):
    content_hash = _investors_content_hash(investors)
    
    # Nếu đã có cache trên đĩa và data investor CHƯA đổi (hash khớp) -> dùng lại luôn.
    # Chỉ encode lại khi data thay đổi hoặc chưa từng cache.
    if use_cache and os.path.exists(EMBEDDING_CACHE_PATH):
        try:
            with open(EMBEDDING_CACHE_PATH, "rb") as f:
                cached = pickle.load(f)
            if cached.get("hash") == content_hash:
                return cached["cache"]
        except (pickle.PickleError, EOFError, KeyError):
            pass

    texts, keys = [], []
    for investor in investors:
        for _ , investor_field, _ in FIELD_MAPPING:
            value = investor.get(investor_field, "")
            text = ", ".join(value) if isinstance(value, list) else str(value)
            texts.append(text)
            
            # SỬA LỖI 3: Thêm ngoặc tròn () để tạo thành 1 tuple (cặp giá trị)
            keys.append((investor["id"], investor_field))
            
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=32)
    
    # Khởi tạo investor_cache. Với mỗi nhà đầu tư, tạo một không gian lưu trữ riêng (dựa trên id),
    # lưu lại tên (name) và chuẩn bị sẵn hộc tủ trống (embeddings) để đựng dữ liệu AI.
    investor_cache = {}
    for investor in investors:
        investor_cache[investor["id"]] = {
            "name": investor["name"],
            "embeddings": {},
        }
    
    # zip(keys, vectors): Ghép cặp 1-1 giữa thông tin nhận diện và vector tương ứng.
    # Sau đó mở đúng ngăn tủ embeddings của nhà đầu tư đó để cất vector vào.
    for (investor_id, investor_field), vector in zip(keys, vectors):
        investor_cache[investor_id]["embeddings"][investor_field] = vector
        
    if use_cache:
        # Tự động tạo cấu trúc thư mục chứa file cache nếu chưa tồn tại
        os.makedirs(os.path.dirname(EMBEDDING_CACHE_PATH), exist_ok=True)
        # Lưu mã hash (để sau này kiểm tra thay đổi) và dữ liệu cache xuống đĩa
        with open(EMBEDDING_CACHE_PATH, "wb") as f:
            pickle.dump({"hash": content_hash, "cache": investor_cache}, f)
            
    return investor_cache
def parse_ticket_size(ticket_size: str):
    minimum, maximum = ticket_size.split("-")
    return int(minimum.strip()), int(maximum.strip())


def normalize_funding(funding) -> float | None:
    """
    Chuẩn hoá funding (do Gemini trích xuất, có thể là số, string tự do,
    hoặc text không tìm thấy) về float. Trả về None nếu không parse được.
    """
    if funding is None:
        return None
    if isinstance(funding, (int, float)):
        return float(funding)

    text = str(funding).strip().upper()
    if not text:
        return None

    text = text.replace(",", "").replace("$", "").replace("USD", "").replace("VND", "").strip()

    match = re.match(r"^([\d.]+)\s*([KMB]?)$", text)
    if not match:
        return None

    number_str, unit = match.groups()
    try:
        number = float(number_str)
    except ValueError:
        return None

    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(unit, 1)
    return number * multiplier


def hard_filter(startup, counterparts):
    """
    counterparts: list gộp từ investors + corporates + universities + research_institutions
    """
    candidates = []
    funding = normalize_funding(startup.get("funding"))

    for cp in counterparts:
        cp_type = cp.get("counterpart_type", "investor")

        if cp_type == "investor" and cp.get("ticket_size"):
                min_t, max_t = parse_ticket_size(cp["ticket_size"])
                if funding is not None and not (min_t <= funding <= max_t):
                    continue

        candidates.append(cp)

    return candidates


def semantic_match(startup, candidate_investors, investor_cache):
    startup_embedding = {}
    for startup_field, _, _ in FIELD_MAPPING:
        
        startup_embedding[startup_field] = embed_text(startup[startup_field]) 
        
    startup_fund = normalize_funding(startup.get("funding"))
    res = []
    
    for investor in candidate_investors:
        investor_id = investor["id"]
        indiv_score = {}
        weight_total = 0
        
        for startup_field, investor_field, weight in FIELD_MAPPING:

            similarity = util.cos_sim(
                startup_embedding[startup_field], 
                investor_cache[investor_id]["embeddings"][investor_field]
            ).item() 
            

            indiv_score[investor_field] = similarity
            weight_total += weight * similarity
    
        if investor.get("ticket_size"):
            min_ticket, max_ticket = parse_ticket_size(investor["ticket_size"])
            funding_fit = compute_funding_fit(startup_fund, min_ticket, max_ticket)
        else:
            funding_fit = 0.5
            
        final_score = predict_score(indiv_score, funding_fit, fallback_weighted_score=weight_total)
        indiv_score_display = [f"{key} matching score: {value}" for key, value in indiv_score.items()]
        
        res.append({
            "id": investor["id"],
            "name": investor["name"],
            "score": round(final_score, 4),
            "indiv_score": indiv_score_display,
        })
 
    # Sắp xếp kết quả từ cao xuống thấp
    res.sort(key=lambda x: x["score"], reverse=True)
    return res

def reason_generate(startup: dict, investor: dict) -> str:
    return generate_match_reason(startup, investor)


def email_generate(startup: dict, investor: dict, match_score: float, match_reason: str) -> str:
    return generate_email_content(startup, investor, match_score, match_reason)


def convert_match(match_result, startup, reason_generate_fn):
    scores = {}
    for s in match_result["indiv_score"]:
        key, value = s.split(" matching score: ")
        scores[key] = float(value)

    startup_info = {
        "name": startup["name"],
        "industry": startup["industry"],
        "technology": scores.get("technology_focus", 0),
        "problem": scores.get("problem_focus", 0),
        "investment_thesis": scores.get("investment_thesis", 0),
        "customers": scores.get("customer_focus", 0),
    }

    investor_info = {
        "id": match_result["id"],
        "name": match_result["name"],
    }

    return {
        "startup": startup_info,
        "investor": investor_info,
        "match_score": match_result["score"],
        "match_reason": reason_generate_fn(startup_info, investor_info),
    }
