import copy
import json
import os
import random
import sys
import pandas as pd
from sentence_transformers import util
 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.matching import FIELD_MAPPING, embed_text, normalize_funding, parse_ticket_size
from core.scoring_model import compute_funding_fit
 
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INVESTORS_PATH = os.path.join(BASE_DIR, "data", "input", "investors_data.json")
STARTUPS_PATH = os.path.join(BASE_DIR, "data", "input", "startups_data.json")
LABELS_PATH = os.path.join(BASE_DIR, "data", "training", "match_labels.csv")

CSV_COLUMNS = ["technology_focus", "problem_focus", "investment_thesis", "customer_focus",
               "funding_fit", "label", "source", "counterpart_type", "raw_score",
               "judge_reason", "weight"]


def load_startups(path: str = STARTUPS_PATH) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
 
def load_investors(path: str = INVESTORS_PATH) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_all_industries(investors: list)-> list:
    industries = set()
    for inv in investors:
        industries.update(inv.get("target_industries", []))
    return sorted(industries)

def compute_pair_feature(startup:dict, investor:dict) -> dict:
    feature = {}
    for startup_field, investor_field, _ in FIELD_MAPPING:
        startup_emb = embed_text(startup.get(startup_field,""))
        investor_emb =  embed_text(investor.get(investor_field,""))
        feature[investor_field] = util.cos_sim(startup_emb, investor_emb).item()
    funding = normalize_funding(startup.get("funding"))
    if investor.get("ticket_size"):
        min_t , max_t = parse_ticket_size(investor["ticket_size"])
        feature["funding_fit"] = compute_funding_fit(funding, min_t, max_t)
    else: feature["funding_fit"]= 0.0
    return feature

def hard_negative_industry(investor: dict, all_investors: list) -> dict:
    """
    Hard negative: clone toàn bộ profile của MỘT INVESTOR KHÁC (không cùng
    target_industries với investor hiện tại) làm startup giả, ghép với
    investor hiện tại, gán label=0.
    all_investors: toàn bộ danh sách investor (bao gồm cả `investor` này).
    """
    candidates = [
        inv for inv in all_investors
        if inv["id"] != investor["id"]
        and not set(inv.get("target_industries", [])) & set(investor.get("target_industries", []))
    ]
    if not candidates:
        return None

    off_domain = random.choice(candidates)
    clone = {
        "name": f"OffDomain_{off_domain['id']}",
        "industry": off_domain.get("target_industries", ["Unknown"])[0],
        "stage": "Seed",
        "funding": "300000",
        "technology": off_domain.get("technology_focus", ""),
        "problem": off_domain.get("problem_focus", ""),
        "solution": off_domain.get("investment_thesis", ""),
        "customers": off_domain.get("customer_focus", ""),
    }
    return {
        "startup": clone,
        "investor": investor,
        "label": 0,
        "source": "construction_industry_mismatch",
        "judge_reason": f"Construction: profile thuộc domain của investor '{off_domain['id']}' "
                         f"(không cùng target_industries với '{investor['id']}'), ghép cặp label=0.",
        "weight": 3.0,
    }
def hard_negative_ticket(startup:dict, investor: dict) -> dict:
    if not investor.get("ticket_size"): return None
    clone = copy.deepcopy(startup)
    _, max_t = parse_ticket_size(investor["ticket_size"])
    clone["funding"] = str(int(max_t*3))
    return{
        "startup": clone,
        "investor": investor,
        "label" : 0,
        "source" :  "construction_ticket_mismatch",
        "judge_reason": f"Construction: funding ép thành {clone['funding']}, gấp 3 lần ticket size tối đa của investor.",
        "weight": 3.0
    }
