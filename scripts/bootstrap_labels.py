import sys
import os
import csv
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to system path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentence_transformers import util
from core.matching import (
    FIELD_MAPPING, normalize_funding, parse_ticket_size, hard_filter, precompute_investor_embeddings
)
from core.scoring_model import compute_funding_fit, FEATURE_COLUMNS
from core.llm_judge import judge_match, score_to_label
from main import load_all_counterparts

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
LABELS_PATH = os.path.join(DATA_DIR, "training", "match_labels.csv")
SKIPPED_PATH = os.path.join(DATA_DIR, "training", "bootstrap_skipped.csv")
ERROR_LOG_PATH = os.path.join(DATA_DIR, "training", "bootstrap_errors.log")


def compute_similarity_score(startup_embeddings: dict, counterpart_embeddings: dict) -> dict:
    """
    Tính cosine similarity từ embedding ĐÃ TÍNH SẴN (không encode lại mỗi lần gọi).
    """
    similar = {}
    for _, counterpart_field, _ in FIELD_MAPPING:
        s_emb = startup_embeddings[counterpart_field]
        c_emb = counterpart_embeddings[counterpart_field]
        similar[counterpart_field] = round(util.cos_sim(s_emb, c_emb).item(), 4)
    return similar


def precompute_startup_embeddings(startups: list) -> dict:
    """
    Batch-encode toàn bộ text của startup 1 lần duy nhất (thay vì encode lại mỗi cặp).
    Key theo tên field của counterpart (technology_focus, problem_focus...) để tra cứu
    thẳng cùng investor_cache trong compute_similarity_score().
    """
    from core.matching import model

    texts, keys = [], []
    for s in startups:
        for startup_field, counterpart_field, _ in FIELD_MAPPING:
            value = s.get(startup_field, "")
            text = ", ".join(value) if isinstance(value, list) else str(value)
            texts.append(text)
            keys.append((s["id"], counterpart_field))

    vectors = model.encode(texts, normalize_embeddings=True, batch_size=32)

    cache = {s["id"]: {} for s in startups}
    for (startup_id, counterpart_field), vector in zip(keys, vectors):
        cache[startup_id][counterpart_field] = vector
    return cache


