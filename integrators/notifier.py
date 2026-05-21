"""
notifier.py
Sends daily literature summary via:
  1. Gmail SMTP HTML Email
  2. LINE Messaging API Push Message
"""
import os
import smtplib
import json
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")

# LINE Messaging API (Push Message)
LINE_ACCESS_TOKEN = os.getenv("LINE_ASSESS_TOKEN", "")  # original typo preserved
LINE_USER_ID = os.getenv("USER_ID", "")
LINE_API_URL = "https://api.line.me/v2/bot/message/push"

TODAY_STR = date.today().strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# HTML Email template builder
# --------------------------------------------------------------------------- #

def _build_email_html(papers: list, notion_url: str = "", dashboard_url: str = "http://localhost:8501") -> str:
    """Build a beautiful, responsive HTML email summarizing today's literature."""
    analyzed = [p for p in papers if p.get("status") == "analyzed"]
    sources = {}
    for p in papers:
        src = p.get("source", "unknown").upper()
        sources[src] = sources.get(src, 0) + 1

    color_map = {"ARXIV": "#6366f1", "BIORXIV": "#10b981", "MEDRXIV": "#f59e0b"}
    badge_parts = []
    for s, n in sources.items():
        bg = color_map.get(s, "#94a3b8")
        badge_parts.append(
            f'<span style="background:{bg};color:white;padding:2px 10px;'
            f'border-radius:12px;font-size:12px;font-weight:600">{s}: {n}</span>'
        )
    source_badges = " ".join(badge_parts)

    # Paper rows
    paper_rows = ""
    for i, p in enumerate(papers[:20], 1):  # Limit to 20 in email
        title = p.get("title", "Unknown")[:100]
        url = p.get("url", "#")
        source = p.get("source", "").upper()
        published = p.get("published_date", "")
        summary = p.get("llm_summary") or p.get("summary", "")
        summary = summary[:200] + "..." if len(summary) > 200 else summary
        code = p.get("code_available", "UNKNOWN")
        data = p.get("data_available", "UNKNOWN")
        status = p.get("status", "pending")

        source_color = {"ARXIV": "#6366f1", "BIORXIV": "#10b981", "MEDRXIV": "#f59e0b"}.get(source, "#94a3b8")
        code_icon = {"YES": "✅", "NO": "❌", "PARTIAL": "🔶", "UNKNOWN": "❓"}.get(code, "❓")
        data_icon = {"YES": "✅", "NO": "❌", "PARTIAL": "🔶", "UNKNOWN": "❓"}.get(data, "❓")
        status_color = "#10b981" if status == "analyzed" else "#f59e0b"

        paper_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:12px 8px;color:#94a3b8;font-size:12px;width:20px">{i}</td>
          <td style="padding:12px 8px">
            <a href="{url}" style="color:#818cf8;text-decoration:none;font-weight:600;font-size:13px">{title}</a>
            <br><span style="color:#64748b;font-size:11px">{published} &nbsp;|&nbsp;
            <span style="background:{source_color};color:white;padding:1px 6px;border-radius:8px;font-size:10px">{source}</span>
            &nbsp;|&nbsp; <span style="color:{status_color}">{status}</span></span>
            <br><span style="color:#94a3b8;font-size:12px;line-height:1.5">{summary}</span>
            <br><span style="font-size:11px;color:#64748b">{code_icon} Code &nbsp; {data_icon} Data</span>
          </td>
        </tr>"""

    notion_button = ""
    if notion_url:
        notion_button = f"""
        <a href="{notion_url}" style="display:inline-block;background:#818cf8;color:white;
           padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 4px;font-size:14px">
           📓 在 Notion 查看
        </a>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:'Segoe UI',Arial,sans-serif">
  <div style="max-width:700px;margin:0 auto;padding:20px">
    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:16px;padding:32px;margin-bottom:20px;text-align:center">
      <div style="font-size:40px;margin-bottom:8px">📚</div>
      <h1 style="margin:0;color:#e0e7ff;font-size:22px;font-weight:700">文獻整合日報</h1>
      <p style="margin:8px 0 0;color:#a5b4fc;font-size:14px">{TODAY_STR}</p>
    </div>

    <!-- Stats -->
    <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap">
      <div style="flex:1;min-width:130px;background:#1e293b;border-radius:12px;padding:16px;text-align:center;border:1px solid #334155">
        <div style="font-size:28px;font-weight:700;color:#818cf8">{len(papers)}</div>
        <div style="color:#64748b;font-size:12px">今日收錄</div>
      </div>
      <div style="flex:1;min-width:130px;background:#1e293b;border-radius:12px;padding:16px;text-align:center;border:1px solid #334155">
        <div style="font-size:28px;font-weight:700;color:#10b981">{len(analyzed)}</div>
        <div style="color:#64748b;font-size:12px">已分析</div>
      </div>
      <div style="flex:1;min-width:130px;background:#1e293b;border-radius:12px;padding:16px;text-align:center;border:1px solid #334155">
        <div style="font-size:28px;font-weight:700;color:#f59e0b">{len(papers) - len(analyzed)}</div>
        <div style="color:#64748b;font-size:12px">待分析</div>
      </div>
    </div>

    <!-- Source distribution -->
    <div style="background:#1e293b;border-radius:12px;padding:16px;margin-bottom:20px;border:1px solid #334155">
      <p style="margin:0 0 8px;color:#94a3b8;font-size:12px">來源分布</p>
      <div>{source_badges}</div>
    </div>

    <!-- Action Buttons -->
    <div style="text-align:center;margin-bottom:20px">
      {notion_button}
      <a href="{dashboard_url}" style="display:inline-block;background:#0f172a;color:#818cf8;border:1px solid #818cf8;
         padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 4px;font-size:14px">
         🖥️ 開啟本地儀表板
      </a>
    </div>

    <!-- Papers Table -->
    <div style="background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155;margin-bottom:20px">
      <h2 style="margin:0 0 16px;color:#e2e8f0;font-size:15px">📋 今日文獻列表</h2>
      <table style="width:100%;border-collapse:collapse">
        {paper_rows}
      </table>
      {"<p style='color:#64748b;font-size:12px;text-align:center;margin:12px 0 0'>... 僅顯示前 20 篇，完整列表請至 Notion 或本地儀表板查看</p>" if len(papers) > 20 else ""}
    </div>

    <!-- Footer -->
    <div style="text-align:center;color:#334155;font-size:11px;padding:16px">
      <p style="margin:0">由 Literature Integrator 自動生成 | {TODAY_STR}</p>
      <p style="margin:4px 0 0">此為系統自動發送的郵件，請勿直接回覆。</p>
    </div>
  </div>