def positive_exact(investor: dict) -> dict:
    """
    Positive: sinh 1 startup tổng hợp trực tiếp từ chính profile investor
    (mọi field liên quan feature đều lấy thẳng từ investor) -> similarity cao thật,
    không cần startup thật làm gốc vì mọi giá trị gốc sẽ bị ghi đè hết.
    """
    clone = {
        "name": f"ExactMatch_{investor['id']}",
        "stage": investor.get("target_stages", ["Seed"])[0],
        "technology": investor.get("technology_focus", ""),
        "problem": investor.get("problem_focus", ""),
        "solution": investor.get("investment_thesis", ""),
        "customers": investor.get("customer_focus", ""),
    }
    if investor.get("ticket_size"):
        min_t, max_t = parse_ticket_size(investor["ticket_size"])
        clone["funding"] = str(int((min_t + max_t) / 2))
    if investor.get("target_industries"):
        clone["industry"] = investor["target_industries"][0]

    return {
        "startup": clone,
        "investor": investor,
        "label": 1,
        "source": "construction_positive",
        "judge_reason": "Construction: profile tổng hợp khớp chính xác tiêu chí investor.",
        "weight": 1.0,
    }
def construction_pairs(startups: list, investors: list = None, all_industries: list = None, max_ticket_negatives_per_investor: int = 2) -> list:
    if investors is None:
        investors = load_investors()
    if all_industries is None:
        all_industries = load_all_industries(investors)

    pairs = []

    # Per-investor: mỗi investor sinh đúng 1 positive + tối đa 1 industry-mismatch,
    # KHÔNG lặp theo startup (tránh trùng lặp, xem giải thích ở tin trước)
    for investor in investors:
        pos = positive_exact(investor)
        if pos is not None:
            pairs.append(pos)

        neg_industry = hard_negative_industry(investor, investors)
        if neg_industry is not None:
            pairs.append(neg_industry)

    # Per-startup thật: chỉ nhánh ticket-mismatch cần nội dung startup thật
    for investor in investors:
        if not investor.get("ticket_size"):
            continue
        sample_size = min(max_ticket_negatives_per_investor, len(startups))
        sampled_startups = random.sample(startups, sample_size)
        for startup in sampled_startups:
            neg_ticket = hard_negative_ticket(startup, investor)
            if neg_ticket is not None:
                pairs.append(neg_ticket)

    return pairs
def pairs_to_rows(pairs: list) -> list:
    rows = []
    for pair in pairs:
        feature = compute_pair_feature(pair["startup"], pair["investor"])
        rows.append({
            "technology_focus": round(feature["technology_focus"], 4),
            "problem_focus": round(feature["problem_focus"], 4),
            "investment_thesis": round(feature["investment_thesis"], 4),
            "customer_focus": round(feature["customer_focus"], 4),
            "funding_fit": round(feature["funding_fit"], 4),
            "label": pair["label"],
            "source": pair["source"],
            "counterpart_type": "investor",
            "raw_score": "",
            "judge_reason": pair["judge_reason"],
            "weight": pair["weight"],
        })
    return rows

def add_rows_to_csv(rows: list, labels_path: str = LABELS_PATH) -> pd.DataFrame:
    new_df = pd.DataFrame(rows, columns=CSV_COLUMNS)
    if os.path.exists(labels_path):
        old_df = pd.read_csv(labels_path)
        if "weight" not in old_df.columns:
            old_df["weight"] = 1.0
        # Loại bỏ construction cũ trước khi ghi construction mới -> chạy lại bao nhiêu lần cũng không bị nhân đôi
        old_df = old_df[old_df["source"] == "bootstrap_llm"]
        combined_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        combined_df = new_df
    combined_df.to_csv(labels_path, index=False)
    return combined_df

if __name__ == "__main__":
    investors = load_investors()
    startups = load_startups()
    all_industries = load_all_industries(investors)
    pairs = construction_pairs(startups, investors, all_industries)
    rows = pairs_to_rows(pairs)
    combined = add_rows_to_csv(rows)
    print(f"Sinh được {len(pairs)} cặp construction cho {len(startups)} startup x {len(investors)} investor")
    print(f"Đã append {len(rows)} dòng vào {LABELS_PATH} (tổng hiện tại: {len(combined)} dòng)")
 
