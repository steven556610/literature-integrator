"""
llm_analyzer.py
Multi-backend LLM analyzer for Literature Integrator.

Supported backends:
  - gemini   : Google Gemini 2.5 Flash (cloud, via google.genai SDK)
  - qwen7b   : Qwen2.5:7b  (local Ollama, fast)
  - qwen14b  : Qwen2.5:14b (local Ollama, more accurate)

All analysis output is in Traditional Chinese (繁體中文).
Backend is configured via LLM_BACKEND env var (default: gemini).
"""
import os
import json
import time
import requests as http_requests
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini").lower()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

QWEN_MODEL_MAP = {
    "qwen7b":  "qwen2.5:7b-instruct",
    "qwen14b": "qwen2.5:14b",
}

# --------------------------------------------------------------------------- #
# System prompt (shared across all backends)
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """你是一位資深的生物醫學 AI 科學家，同時具備以下專業背景：
- 癌症免疫療法與癌症疫苗開發（新抗原、mRNA 疫苗、T 細胞療法）
- 計算生物學與生物資訊學
- 藥物開發與分子對接
- 機器學習、深度學習、大型語言模型（LLM）
- 自然語言處理（NLP）

你的任務是根據所提供的文獻標題與摘要，進行深度分析並以「繁體中文」回答。

請嚴格以 JSON 格式輸出，不得包含任何 JSON 以外的文字（不要加 ```json 等標記）：
{
  "llm_summary": "（繁體中文）2~4 句話的精簡摘要，包含核心方法與主要貢獻",
  "translated_summary": "（繁體中文）請將原始摘要(Abstract)完整翻譯為繁體中文",
  "code_available": "YES | NO | PARTIAL | UNKNOWN",
  "code_url": "程式碼連結（若無則為空字串）",
  "data_available": "YES | NO | PARTIAL | UNKNOWN",
  "data_url": "資料集連結（若無則為空字串）",
  "theory_assumptions": "（繁體中文）本文的核心理論假設或關鍵科學猜想",
  "exp_motivation": "（繁體中文）本文想解決什麼痛點？實驗動機與研究缺口為何？",
  "sota_comparison": "（繁體中文）與現有 SOTA 相比如何？是否有具體指標提升？有哪些優缺點？"
}

判斷原則：
- code_available: 若摘要提到 GitHub / 開源 → YES；「即將發布」→ PARTIAL；明確不公開 → NO；其他 → UNKNOWN
- data_available: 同理判斷資料集是否公開可用"""

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _build_user_message(paper: dict) -> str:
    return f"""請分析以下文獻：

來源: {paper.get('source','').upper()} | 發表日期: {paper.get('published_date','')}
標題: {paper.get('title','Unknown Title')}
作者: {paper.get('authors','')}
連結: {paper.get('url','')}

摘要:
{paper.get('summary','')}

請輸出純 JSON，不要有任何其他文字。"""


def _parse_json_response(text: str) -> dict | None:
    """Robustly parse JSON from LLM output, stripping markdown fences if present."""
    text = text.strip()
    # Strip ```json ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    # Find first { ... }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _normalize_result(result: dict) -> dict:
    """Ensure all required keys exist and normalize availability flags."""
    required = ["llm_summary", "translated_summary", "code_available", "code_url",
                "data_available", "data_url", "theory_assumptions",
                "exp_motivation", "sota_comparison"]
    for key in required:
        if key not in result:
            result[key] = ""
    for field in ["code_available", "data_available"]:
        val = str(result.get(field, "UNKNOWN")).upper().strip()
        if val not in ("YES", "NO", "PARTIAL", "UNKNOWN"):
            val = "UNKNOWN"
        result[field] = val
    return result


# --------------------------------------------------------------------------- #
# Backend: Gemini (google.genai SDK — new API)
# --------------------------------------------------------------------------- #

