"""
notion_client.py
Handles Notion API integration for Literature Integrator:
  - Finds today's daily standup page in the configured database
  - Creates a 'literature_日期' child page under it with structured analysis blocks
  - Falls back to creating a standalone page in the database if no daily page found
"""
import os
import json
import requests
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

TODAY_STR = date.today().strftime("%Y-%m-%d")   # e.g. 2026-05-21
TODAY_DISPLAY = date.today().strftime("%Y/%m/%d")


# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #

def _get(endpoint: str, params: dict = None) -> dict:
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(endpoint: str, payload: dict) -> dict:
    resp = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _patch(endpoint: str, payload: dict) -> dict:
    resp = requests.patch(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------- #
# Helpers for building Notion blocks
# --------------------------------------------------------------------------- #

def _rich_text(text: str, bold: bool = False, color: str = "default") -> dict:
    return {
        "type": "text",
        "text": {"content": text[:2000]},   # Notion 2000 char limit per rich_text segment
        "annotations": {"bold": bold, "color": color},
    }


def _heading2(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [_rich_text(text, bold=True)]},
    }


def _heading3(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": [_rich_text(text)]},
    }


def _paragraph(text: str, color: str = "default") -> dict:
    # Notion limits paragraph to 2000 chars; split if needed (we'll just truncate for blocks)
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [_rich_text(text[:2000], color=color)]},
    }


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [_rich_text(text[:2000])]},
    }


def _callout(text: str, emoji: str = "📌", color: str = "gray_background") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [_rich_text(text[:2000])],
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color,
        },
    }


def _toggle(title: str, children: list) -> dict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [_rich_text(title, bold=True)],
            "children": children,
        },
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


# --------------------------------------------------------------------------- #
# Build blocks for a single paper
# --------------------------------------------------------------------------- #

def _paper_blocks(paper, idx: int) -> list:
    """Generate a set of blocks representing one paper's analysis."""
    title = paper.get("title", "Unknown Title")
    authors = paper.get("authors", "")
    url = paper.get("url", "")
    source = paper.get("source", "").upper()
    published_date = paper.get("published_date", "")
    llm_summary = paper.get("llm_summary") or paper.get("summary", "")
    code_available = paper.get("code_available", "UNKNOWN")
    code_url = paper.get("code_url", "")
    data_available = paper.get("data_available", "UNKNOWN")
    data_url = paper.get("data_url", "")
    theory = paper.get("theory_assumptions", "")
    motivation = paper.get("exp_motivation", "")
    sota = paper.get("sota_comparison", "")

    # Emoji map
    source_emoji = {"ARXIV": "📄", "BIORXIV": "🧬", "MEDRXIV": "🏥"}.get(source, "📑")
    code_emoji = {"YES": "✅", "NO": "❌", "PARTIAL": "🔶", "UNKNOWN": "❓"}.get(code_available, "❓")
    data_emoji = {"YES": "✅", "NO": "❌", "PARTIAL": "🔶", "UNKNOWN": "❓"}.get(data_available, "❓")

    blocks = [
        _heading3(f"{source_emoji} {idx}. {title}"),
        _paragraph(f"📅 {published_date} | 來源: {source} | 作者: {authors[:120]}", color="gray"),
        _paragraph(f"🔗 {url}", color="blue"),
        _callout(llm_summary[:1800] if llm_summary else "（尚未分析）", emoji="💡", color="blue_background"),
    ]

    # Code & Data availability
    code_line = f"{code_emoji} 程式碼: {code_available}"
    if code_url:
        code_line += f" | {code_url}"
    data_line = f"{data_emoji} 資料集: {data_available}"
    if data_url:
        data_line += f" | {data_url}"
    blocks.append(_bullet(code_line))
    blocks.append(_bullet(data_line))

    # Toggle: Theory, Motivation, SOTA (only if analyzed)
    if theory:
        blocks.append(_toggle("💭 理論假設", [_paragraph(theory[:2000])]))
    if motivation:
        blocks.append(_toggle("🎯 實驗動機", [_paragraph(motivation[:2000])]))
    if sota:
        blocks.append(_toggle("🏆 SOTA 比較", [_paragraph(sota[:2000])]))

    blocks.append(_divider())
    return blocks


