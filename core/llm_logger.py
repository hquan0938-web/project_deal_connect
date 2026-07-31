import sqlite3
import json
import time
import hashlib
import os
import functools

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "llm_logs.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_hash TEXT,
            prompt_type TEXT,
            prompt TEXT,
            response TEXT,
            model TEXT,
            latency_ms REAL,
            success INTEGER,
            error TEXT,
            created_at TEXT
        )
    """)
    return conn


def log_llm_call(prompt: str, response: str, prompt_type: str, model: str,
                  latency_ms: float, success: bool = True, error: str = None):
    conn = _get_conn()
    prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()
    conn.execute(
        """INSERT INTO llm_calls
           (prompt_hash, prompt_type, prompt, response, model, latency_ms, success, error, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (prompt_hash, prompt_type, prompt, response, model, latency_ms,
         int(success), error, time.strftime("%Y-%m-%dT%H:%M:%S"))
    )
    conn.commit()
    conn.close()


def logged_llm_call(prompt_type: str):
    """
    Decorator: bọc quanh 1 hàm gọi LLM (nhận prompt trả về response text),
    tự động đo latency + ghi log, không đổi behavior của hàm gốc.

    Cách dùng:
        @logged_llm_call(prompt_type="match_reason")
        def call_gemini(prompt_text: str, model: str) -> str:
            response = client.models.generate_content(model=model, contents=prompt_text)
            return response.text
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(prompt_text, *args, model="unknown", **kwargs):
            start = time.time()
            try:
                result = fn(prompt_text, *args, model=model, **kwargs)
                latency_ms = (time.time() - start) * 1000
                log_llm_call(prompt_text, result, prompt_type, model, latency_ms, success=True)
                return result
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                log_llm_call(prompt_text, "", prompt_type, model, latency_ms, success=False, error=str(e))
                raise
        return wrapper
    return decorator


def get_recent_calls(limit: int = 10, prompt_type: str = None):
    conn = _get_conn()
    if prompt_type:
        rows = conn.execute(
            "SELECT id, prompt_type, model, latency_ms, success, created_at FROM llm_calls WHERE prompt_type=? ORDER BY id DESC LIMIT ?",
            (prompt_type, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, prompt_type, model, latency_ms, success, created_at FROM llm_calls ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return rows


def get_stats():
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM llm_calls WHERE success=0").fetchone()[0]
    avg_latency = conn.execute("SELECT AVG(latency_ms) FROM llm_calls WHERE success=1").fetchone()[0]
    by_type = conn.execute("SELECT prompt_type, COUNT(*) FROM llm_calls GROUP BY prompt_type").fetchall()
    conn.close()
    return {
        "total_calls": total,
        "failed_calls": failed,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency else None,
        "by_type": dict(by_type),
    }