def bootstrap(
    startups: list,
    counterparts: list,
    max_pairs: int = None,
    sleep_between_calls: float = 1.0,
    max_workers: int = 5,
):
    """
    Generates synthetic training labels using LLM as a judge.
    Gọi Gemini SONG SONG (max_workers luồng cùng lúc) thay vì tuần tự từng cặp + sleep,
    giảm mạnh thời gian chạy so với bản gọi tuần tự trước đây.
    """
    os.makedirs(os.path.dirname(LABELS_PATH), exist_ok=True)
    file_exists = os.path.exists(LABELS_PATH)
    skipped_exists = os.path.exists(SKIPPED_PATH)

    # 1) Precompute embedding 1 lần cho toàn bộ startup + counterpart (không encode lại mỗi cặp)
    startup_cache = precompute_startup_embeddings(startups)
    investor_cache = precompute_investor_embeddings(counterparts)

    # 2) Gom toàn bộ cặp (startup, counterpart) hợp lệ (sau hard_filter) thành 1 danh sách phẳng
    all_pairs = []
    for startup in startups:
        candidates = hard_filter(startup, counterparts)
        for counterpart in candidates:
            all_pairs.append((startup, counterpart))
            if max_pairs and len(all_pairs) >= max_pairs:
                break
        if max_pairs and len(all_pairs) >= max_pairs:
            break

    print(f"[*] Tổng {len(all_pairs)} cặp cần chấm điểm, chạy song song {max_workers} luồng...")

    n_written, n_skipped = 0, 0
    write_lock = threading.Lock()

    def call_judge(pair):
        startup, counterpart = pair
        if sleep_between_calls:
            time.sleep(sleep_between_calls)  # giãn nhẹ trong mỗi luồng để tránh burst request
        judge_result = judge_match(startup, counterpart)
        return startup, counterpart, judge_result

    # Open all three output files together so each run cleanly appends to its own file
    with open(LABELS_PATH, "a", newline="", encoding="utf-8") as f, \
         open(SKIPPED_PATH, "a", newline="", encoding="utf-8") as f_skip, \
         open(ERROR_LOG_PATH, "a", encoding="utf-8") as f_err:

        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(FEATURE_COLUMNS + ["label", "source", "counterpart_type", "raw_score", "judge_reason"])

        skip_writer = csv.writer(f_skip)
        if not skipped_exists:
            skip_writer.writerow(["timestamp", "startup", "counterpart", "counterpart_type", "reason"])

        run_started = time.strftime("%Y-%m-%d %H:%M:%S")
        f_err.write(f"\n=== Run started {run_started} ===\n")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(call_judge, pair) for pair in all_pairs]

            for future in as_completed(futures):
                startup, counterpart, judge_result = future.result()
                cp_name = counterpart.get("name", "Unknown")
                cp_type = counterpart.get("counterpart_type", "investor")

                with write_lock:
                    if judge_result is None:
                        n_skipped += 1
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        reason = "Judge error or parse failed"
                        print(f"  [SKIP] {startup.get('name', 'Unknown')} x {cp_name} ({cp_type}) — {reason}")
                        skip_writer.writerow([ts, startup.get("name", "Unknown"), cp_name, cp_type, reason])
                        f_err.write(f"[{ts}] SKIP {startup.get('name', 'Unknown')} x {cp_name} ({cp_type}) — {reason}\n")
                        continue

                    sim_feats = compute_similarity_score(
                        startup_cache[startup["id"]], investor_cache[counterpart["id"]]["embeddings"]
                    )
                    funding = normalize_funding(startup.get("funding"))
                    if counterpart.get("ticket_size"):
                        min_t, max_t = parse_ticket_size(counterpart["ticket_size"])
                        funding_fit = compute_funding_fit(funding, min_t, max_t)
                    else:
                        funding_fit = 0.5

                    label = score_to_label(judge_result["score"])
                    row = [
                        sim_feats.get("technology_focus", 0),
                        sim_feats.get("problem_focus", 0),
                        sim_feats.get("investment_thesis", 0),
                        sim_feats.get("customer_focus", 0),
                        funding_fit,
                        label,
                        "bootstrap_llm",
                        cp_type,
                        judge_result["score"],
                        judge_result.get("reason", ""),
                    ]
                    writer.writerow(row)
                    n_written += 1
                    print(f"  [OK] {startup.get('name', 'Unknown')} x {cp_name} ({cp_type}) -> score={judge_result['score']} label={label}")

    _print_summary(n_written, n_skipped)
            

def _print_summary(n_written, n_skipped):
    print(f"\n=== BOOTSTRAP COMPLETED ===")
    print(f"Successfully written: {n_written} rows -> {LABELS_PATH}")
    print(f"Skipped (judge errors): {n_skipped} rows -> {SKIPPED_PATH}")
    print(f"Error details logged   -> {ERROR_LOG_PATH}")
    if n_written > 0:
        print(f'Next step run: python -c "from core.scoring_model import train_model; print(train_model())"')


if __name__ == "__main__":
    startups = json.load(open(os.path.join(DATA_DIR, "input", "startups_data.json"), encoding="utf-8"))
        
    counterparts = load_all_counterparts()
    # max_workers=5 luồng song song, mỗi luồng nghỉ 1s giữa các lệnh gọi -> hiệu quả
    # gần ~5 request/giây thay vì 1 request/13s như trước. Nếu bắt đầu thấy lỗi 429,
    # giảm max_workers hoặc tăng sleep_between_calls; nếu chạy êm, có thể tăng thêm.
    bootstrap(startups, counterparts, sleep_between_calls=1.0, max_workers=5)