"""
daily_job.py
Orchestrates the full daily literature pipeline:
  1. Crawl new papers from arXiv, bioRxiv, medRxiv
  2. Insert into SQLite database
  3. Auto-analyze today's new papers with Gemini
  4. Push structured summary to Notion
  5. Send LINE and Email notifications
Can be run directly (python scheduler/daily_job.py) or via Windows Task Scheduler.
"""
import os
import sys
import time
import argparse
from datetime import date, datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from database.db_manager import init_db, add_paper, update_analysis, get_all_papers
from crawlers.arxiv_crawler import fetch_arxiv_papers
from crawlers.biorxiv_crawler import fetch_biorxiv_papers
from processors.llm_analyzer import analyze_paper
from integrators.notion_client import push_to_notion
from integrators.notifier import send_all_notifications

TODAY_STR = date.today().strftime("%Y-%m-%d")

# --------------------------------------------------------------------------- #
# Step 1: Crawl
# --------------------------------------------------------------------------- #

def run_crawl(daily_mode: bool = True) -> list:
    """Crawl papers and return list of newly inserted paper dicts."""
    print(f"\n{'='*60}")
    print(f"[STEP 1] Crawling papers | mode={'daily' if daily_mode else 'historical'}")
    print(f"{'='*60}\n")

    years_list = [str(y) for y in range(2020, 2027)]
    new_papers = []

    # --- arXiv ---
    try:
        print("[*] Crawling arXiv...")
        arxiv_papers = fetch_arxiv_papers(years_list=years_list, max_results=50, daily_mode=daily_mode)
        inserted = 0
        for p in arxiv_papers:
            if add_paper(p):
                new_papers.append(p)
                inserted += 1
        print(f"  ✅ arXiv: {len(arxiv_papers)} fetched, {inserted} new inserted")
    except Exception as e:
        print(f"  ❌ arXiv crawl failed: {e}")

    # --- bioRxiv ---
    try:
        print("[*] Crawling bioRxiv/medRxiv...")
        biorxiv_papers = fetch_biorxiv_papers(years_list=years_list, max_results=50, daily_mode=daily_mode)
        inserted = 0
        for p in biorxiv_papers:
            if add_paper(p):
                new_papers.append(p)
                inserted += 1
        print(f"  ✅ bioRxiv/medRxiv: {len(biorxiv_papers)} fetched, {inserted} new inserted")
    except Exception as e:
        print(f"  ❌ bioRxiv crawl failed: {e}")

    print(f"\n[*] Total new papers inserted: {len(new_papers)}")
    return new_papers


# --------------------------------------------------------------------------- #
# Step 2: Analyze today's new papers
# --------------------------------------------------------------------------- #

def run_analysis(papers: list, max_analyze: int = 20, delay: float = 2.0) -> list:
    """Analyze newly crawled papers using Gemini. Returns list of paper dicts with analysis."""
    if not papers:
        print("\n[STEP 2] No new papers to analyze — skipping LLM analysis.")
        return []

    print(f"\n{'='*60}")
    print(f"[STEP 2] Analyzing {min(len(papers), max_analyze)} papers with Gemini")
    print(f"{'='*60}\n")

    analyzed_papers = []
    for i, paper in enumerate(papers[:max_analyze], 1):
        paper_id = paper.get("paper_id", "unknown")
        print(f"  [{i}/{min(len(papers), max_analyze)}] Analyzing: {paper.get('title', '')[:60]}")

        analysis = analyze_paper(paper)
        if update_analysis(paper_id, analysis):
            # Merge analysis into paper dict for notification
            merged = {**paper, **analysis}
            analyzed_papers.append(merged)
            print(f"    ✅ Analysis saved | status={analysis['status']}")
        else:
            print(f"    ⚠️  Failed to save analysis for {paper_id}")

        if i < min(len(papers), max_analyze):
            time.sleep(delay)

    return analyzed_papers


# --------------------------------------------------------------------------- #
# Step 3: Compile today's papers for report
# --------------------------------------------------------------------------- #