def _analyze_gemini(paper: dict, retries: int = 3, delay: float = 5.0) -> dict:
    """Analyze via Google Gemini 2.5 Flash using the new google.genai SDK."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError("google-genai package not installed. Run: pip install google-genai")

    if not GOOGLE_API_KEY:
        raise EnvironmentError("GOOGLE_API_KEY not set in .env")

    client = genai.Client(api_key=GOOGLE_API_KEY)
    user_msg = _build_user_message(paper)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_msg}"

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(f"    [Gemini] Attempt {attempt}/{retries}...")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                    top_p=0.8,
                    max_output_tokens=1500,
                ),
            )
            raw_text = response.text.strip()
            result = _parse_json_response(raw_text)
            if result:
                result = _normalize_result(result)
                result["status"] = "analyzed"
                result["raw_analysis"] = raw_text
                result["backend"] = "gemini-2.5-flash"
                return result
            else:
                raise ValueError(f"JSON parse failed. Raw: {raw_text[:200]}")
        except Exception as e:
            print(f"    [Gemini] Error: {e}")
            last_error = e
            if attempt < retries:
                time.sleep(delay)

    return _failed_result(str(last_error), "gemini-2.5-flash")


# --------------------------------------------------------------------------- #
# Backend: Ollama (Qwen2.5 local)
# --------------------------------------------------------------------------- #

def _analyze_ollama(paper: dict, model_tag: str, retries: int = 3, delay: float = 5.0) -> dict:
    """Analyze via Ollama local inference (Qwen2.5:7b or 14b)."""
    user_msg = _build_user_message(paper)
    payload = {
        "model": model_tag,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.8,
            "num_predict": 1500,
        },
    }
    url = f"{OLLAMA_BASE_URL}/api/chat"

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(f"    [Ollama/{model_tag}] Attempt {attempt}/{retries}...")
            resp = http_requests.post(url, json=payload, timeout=900)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data.get("message", {}).get("content", "")
            result = _parse_json_response(raw_text)
            if result:
                result = _normalize_result(result)
                result["status"] = "analyzed"
                result["raw_analysis"] = raw_text
                result["backend"] = model_tag
                return result
            else:
                raise ValueError(f"JSON parse failed. Raw: {raw_text[:200]}")
        except Exception as e:
            print(f"    [Ollama/{model_tag}] Error: {e}")
            last_error = e
            if attempt < retries:
                time.sleep(delay)

    return _failed_result(str(last_error), model_tag)


# --------------------------------------------------------------------------- #
# Failed result template
# --------------------------------------------------------------------------- #

def _failed_result(error_msg: str, backend: str) -> dict:
    return {
        "status": "failed",
        "llm_summary": "分析失敗，無法生成摘要",
        "translated_summary": "翻譯失敗",
        "code_available": "UNKNOWN",
        "code_url": "",
        "data_available": "UNKNOWN",
        "data_url": "",
        "theory_assumptions": "",
        "exp_motivation": "",
        "sota_comparison": "",
        "raw_analysis": error_msg,
        "backend": backend,
    }


# --------------------------------------------------------------------------- #
# Public API: analyze_paper()
# --------------------------------------------------------------------------- #

def analyze_paper(paper: dict, backend: str = None, retries: int = 3) -> dict:
    """
    Analyze a single paper dict using the configured (or specified) backend.

    Args:
        paper  : dict with keys: title, authors, summary, url, source, published_date
        backend: override LLM_BACKEND env var ('gemini' | 'qwen7b' | 'qwen14b')
        retries: number of retry attempts on transient errors

    Returns:
        dict with analysis fields + 'status', 'backend', 'raw_analysis'
    """
    chosen = (backend or LLM_BACKEND).lower()
    title_short = paper.get("title", "Unknown")[:60]
    print(f"  [*] Analyzing [{chosen}]: {title_short}...")

    if chosen == "gemini":
        return _analyze_gemini(paper, retries=retries)
    elif chosen in QWEN_MODEL_MAP:
        return _analyze_ollama(paper, QWEN_MODEL_MAP[chosen], retries=retries)
    else:
        # Try Ollama with raw model name as fallback
        print(f"  [!] Unknown backend '{chosen}', trying as Ollama model name...")
        return _analyze_ollama(paper, chosen, retries=retries)


# --------------------------------------------------------------------------- #
# Batch analyzer
# --------------------------------------------------------------------------- #

def analyze_pending_papers(papers: list, backend: str = None, rate_limit_delay: float = 2.0) -> list:
    """
    Analyze a list of paper objects (SQLAlchemy ORM rows or plain dicts).
    Returns list of (paper_id, analysis_dict) tuples.
    """
    results = []
    total = len(papers)
    chosen = (backend or LLM_BACKEND).lower()
    print(f"\n[*] Batch analysis: {total} papers | backend={chosen}\n")

    for i, paper in enumerate(papers, 1):
        # Support both ORM objects and plain dicts
        paper_dict = {
            "paper_id":       getattr(paper, "paper_id",       paper.get("paper_id", "unknown")),
            "title":          getattr(paper, "title",           paper.get("title", "")),
            "authors":        getattr(paper, "authors",         paper.get("authors", "")),
            "summary":        getattr(paper, "summary",         paper.get("summary", "")),
            "url":            getattr(paper, "url",             paper.get("url", "")),
            "source":         getattr(paper, "source",          paper.get("source", "")),
            "published_date": getattr(paper, "published_date",  paper.get("published_date", "")),
        }
        paper_id = paper_dict["paper_id"]
        analysis = analyze_paper(paper_dict, backend=backend)
        results.append((paper_id, analysis))
        print(f"  [{i}/{total}] {paper_dict['title'][:55]} -> {analysis['status']} [{analysis.get('backend','')}]")

        if i < total:
            # Ollama doesn't need rate limiting (local), Gemini does
            sleep_time = 0.5 if chosen in QWEN_MODEL_MAP else rate_limit_delay
            time.sleep(sleep_time)

    ok = sum(1 for _, a in results if a["status"] == "analyzed")
    print(f"\n[*] Batch complete: {ok}/{total} papers analyzed.")
    return results


# --------------------------------------------------------------------------- #
# CLI test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys

    backend_arg = sys.argv[1] if len(sys.argv) > 1 else LLM_BACKEND
    print(f"Testing with backend: {backend_arg}\n")

    test_paper = {
        "paper_id": "2303.08774",
        "title": "GPT-4 Technical Report",
        "authors": "OpenAI",
        "published_date": "2023-03-15",
        "summary": (
            "We report the development of GPT-4, a large-scale, multimodal model which can accept "
            "image and text inputs and produce text outputs. GPT-4 exhibits human-level performance "
            "on various professional and academic benchmarks, including passing a simulated bar exam "
            "with a score around the top 10% of test takers."
        ),
        "url": "https://arxiv.org/abs/2303.08774",
        "source": "arxiv",
    }

    result = analyze_paper(test_paper, backend=backend_arg)
    print("\n--- Analysis Result ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))