</body>
</html>"""
    return html


# --------------------------------------------------------------------------- #
# Send Email
# --------------------------------------------------------------------------- #

def send_email_report(papers: list, notion_url: str = "", subject: str = None) -> bool:
    """Send an HTML email report of today's literature to the configured receiver."""
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
        print("[!] Email credentials not configured — skipping email notification.")
        return False

    if not subject:
        subject = f"📚 Literature Integrator 日報 — {TODAY_STR} ({len(papers)} 篇文獻)"

    html_content = _build_email_html(papers, notion_url)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        print(f"[*] Sending email to {RECEIVER_EMAIL}...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"  ✅ Email sent successfully.")
        return True
    except Exception as e:
        print(f"  ❌ Email sending failed: {e}")
        return False


# --------------------------------------------------------------------------- #
# Send LINE Push Message
# --------------------------------------------------------------------------- #

def _build_line_message(papers: list, notion_url: str = "") -> str:
    """Build a compact LINE text message for today's literature summary."""
    analyzed = [p for p in papers if p.get("status") == "analyzed"]
    sources = {}
    for p in papers:
        src = p.get("source", "unknown").upper()
        sources[src] = sources.get(src, 0) + 1
    source_str = " | ".join(f"{s}:{n}" for s, n in sources.items())

    lines = [
        f"📚 文獻整合日報 {TODAY_STR}",
        f"━━━━━━━━━━━━━━━━",
        f"📊 今日收錄: {len(papers)} 篇",
        f"✅ 已分析: {len(analyzed)} 篇",
        f"⏳ 待分析: {len(papers) - len(analyzed)} 篇",
        f"📂 來源: {source_str}",
        "",
        "🔥 今日精選文獻:",
    ]

    # Top 5 papers
    for i, p in enumerate(papers[:5], 1):
        title = p.get("title", "Unknown")[:60]
        source = p.get("source", "").upper()
        lines.append(f"{i}. [{source}] {title}...")
        if p.get("llm_summary"):
            summary_snippet = p["llm_summary"][:80].replace("\n", " ")
            lines.append(f"   💡 {summary_snippet}...")

    if len(papers) > 5:
        lines.append(f"\n... 另有 {len(papers) - 5} 篇文獻")

    lines.append("")
    if notion_url:
        lines.append(f"📓 Notion: {notion_url}")
    lines.append("🖥️ 儀表板: http://localhost:8501")

    return "\n".join(lines)


def send_line_report(papers: list, notion_url: str = "") -> bool:
    """Send a LINE push message to the configured user."""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("[!] LINE credentials not configured — skipping LINE notification.")
        return False

    text = _build_line_message(papers, notion_url)

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
    }

    try:
        print(f"[*] Sending LINE push message to user {LINE_USER_ID[:8]}...")
        resp = requests.post(LINE_API_URL, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            print("  ✅ LINE message sent successfully.")
            return True
        else:
            print(f"  ❌ LINE API returned status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ LINE message sending failed: {e}")
        return False


# --------------------------------------------------------------------------- #
# Combined notifier
# --------------------------------------------------------------------------- #

def send_all_notifications(papers: list, notion_url: str = "") -> dict:
    """Send all configured notifications (Email + LINE). Returns status dict."""
    results = {
        "email": send_email_report(papers, notion_url),
        "line": send_line_report(papers, notion_url),
    }
    print(f"\n[*] Notification summary: Email={'OK' if results['email'] else 'FAILED'}, LINE={'OK' if results['line'] else 'FAILED'}")
    return results


# --------------------------------------------------------------------------- #
# CLI test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    mock_papers = [
        {
            "paper_id": "2303.08774",
            "title": "GPT-4 Technical Report",
            "authors": "OpenAI",
            "published_date": "2023-03-15",
            "summary": "We report the development of GPT-4...",
            "url": "https://arxiv.org/abs/2303.08774",
            "source": "arxiv",
            "status": "analyzed",
            "llm_summary": "GPT-4 是一個支援圖文輸入的大型語言模型，在多項專業考試中達到人類頂尖水準。",
            "code_available": "NO",
            "data_available": "NO",
        }
    ]

    print("=== Testing Email ===")
    send_email_report(mock_papers, notion_url="https://notion.so/test-page")

    print("\n=== Testing LINE ===")
    send_line_report(mock_papers, notion_url="https://notion.so/test-page")