# --------------------------------------------------------------------------- #
# Find today's daily page in the Notion database
# --------------------------------------------------------------------------- #

def find_today_daily_page() -> str | None:
    """
    Search the configured Notion database for a page representing today's daily standup.
    Matches pages whose title contains today's date (YYYY-MM-DD or YY/MM/DD format)
    and contains '_daily' or 'daily' (case-insensitive).
    Returns the page_id string or None.
    """
    if not NOTION_DATABASE_ID:
        print("[!] NOTION_DATABASE_ID not configured.")
        return None

    payload = {
        "filter": {
            "property": "title",
            "title": {"contains": TODAY_STR},
        },
        "page_size": 10,
    }

    try:
        data = _post(f"/databases/{NOTION_DATABASE_ID}/query", payload)
        results = data.get("results", [])

        for page in results:
            # Check page title
            title_prop = page.get("properties", {}).get("Name") or \
                         page.get("properties", {}).get("title") or \
                         page.get("properties", {}).get("Title", {})

            # Navigate to title rich_text
            title_content = ""
            if title_prop:
                for key, val in title_prop.items():
                    if isinstance(val, list):
                        for rt in val:
                            if isinstance(rt, dict):
                                title_content += rt.get("plain_text", "")

            # Must contain 'daily' (case-insensitive)
            if "daily" in title_content.lower():
                print(f"[*] Found today's daily page: {title_content!r} ({page['id']})")
                return page["id"]

        print(f"[*] No daily page found for {TODAY_STR}.")
        return None

    except Exception as e:
        print(f"[!] Error searching Notion database: {e}")
        return None


# --------------------------------------------------------------------------- #
# Create literature child page under daily standup page
# --------------------------------------------------------------------------- #

def create_literature_subpage(parent_page_id: str, papers: list, today_date: str = None) -> str | None:
    """
    Create a child page named 'literature_日期' under the given parent page.
    Populates it with structured blocks for each paper.
    Returns the new page URL or None on failure.
    """
    if not today_date:
        today_date = TODAY_STR

    page_title = f"literature_{today_date}"
    analyzed = [p for p in papers if (p.get("status") == "analyzed" or p.get("llm_summary"))]
    pending = [p for p in papers if p not in analyzed]

    print(f"[*] Creating Notion child page '{page_title}' under parent {parent_page_id}...")
    print(f"    Analyzed: {len(analyzed)}, Pending: {len(pending)}")

    # Build all blocks
    header_blocks = [
        _heading2(f"📚 文獻整合日報 — {today_date}"),
        _callout(
            f"今日共收錄 {len(papers)} 篇文獻，其中 {len(analyzed)} 篇已完成 AI 分析，{len(pending)} 篇待分析。",
            emoji="📊",
            color="green_background",
        ),
        _divider(),
    ]

    paper_blocks = []
    for i, paper in enumerate(papers, 1):
        paper_blocks.extend(_paper_blocks(paper, i))

    # Notion API limits 100 blocks per append_children call
    # Split into batches
    all_blocks = header_blocks + paper_blocks

    try:
        # Create the page with initial content (first 100 blocks)
        page_payload = {
            "parent": {"page_id": parent_page_id},
            "icon": {"type": "emoji", "emoji": "📚"},
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": page_title}}]
                }
            },
            "children": all_blocks[:100],
        }

        new_page = _post("/pages", page_payload)
        new_page_id = new_page["id"]
        page_url = new_page.get("url", f"https://notion.so/{new_page_id.replace('-', '')}")

        # Append remaining blocks in batches
        remaining = all_blocks[100:]
        while remaining:
            batch = remaining[:100]
            remaining = remaining[100:]
            _patch(f"/blocks/{new_page_id}/children", {"children": batch})

        print(f"  ✅ Notion page created: {page_url}")
        return page_url

    except Exception as e:
        print(f"  ❌ Error creating Notion child page: {e}")
        return None


