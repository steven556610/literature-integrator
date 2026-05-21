# 📚 Literature Integrator

> 智慧文獻整合平台 — 自動蒐集、分析並推送科學文獻日報

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red?logo=streamlit)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 功能特色

| 功能 | 說明 |
|------|------|
| 🔍 **多源爬蟲** | 自動從 arXiv、bioRxiv、medRxiv 蒐集 2020–2026 年文獻 |
| 🤖 **AI 深度分析** | 支援 **Qwen2.5-7B / 14B**（本地）與 **Gemini 2.0 Flash**（雲端） |
| 📊 **互動儀表板** | 深色玻璃質感 Streamlit UI，含搜尋、篩選、分析展示 |
| 🔗 **URL 直接解析** | 貼上 arXiv / bioRxiv / DOI 連結，自動分析存入資料庫 |
| 📓 **Notion 整合** | 每日自動在 Notion 日誌下建立 `literature_日期` 子頁面 |
| 📧 **Email 通知** | 精美 HTML 格式的每日文獻日報 |
| 💬 **LINE 推播** | 透過 LINE Messaging API 推送每日摘要 |

---

## 🏗️ 系統架構

```
literature_integrator/
├── app.py                    # Streamlit 儀表板
├── requirements.txt          # Python 依賴
├── environment.yml           # Conda 環境定義
├── .env.example              # 環境變數範本
│
├── crawlers/
│   ├── arxiv_crawler.py      # arXiv REST API 爬蟲
│   ├── biorxiv_crawler.py    # bioRxiv/medRxiv (Europe PMC) 爬蟲
│   └── paper_resolver.py     # URL/DOI 解析器
│
├── database/
│   └── db_manager.py         # SQLite + SQLAlchemy ORM
│
├── processors/
│   └── llm_analyzer.py       # 多後端 LLM 分析（Qwen / Gemini）
│
├── integrators/
│   ├── notion_client.py      # Notion API 整合
│   └── notifier.py           # Email + LINE 通知
│
└── scheduler/
    └── daily_job.py          # 每日自動化排程任務
```

---

## 🚀 快速開始

### 1. 建立 Conda 環境

```bash
conda env create -f environment.yml
conda activate literature_integrator
```

或手動安裝：

```bash
conda create -n literature_integrator python=3.11 -y
conda activate literature_integrator
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env 填入你的 API Keys
```

`.env` 需填入：

```env
# Google Gemini API（雲端分析用）
GOOGLE_API_KEY=your_google_api_key

# Notion 整合
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_database_id

# LINE Messaging API
LINE_ASSESS_TOKEN=your_line_channel_access_token
USER_ID=your_line_user_id

# Email (Gmail SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECEIVER_EMAIL=receiver@gmail.com

# LLM 後端選擇: gemini | qwen7b | qwen14b
LLM_BACKEND=qwen14b
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. 安裝 Ollama（本地 Qwen 模型）

```bash
# 下載 Ollama: https://ollama.com
ollama pull qwen2.5:7b-instruct   # 4.7GB，快速
ollama pull qwen2.5:14b           # 9.0GB，高精度
```

### 4. 啟動儀表板

```bash
streamlit run app.py
# 開啟瀏覽器: http://localhost:8501
```

### 5. 執行每日任務

```bash
# 每日自動爬取 + 分析 + 通知
python scheduler/daily_job.py --mode daily

# 歷史資料爬取（2020–2026）
python scheduler/daily_job.py --mode historical
```

---

## 🤖 LLM 後端比較

| 後端 | 模型 | 環境 | 速度 | 精度 | 成本 |
|------|------|------|------|------|------|
| `qwen14b` | Qwen2.5:14b | 本地 Ollama | 中 | ⭐⭐⭐⭐⭐ | 免費 |
| `qwen7b`  | Qwen2.5:7b  | 本地 Ollama | 快 | ⭐⭐⭐⭐ | 免費 |
| `gemini`  | Gemini 2.0 Flash | 雲端 | 極快 | ⭐⭐⭐⭐⭐ | 有限免費 |

---

## 📋 AI 分析欄位

每篇文獻由 LLM 自動提取以下六個維度（全繁體中文輸出）：

- **💡 中文摘要** — 2~4 句精簡說明，包含核心方法與貢獻
- **💭 理論假設** — 核心科學假設或生物學/計算猜想
- **🎯 實驗動機** — 想解決的痛點與研究缺口
- **🏆 SOTA 比較** — 與現有最先進方法的具體指標比較
- **💻 程式碼可用性** — `YES / NO / PARTIAL / UNKNOWN` + 連結
- **📂 資料集可用性** — `YES / NO / PARTIAL / UNKNOWN` + 連結

---

## 📅 排程設定（Windows Task Scheduler）

```
程式路徑: D:\miniconda3\envs\literature_integrator\python.exe
參數: D:\code\literature_integrator\scheduler\daily_job.py --mode daily
觸發時間: 每天 08:00
```

---

## 📦 依賴套件

- `streamlit` — Web 儀表板
- `google-genai` — Gemini 2.0 API
- `sqlalchemy` — SQLite ORM
- `requests` — HTTP 客戶端（arXiv / Europe PMC / Crossref API）
- `python-dotenv` — 環境變數管理
- `pandas` — 資料處理

---

## 🔒 安全注意事項

- `.env` 已加入 `.gitignore`，絕對不要提交含 API Keys 的檔案
- 使用 Gmail 時請使用 [App Password](https://myaccount.google.com/apppasswords)，不要使用帳號密碼
- Notion Integration Token 請限制在最小必要權限

---

## 📄 License

MIT License — 詳見 [LICENSE](LICENSE)
