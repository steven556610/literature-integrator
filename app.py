"""
app.py  —  Literature Integrator  |  Premium Streamlit Dashboard
Dark-mode glassmorphic design with:
  - KPI metric cards
  - Interactive paper grid with AI analysis drawer
  - URL submission & on-demand analysis
  - Manual crawl / daily job triggers
  - Source & status filter panels
"""
import os
import sys
import json
import time
from datetime import date, datetime

import streamlit as st
import pandas as pd

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# ------------------------------------------------------------------ #
# Streamlit page config (MUST be first st call)
# ------------------------------------------------------------------ #
st.set_page_config(
    page_title="Literature Integrator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# Global CSS — Dark glassmorphic theme
# ------------------------------------------------------------------ #
st.markdown("""
<style>
/* ===== Base overrides ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background: #080d1a;
}

/* ===== Sidebar ===== */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1224 0%, #080d1a 100%);
    border-right: 1px solid #1e2d4a;
}
[data-testid="stSidebar"] .sidebar-content {
    background: transparent;
}

/* ===== Main header ===== */
.main-header {
    background: linear-gradient(135deg, #0d1224 0%, #1a1040 50%, #0d1a1f 100%);
    border: 1px solid #2d3a5e;
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.main-header::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at 20% 50%, rgba(99,102,241,0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 50%, rgba(16,185,129,0.05) 0%, transparent 50%);
    pointer-events: none;
}
.main-title {
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, #818cf8, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.main-subtitle {
    color: #64748b;
    font-size: 13px;
    margin: 6px 0 0;
}

/* ===== KPI Cards ===== */
.kpi-card {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    border: 1px solid #1e3a5f;
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
    cursor: default;
}
.kpi-card:hover {
    transform: translateY(-2px);
    border-color: #818cf8;
    box-shadow: 0 8px 32px rgba(99,102,241,0.15);
}
.kpi-value {
    font-size: 36px;
    font-weight: 700;
    line-height: 1;
}
.kpi-label {
    font-size: 11px;
    color: #64748b;
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ===== Paper cards ===== */
.paper-card {
    background: linear-gradient(135deg, #0f172a, #0d1628);
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
    transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
    position: relative;
}
.paper-card:hover {
    border-color: #6366f1;
    box-shadow: 0 4px 24px rgba(99,102,241,0.12);
    transform: translateY(-1px);
}
.paper-title {
    font-size: 14px;
    font-weight: 600;
    color: #c7d2fe;
    line-height: 1.4;
    margin-bottom: 6px;
}
.paper-meta {
    font-size: 11px;
    color: #475569;
    margin-bottom: 8px;
}
.paper-summary {
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.6;
}
.source-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.03em;
}
.badge-arxiv { background: rgba(99,102,241,0.2); color: #818cf8; border: 1px solid rgba(99,102,241,0.3); }
.badge-biorxiv { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }
.badge-medrxiv { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }
.status-analyzed { color: #34d399; font-size: 11px; }
.status-pending { color: #fbbf24; font-size: 11px; }
.status-failed { color: #f87171; font-size: 11px; }

/* ===== Analysis blocks ===== */
.analysis-block {
    background: #0d1628;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 8px 0;
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.6;
}
.analysis-label {
    font-size: 11px;
    font-weight: 600;
    color: #818cf8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}

/* ===== URL submit box ===== */
.submit-section {
    background: linear-gradient(135deg, #0f172a, #1a1040);
    border: 1px solid #2d3a5e;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 20px;
}

/* ===== Hide Streamlit chrome ===== */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.stDeployButton {display: none;}

/* ===== Metrics override ===== */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    border: 1px solid #1e3a5f;
    border-radius: 14px;
    padding: 16px;
}

/* ===== Tabs ===== */
.stTabs [data-baseweb="tab-list"] {
    background: #0d1224;
    border-radius: 8px;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    color: #64748b;
    font-size: 13px;
    border-radius: 6px;
}
.stTabs [aria-selected="true"] {
    background: rgba(99,102,241,0.15) !important;
    color: #818cf8 !important;
}

/* ===== Buttons ===== */
.stButton > button {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    transition: opacity 0.2s, transform 0.15s;
}
.stButton > button:hover {
    opacity: 0.9;
    transform: translateY(-1px);
}

/* ===== Inputs ===== */
.stTextInput > div > div > input {
    background: #0f172a;
    border: 1px solid #2d3a5e;
    color: #e2e8f0;
    border-radius: 8px;
}
.stSelectbox > div > div {
    background: #0f172a;
    border: 1px solid #2d3a5e;
    color: #e2e8f0;
}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ #
# Lazy imports (DB and processors — avoid import errors at startup)
# ------------------------------------------------------------------ #

@st.cache_resource
def get_db():
    from database.db_manager import init_db, get_all_papers, add_paper, update_analysis, delete_paper
    init_db()
    return {
        "get_all_papers": get_all_papers,
        "add_paper": add_paper,
        "update_analysis": update_analysis,
        "delete_paper": delete_paper,
    }


# ------------------------------------------------------------------ #
# Helper: load papers as list of dicts
# ------------------------------------------------------------------ #

def load_papers(status=None, source=None, limit=None):
    db = get_db()
    raw = db["get_all_papers"](status=status, source=source, limit=limit)
    papers = []
    for p in raw:
        papers.append({
            "id": p.id,
            "paper_id": p.paper_id,
            "title": p.title or "",
            "authors": p.authors or "",
            "published_date": p.published_date or "",
            "summary": p.summary or "",
            "url": p.url or "",
            "source": p.source or "",
            "status": p.status or "pending",
            "analyzed_at": p.analyzed_at or "",
            "llm_summary": p.llm_summary or "",
            "code_available": p.code_available or "UNKNOWN",
            "code_url": p.code_url or "",
            "data_available": p.data_available or "UNKNOWN",
            "data_url": p.data_url or "",
            "theory_assumptions": p.theory_assumptions or "",
            "exp_motivation": p.exp_motivation or "",
            "sota_comparison": p.sota_comparison or "",
        })
    return papers


# ------------------------------------------------------------------ #
# Sidebar
# ------------------------------------------------------------------ #

with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:16px 0 8px">
        <div style="font-size:36px">📚</div>
        <div style="font-size:15px;font-weight:700;color:#818cf8;margin-top:4px">Literature Integrator</div>
        <div style="font-size:11px;color:#475569">AI-Powered Research Hub</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # --- Filters ---
    st.markdown("**🔍 篩選器**")
    filter_status = st.selectbox(
        "分析狀態",
        ["全部", "已分析 (analyzed)", "待分析 (pending)", "失敗 (failed)"],
        key="filter_status"
    )
    filter_source = st.selectbox(
        "來源",
        ["全部", "arXiv", "bioRxiv", "medRxiv"],
        key="filter_source"
    )
    search_query = st.text_input("搜尋標題 / 作者", placeholder="輸入關鍵字...", key="search_query")

    st.divider()

    # --- LLM Backend ---
    st.markdown("**🧠 LLM 分析後端**")
    llm_backend = st.selectbox(
        "選擇模型",
        ["qwen14b", "qwen7b", "gemini"],
        format_func=lambda x: {
            "qwen14b": "🦙 Qwen2.5-14B (本地 · 高精度)",
            "qwen7b":  "🦙 Qwen2.5-7B  (本地 · 快速)",
            "gemini":  "✨ Gemini 2.0 Flash (雲端)",
        }[x],
        key="llm_backend",
    )
    # Show Ollama status
    try:
        r = __import__('requests').get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            st.markdown('<div style="color:#34d399;font-size:11px">● Ollama 運作中</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#f87171;font-size:11px">● Ollama 無回應</div>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<div style="color:#f87171;font-size:11px">● Ollama 未啟動</div>', unsafe_allow_html=True)

    st.divider()

    # --- Quick Actions ---
    st.markdown("**⚡ 快速操作**")

    if st.button("🔄 重新整理資料", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if st.button("📅 執行今日爬取", use_container_width=True):
        with st.spinner("爬取中..."):
            try:
                from crawlers.arxiv_crawler import fetch_arxiv_papers
                from crawlers.biorxiv_crawler import fetch_biorxiv_papers
                db = get_db()
                years = [str(y) for y in range(2020, 2027)]
                ax = fetch_arxiv_papers(years_list=years, max_results=30, daily_mode=True)
                bx = fetch_biorxiv_papers(years_list=years, max_results=30, daily_mode=True)
                added = sum(1 for p in ax + bx if db["add_paper"](p))
                st.success(f"新增 {added} 篇文獻")
                st.cache_data.clear()
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"爬取失敗: {e}")

    if st.button("🤖 執行完整日報任務", use_container_width=True):
        with st.spinner("執行日報任務中... (可能需要數分鐘)"):
            try:
                import subprocess
                py_exe = r"D:\miniconda3\envs\literature_integrator\python.exe"
                result = subprocess.run(
                    [py_exe, "scheduler/daily_job.py", "--mode", "daily", "--max-analyze", "15"],
                    capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)),
                    env={**os.environ, "LLM_BACKEND": llm_backend}
                )
                if result.returncode == 0:
                    st.success("日報任務完成！")
                else:
                    st.error(f"任務失敗:\n{result.stderr[:500]}")
            except Exception as e:
                st.error(f"錯誤: {e}")

    st.divider()
    st.markdown(f"<div style='font-size:10px;color:#334155;text-align:center'>最後更新: {datetime.now().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ #
# Header
# ------------------------------------------------------------------ #

st.markdown(f"""
<div class="main-header">
    <h1 class="main-title">📚 Literature Integrator</h1>
    <p class="main-subtitle">智慧文獻整合平台 · 藥物 × 癌症疫苗 × AI × NLP · {date.today().strftime('%Y/%m/%d')}</p>
</div>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ #
# Load data
# ------------------------------------------------------------------ #

@st.cache_data(ttl=60)
def cached_load_papers():
    return load_papers()

all_papers = cached_load_papers()

# Apply filters
def apply_filters(papers):
    filtered = papers

    # Status filter
    status_map = {
        "已分析 (analyzed)": "analyzed",
        "待分析 (pending)": "pending",
        "失敗 (failed)": "failed",
    }
    if filter_status != "全部":
        s = status_map.get(filter_status, filter_status)
        filtered = [p for p in filtered if p["status"] == s]

    # Source filter
    source_map = {"arXiv": "arxiv", "bioRxiv": "biorxiv", "medRxiv": "medrxiv"}
    if filter_source != "全部":
        src = source_map.get(filter_source, filter_source.lower())
        filtered = [p for p in filtered if p["source"] == src]

    # Search
    if search_query.strip():
        q = search_query.lower()
        filtered = [p for p in filtered if q in p["title"].lower() or q in p["authors"].lower()]

    return filtered

papers = apply_filters(all_papers)


# ------------------------------------------------------------------ #
# KPI metrics
# ------------------------------------------------------------------ #

total = len(all_papers)
analyzed = sum(1 for p in all_papers if p["status"] == "analyzed")
pending = sum(1 for p in all_papers if p["status"] == "pending")
failed = sum(1 for p in all_papers if p["status"] == "failed")
arxiv_count = sum(1 for p in all_papers if p["source"] == "arxiv")
biorxiv_count = sum(1 for p in all_papers if p["source"] == "biorxiv")
medrxiv_count = sum(1 for p in all_papers if p["source"] == "medrxiv")

col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

with col1:
    st.metric("📑 總文獻數", total)
with col2:
    st.metric("✅ 已分析", analyzed, delta=f"{analyzed/total*100:.0f}%" if total else None)
with col3:
    st.metric("⏳ 待分析", pending)
with col4:
    st.metric("❌ 失敗", failed)
with col5:
    st.metric("arXiv", arxiv_count)
with col6:
    st.metric("bioRxiv", biorxiv_count)
with col7:
    st.metric("medRxiv", medrxiv_count)

st.divider()


# ------------------------------------------------------------------ #
# URL submission box
# ------------------------------------------------------------------ #

st.markdown("### 🔗 新增文獻連結")
with st.container():
    col_url, col_btn = st.columns([4, 1])
    with col_url:
        submitted_url = st.text_input(
            "貼上文獻 URL（支援 arXiv、bioRxiv、medRxiv、DOI）",
            placeholder="https://arxiv.org/abs/2303.08774",
            label_visibility="collapsed",
            key="url_input"
        )
    with col_btn:
        analyze_after = st.toggle("立即分析", value=True, key="analyze_toggle")
        add_clicked = st.button("➕ 新增", use_container_width=True, key="add_paper_btn")

    if add_clicked and submitted_url.strip():
        with st.spinner(f"解析中: {submitted_url[:60]}..."):
            try:
                from crawlers.paper_resolver import resolve_paper
                paper_data = resolve_paper(submitted_url.strip())
                if paper_data:
                    db = get_db()
                    was_new = db["add_paper"](paper_data)
                    if was_new:
                        st.success(f"已加入資料庫: **{paper_data['title'][:80]}**")
                        if analyze_after:
                            backend_label = {"qwen14b": "Qwen2.5-14B", "qwen7b": "Qwen2.5-7B", "gemini": "Gemini 2.0 Flash"}.get(llm_backend, llm_backend)
                            with st.spinner(f"使用 {backend_label} 進行 AI 分析中..."):
                                from processors.llm_analyzer import analyze_paper as analyze_fn
                                analysis = analyze_fn(paper_data, backend=llm_backend)
                                db["update_analysis"](paper_data["paper_id"], analysis)
                                if analysis["status"] == "analyzed":
                                    st.success(f"AI 分析完成！(模型: {analysis.get('backend', llm_backend)})")
                                    try:
                                        from integrators.notifier import send_all_notifications
                                        paper_data.update(analysis)
                                        send_all_notifications([paper_data])
                                    except Exception as notify_err:
                                        st.warning(f"通知發送失敗: {notify_err}")
                                else:
                                    st.warning(f"分析未完成: {analysis.get('raw_analysis','')[:120]}")
                    else:
                        st.info("此文獻已存在於資料庫中")
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("無法解析此連結，請確認 URL 格式")
            except Exception as e:
                st.error(f"錯誤: {e}")

st.divider()


# ------------------------------------------------------------------ #
# Paper list with analysis viewer
# ------------------------------------------------------------------ #

st.markdown(f"### 📋 文獻列表 <span style='color:#475569;font-size:14px;font-weight:400'>（共 {len(papers)} 篇）</span>", unsafe_allow_html=True)

if not papers:
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;color:#475569">
        <div style="font-size:48px;margin-bottom:16px">📭</div>
        <div style="font-size:16px;font-weight:600;color:#64748b">尚無符合條件的文獻</div>
        <div style="font-size:13px;margin-top:8px">請調整篩選條件，或使用「執行今日爬取」按鈕載入文獻</div>
    </div>
    """, unsafe_allow_html=True)
else:
    # Pagination
    ITEMS_PER_PAGE = 15
    total_pages = max(1, (len(papers) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if "page_num" not in st.session_state:
        st.session_state.page_num = 1

    # Keep page in bounds
    st.session_state.page_num = min(st.session_state.page_num, total_pages)

    page_papers = papers[(st.session_state.page_num - 1) * ITEMS_PER_PAGE:
                         st.session_state.page_num * ITEMS_PER_PAGE]

    for paper in page_papers:
        source = paper["source"].upper()
        source_class = {"ARXIV": "badge-arxiv", "BIORXIV": "badge-biorxiv", "MEDRXIV": "badge-medrxiv"}.get(source, "")
        status_class = {"analyzed": "status-analyzed", "pending": "status-pending", "failed": "status-failed"}.get(paper["status"], "")
        status_text = {"analyzed": "✅ 已分析", "pending": "⏳ 待分析", "failed": "❌ 分析失敗"}.get(paper["status"], paper["status"])
        code_icon = {"YES": "✅", "NO": "❌", "PARTIAL": "🔶", "UNKNOWN": "❓"}.get(paper["code_available"], "❓")
        data_icon = {"YES": "✅", "NO": "❌", "PARTIAL": "🔶", "UNKNOWN": "❓"}.get(paper["data_available"], "❓")

        with st.expander(f"**{paper['title'][:90]}{'...' if len(paper['title']) > 90 else ''}**", expanded=False):
            # Paper metadata row
            col_meta, col_actions = st.columns([3, 1])
            with col_meta:
                st.markdown(f"""
                <span class="source-badge {source_class}">{source}</span>&nbsp;
                <span style="color:#475569;font-size:11px">{paper['published_date']}</span>&nbsp;
                <span class="{status_class}">{status_text}</span>
                <br><span style="color:#64748b;font-size:12px">👤 {paper['authors'][:100]}</span>
                <br><a href="{paper['url']}" target="_blank" style="color:#818cf8;font-size:11px">🔗 {paper['url'][:60]}...</a>
                """, unsafe_allow_html=True)
            with col_actions:
                if paper["status"] != "analyzed":
                    if st.button("🤖 分析此文獻", key=f"analyze_{paper['paper_id']}", use_container_width=True):
                        backend_label = {"qwen14b": "Qwen2.5-14B", "qwen7b": "Qwen2.5-7B", "gemini": "Gemini"}.get(llm_backend, llm_backend)
                        with st.spinner(f"[{backend_label}] 分析中..."):
                            try:
                                from processors.llm_analyzer import analyze_paper as analyze_fn
                                db = get_db()
                                analysis = analyze_fn(paper, backend=llm_backend)
                                db["update_analysis"](paper["paper_id"], analysis)
                                st.success(f"分析完成 [{analysis.get('backend', llm_backend)}]")
                                try:
                                    from integrators.notifier import send_all_notifications
                                    paper.update(analysis)
                                    send_all_notifications([paper])
                                except Exception as notify_err:
                                    st.warning(f"通知發送失敗: {notify_err}")
                                st.cache_data.clear()
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"分析失敗: {e}")
                if st.button("🗑️ 刪除", key=f"delete_{paper['paper_id']}", use_container_width=True):
                    db = get_db()
                    db["delete_paper"](paper["paper_id"])
                    st.cache_data.clear()
                    st.rerun()

            # Original abstract
            st.markdown("**📄 原始摘要**")
            st.markdown(f"""<div class="analysis-block">{paper['summary'][:800]}{'...' if len(paper['summary']) > 800 else ''}</div>""", unsafe_allow_html=True)
            
            if paper.get("translated_summary"):
                st.markdown("**🇹🇼 摘要繁中翻譯**")
                st.markdown(f"""<div class="analysis-block">{paper['translated_summary']}</div>""", unsafe_allow_html=True)

            # AI Analysis (only if analyzed)
            if paper["status"] == "analyzed":
                st.markdown("**🤖 AI 分析結果**")

                tab1, tab2, tab3, tab4, tab5 = st.tabs(
                    ["💡 中文摘要", "💭 理論假設", "🎯 實驗動機", "🏆 SOTA 比較", "💻 程式碼 & 資料"]
                )

                with tab1:
                    st.markdown(f"""<div class="analysis-block">{paper['llm_summary'] or '—'}</div>""", unsafe_allow_html=True)

                with tab2:
                    st.markdown(f"""<div class="analysis-block">{paper['theory_assumptions'] or '—'}</div>""", unsafe_allow_html=True)

                with tab3:
                    st.markdown(f"""<div class="analysis-block">{paper['exp_motivation'] or '—'}</div>""", unsafe_allow_html=True)

                with tab4:
                    st.markdown(f"""<div class="analysis-block">{paper['sota_comparison'] or '—'}</div>""", unsafe_allow_html=True)

                with tab5:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**程式碼** {code_icon} `{paper['code_available']}`")
                        if paper["code_url"]:
                            st.markdown(f"🔗 [{paper['code_url'][:50]}]({paper['code_url']})")
                    with c2:
                        st.markdown(f"**資料集** {data_icon} `{paper['data_available']}`")
                        if paper["data_url"]:
                            st.markdown(f"🔗 [{paper['data_url'][:50]}]({paper['data_url']})")

    # Pagination controls
    st.divider()
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("← 上一頁", disabled=st.session_state.page_num <= 1, use_container_width=True):
            st.session_state.page_num -= 1
            st.rerun()
    with col_info:
        st.markdown(f"<div style='text-align:center;color:#64748b;font-size:13px;padding-top:8px'>第 {st.session_state.page_num} / {total_pages} 頁</div>", unsafe_allow_html=True)
    with col_next:
        if st.button("下一頁 →", disabled=st.session_state.page_num >= total_pages, use_container_width=True):
            st.session_state.page_num += 1
            st.rerun()


# ------------------------------------------------------------------ #
# Charts section
# ------------------------------------------------------------------ #

if all_papers:
    st.divider()
    st.markdown("### 📊 統計分析")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        df_source = pd.DataFrame({
            "來源": ["arXiv", "bioRxiv", "medRxiv"],
            "數量": [arxiv_count, biorxiv_count, medrxiv_count]
        })
        st.bar_chart(df_source.set_index("來源"), color="#818cf8", height=200)
        st.caption("來源分布")

    with chart_col2:
        # Papers by year
        year_counts = {}
        for p in all_papers:
            yr = p["published_date"][:4] if p["published_date"] else "未知"
            year_counts[yr] = year_counts.get(yr, 0) + 1

        if year_counts:
            df_year = pd.DataFrame({"年份": list(year_counts.keys()), "數量": list(year_counts.values())})
            df_year = df_year.sort_values("年份")
            st.bar_chart(df_year.set_index("年份"), color="#34d399", height=200)
            st.caption("各年份文獻數量")