# --------------------------------------------------------------------------- #
# Fallback: create standalone page in database
# --------------------------------------------------------------------------- #

def create_literature_db_page(papers: list, today_date: str = None) -> str | None:
    """
    Fallback method: create a new page directly inside the Notion database
    (not as a child of any daily page) when no daily standup page is found.
    """
    if not today_date:
        today_date = TODAY_STR
    if not NOTION_DATABASE_ID:
        print("[!] NOTION_DATABASE_ID not configured — cannot create DB page.")
        return None

    page_title = f"literature_{today_date}"
    print(f"[*] Creating standalone Notion DB page '{page_title}' (fallback)...")

    analyzed = [p for p in papers if (p.get("status") == "analyzed" or p.get("llm_summary"))]
    pending_count = len(papers) - len(analyzed)

    header_blocks = [
        _callout(
            f"今日共收錄 {len(papers)} 篇文獻，其中 {len(analyzed)} 篇已分析，{pending_count} 篇待分析。",
            emoji="📊",
            color="green_background",
        ),
        _divider(),
    ]

    paper_blocks = []
    for i, paper in enumerate(papers, 1):
        paper_blocks.extend(_paper_blocks(paper, i))

    all_blocks = header_blocks + paper_blocks

    try:
        page_payload = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "icon": {"type": "emoji", "emoji": "📚"},
            "properties": {
                "Name": {
                    "title": [{"type": "text", "text": {"content": page_title}}]
                }
            },
            "children": all_blocks[:100],
        }

        new_page = _post("/pages", page_payload)
        new_page_id = new_page["id"]
        page_url = new_page.get("url", f"https://notion.so/{new_page_id.replace('-', '')}")

        remaining = all_blocks[100:]
        while remaining:
            batch = remaining[:100]
            remaining = remaining[100:]
            _patch(f"/blocks/{new_page_id}/children", {"children": batch})

        print(f"  ✅ Standalone Notion page created: {page_url}")
        return page_url

    except Exception as e:
        print(f"  ❌ Error creating standalone Notion page: {e}")
        return None


# --------------------------------------------------------------------------- #
# Main dispatch
# --------------------------------------------------------------------------- #

def push_to_notion(papers: list, today_date: str = None) -> str | None:
    """
    Find today's daily page; if found, create child page; otherwise create standalone page.
    Returns the created page URL or None.
    """
    if not today_date:
        today_date = TODAY_STR

    daily_page_id = find_today_daily_page()

    if daily_page_id:
        return create_literature_subpage(daily_page_id, papers, today_date)
    else:
        print("[*] Falling back to standalone DB page creation.")
        return create_literature_db_page(papers, today_date)


# --------------------------------------------------------------------------- #
# CLI test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    # Test with a mock paper
    mock_papers = [
        {
            "paper_id": "2303.08774",
            "title": "GPT-4 Technical Report",
            "authors": "OpenAI",
            "published_date": "2023-03-15",
            "summary": "We report the development of GPT-4, a large-scale, multimodal model...",
            "url": "https://arxiv.org/abs/2303.08774",
            "source": "arxiv",
            "status": "analyzed",
            "llm_summary": "GPT-4 是一個支援圖文輸入的大型語言模型，在多項專業考試中達到人類頂尖水準。本文詳述其開發過程與對齊挑戰。",
            "code_available": "NO",
            "code_url": "",
            "data_available": "NO",
            "data_url": "",
            "theory_assumptions": "模型規模化定律（Scaling Law）在大型多模態模型中仍然有效",
            "exp_motivation": "解決現有 LLM 在複雜推理與多模態理解方面的不足",
            "sota_comparison": "在 MMLU、HumanEval 等基準中超越 GPT-3.5 和其他開源模型",
        }
    ]

    url = push_to_notion(mock_papers)
    if url:
        print(f"\n✅ Notion page URL: {url}")
    else:
        print("\n❌ Failed to create Notion page")