def compile_today_papers() -> list:
    """Get all papers from today for the report."""
    all_papers = get_all_papers()
    today_papers = [
        {
            "paper_id": p.paper_id,
            "title": p.title,
            "authors": p.authors,
            "published_date": p.published_date,
            "summary": p.summary,
            "url": p.url,
            "source": p.source,
            "status": p.status,
            "llm_summary": p.llm_summary,
            "code_available": p.code_available,
            "code_url": p.code_url,
            "data_available": p.data_available,
            "data_url": p.data_url,
            "theory_assumptions": p.theory_assumptions,
            "exp_motivation": p.exp_motivation,
            "sota_comparison": p.sota_comparison,
        }
        for p in all_papers
        if p.published_date and p.published_date >= TODAY_STR
    ]

    # If no today's papers (e.g., weekend/holiday), take latest 10 for the report
    if not today_papers:
        print("[*] No papers with today's date found — using 10 most recent papers for report.")
        today_papers = [
            {
                "paper_id": p.paper_id,
                "title": p.title,
                "authors": p.authors,
                "published_date": p.published_date,
                "summary": p.summary,
                "url": p.url,
                "source": p.source,
                "status": p.status,
                "llm_summary": p.llm_summary,
                "code_available": p.code_available,
                "code_url": p.code_url,
                "data_available": p.data_available,
                "data_url": p.data_url,
                "theory_assumptions": p.theory_assumptions,
                "exp_motivation": p.exp_motivation,
                "sota_comparison": p.sota_comparison,
            }
            for p in all_papers[:10]
        ]

    return today_papers


# --------------------------------------------------------------------------- #
# Step 4: Notion + Notifications
# --------------------------------------------------------------------------- #

def run_notifications(papers: list) -> str:
    """Push to Notion and send LINE + Email. Returns Notion URL."""
    print(f"\n{'='*60}")
    print(f"[STEP 3] Pushing to Notion & sending notifications")
    print(f"{'='*60}\n")

    notion_url = push_to_notion(papers)
    print(f"  Notion URL: {notion_url}")

    send_all_notifications(papers, notion_url=notion_url or "")
    return notion_url or ""


# --------------------------------------------------------------------------- #
# Main job orchestrator
# --------------------------------------------------------------------------- #

def run_daily_job(daily_mode: bool = True, max_analyze: int = 20, dry_run: bool = False):
    """Run the complete daily literature pipeline."""
    start_time = datetime.now()
    print(f"\n{'#'*60}")
    print(f"# Literature Integrator — Daily Job")
    print(f"# Date: {TODAY_STR}  |  Mode: {'daily' if daily_mode else 'historical'}")
    print(f"# Dry Run: {dry_run}")
    print(f"{'#'*60}\n")

    # Initialize DB (idempotent)
    init_db()

    if not dry_run:
        # Step 1: Crawl
        new_papers = run_crawl(daily_mode=daily_mode)

        # Step 2: Analyze
        run_analysis(new_papers, max_analyze=max_analyze)
    else:
        print("[DRY RUN] Skipping crawl and analysis.")

    # Step 3: Compile report papers (today's papers)
    report_papers = compile_today_papers()
    print(f"\n[*] Report will include {len(report_papers)} papers.")

    if not report_papers:
        print("[!] No papers found for report — skipping notifications.")
        return

    if not dry_run:
        # Step 4: Notify
        run_notifications(report_papers)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'#'*60}")
    print(f"# Daily Job Complete | Elapsed: {elapsed:.1f}s")
    print(f"{'#'*60}\n")


# --------------------------------------------------------------------------- #
# CLI entrypoint
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Literature Integrator Daily Pipeline")
    parser.add_argument(
        "--mode",
        choices=["daily", "historical"],
        default="daily",
        help="Crawl mode: 'daily' (last 7 days) or 'historical' (2020–2026)",
    )
    parser.add_argument(
        "--max-analyze",
        type=int,
        default=20,
        help="Maximum number of new papers to analyze in one run (default: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip crawling and analysis; only compile report and send notifications",
    )

    args = parser.parse_args()
    run_daily_job(
        daily_mode=(args.mode == "daily"),
        max_analyze=args.max_analyze,
        dry_run=args.dry_run,
    )
