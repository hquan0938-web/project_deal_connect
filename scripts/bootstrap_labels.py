import csv
import itertools
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from core.llm_judge import judge_pairwise_consistent
from core.matching import hard_filter
from core.scoring_model import BASE_FEATURE_COLUMNS
from scripts.generate_pairs import (
    compute_pair_feature,
    construction_pairs,
    load_all_industries,
    load_investors,
)
 
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STARTUPS_PATH = os.path.join(BASE_DIR, "data", "output", "startup_data.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "training", "match_labels.csv")
 
CONSTRUCTION_WEIGHT = 3.0
PAIRWISE_WEIGHT = 1.0
PAIRWISE_N_CALLS = 3
MAX_PAIRWISE_COMPARISONS_PER_STARTUP = 5 


def load_startups(path: str = STARTUPS_PATH) -> list:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]
def build_construction_rows(startups: list, investors: list, all_industries: list) -> list:
    """Ghép construction pairs -> tính feature -> trả về list row cho CSV."""
    rows = []
    pairs = construction_pairs(startups, investors, all_industries)
    for pair in pairs:
        features = compute_pair_feature(pair["startup"], pair["investor"])
        row = {col: features.get(col, 0.0) for col in BASE_FEATURE_COLUMNS if col in features}
        row["label"] = pair["label"]
        row["source"] = pair["source"]
        row["weight"] = pair["weight"]
        rows.append(row)
    return rows
PAIRWISE_MAX_WORKERS = 4 

def _run_one_comparison(startup: dict, investor_a: dict, investor_b: dict,
                         anchor_positive: dict, anchor_negative: dict) -> list:
    winner = judge_pairwise_consistent(startup, investor_a, startup, investor_a, investor_b,
        anchor_positive=anchor_positive, anchor_negative=anchor_negative,
        n_calls=PAIRWISE_N_CALLS,
    )
    if winner is None:
        return []
    if winner is "tie":
        return []
    winner_investor = investor_a if winner == "A" else investor_b
    loser_investor = investor_b if winner == "A" else investor_a
 
    win_features = compute_pair_feature(startup, winner_investor)
    lose_features = compute_pair_feature(startup, loser_investor)

    return [
        {**{c: win_features.get(c, 0.0) for c in BASE_FEATURE_COLUMNS if c in win_features},
         "label": 1, "source": "pairwise", "weight": PAIRWISE_WEIGHT},
        {**{c: lose_features.get(c, 0.0) for c in BASE_FEATURE_COLUMNS if c in lose_features},
         "label": 0, "source": "pairwise", "weight": PAIRWISE_WEIGHT},
    ]
def build_pairwise_rows(startups: list, investors: list, anchor_positive: dict, anchor_negative: dict) -> list:
    all_comparisons = []
    for startup in startups:
        candidates = hard_filter(startup, investors)
        if len(candidates) < 2:
            continue # less than 2 candidates, cannot compare
        comparisons = list(itertools.combinations(candidates, 2))[:MAX_PAIRWISE_COMPARISONS_PER_STARTUP]
        #create pairwise comparisons for each startup
        for investor_a, investor_b in comparisons:
            all_comparisons.append((startup, investor_a, investor_b))

    rows = []
    with ThreadPoolExecutor(max_workers=PAIRWISE_MAX_WORKERS) as executor:
        futures = [
            executor.submit(_run_one_comparison, startup, investor_a, investor_b,
                             anchor_positive, anchor_negative)
            for startup, investor_a, investor_b in all_comparisons
        ]
        # each pair, executor.submit returns a Future object, which represents the result of the computation that will be available in the future. 
        # The as_completed function is used to iterate over these Future objects as they complete, 
        # allowing us to process the results as soon as they are ready, rather than waiting for all of them to finish. 
        # This can improve efficiency and responsiveness, especially when dealing with a large number of comparisons.
        for future in as_completed(futures):
            rows.extend(future.result())
 
    return rows

def main():
    investors = load_investors()
    all_industries = load_all_industries(investors)
    startups = load_startups()
    construction_rows = build_construction_rows(startups, investors, all_industries)
    construction_pairs_list = construction_pairs(startups, investors, all_industries)
    anchor_positive = next((p for p in construction_pairs_list if p["source"] == "construction_positive"), None)
    anchor_negative = next((p for p in construction_pairs_list if p["source"] == "construction_industry_mismatch"), None)
 
    pairwise_rows = build_pairwise_rows(startups, investors, anchor_positive, anchor_negative)
    all_rows = construction_rows + pairwise_rows
    if not all_rows:
        print("[bootstrap] Không sinh được dòng nào — kiểm tra lại data đầu vào.")
        return
    fieldnames = [c for c in BASE_FEATURE_COLUMNS if any(c in r for r in all_rows)] + ["label", "source", "weight"]
    # fieldnames is constructed by taking all the base feature columns that are present in any of the rows (all_rows) 
    # and adding the additional columns "label", "source", and "weight" to the list.
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({k: row.get(k, 0.0) for k in fieldnames})
 
 
 
if __name__ == "__main__":
    main()