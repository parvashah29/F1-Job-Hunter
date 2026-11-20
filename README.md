# F-1 Job Hunter Agent 🏎️

> An automated, free, AI-powered dual-track job scraper for F-1 OPT visa holders.
> Runs every evening at **7:00 PM** and drops two curated Markdown reports in your `reports/` folder.

---

## 📁 Project Structure

```
F1 Job Hunter/
├── config.yaml           ← ✏️  Edit this to customize roles, companies, model
├── main.py               ← Orchestrator (run this)
├── scraper_ats.py        ← Track A: Greenhouse + Lever JSON APIs
├── scraper_bigtech.py    ← Track B: Playwright scraper for Big Tech
├── ai_analyzer.py        ← Ollama LLM wrapper (YES/NO sponsorship filter)
├── role_matcher.py       ← Tier classifier (pre-filters before AI)
├── database.py           ← SQLite deduplication layer
├── report_generator.py   ← Markdown report builder
├── notifier.py           ← macOS desktop notification
├── setup_cron.sh         ← One-shot cron installer (7 PM daily)
├── requirements.txt      ← Python dependencies
├── reports/              ← Output: daily_jobs_*.md & bigtech_jobs_*.md
├── data/jobs.db          ← SQLite database (auto-created)
└── logs/                 ← Per-run log files
```

---

## ⚙️ Setup (One Time)

### 1. Install dependencies
```bash
pip3 install -r requirements.txt
playwright install chromium
```

### 2. Make sure Ollama is running
```bash
ollama serve          # Start Ollama in background
ollama pull llama3.2  # Pull the model (already done if you see it in ollama list)
```

### 3. Run a dry test
```bash
python3 main.py --dry-run
```
This scrapes job titles (no AI calls, no DB writes) — verifies connectivity.

### 4. Run a live test
```bash
python3 main.py
```
Full run — scrapes, analyzes, saves to DB, generates reports, sends macOS notification.

### 5. Schedule daily at 7 PM
```bash
bash setup_cron.sh
```

---

## 🚀 Commands

| Command | What it does |
|---|---|
| `python3 main.py` | Full run — both tracks |
| `python3 main.py --dry-run` | Test: scrape titles only, no AI/DB |
| `python3 main.py --track a` | Only ATS/aggregator scraper |
| `python3 main.py --track b` | Only Big Tech scraper |
| `python3 main.py --report` | Regenerate reports from today's DB data |
| `bash setup_cron.sh` | Install 7 PM cron job |
| `crontab -l` | Verify cron is installed |

---

## 📄 Output Reports

| File | Content |
|---|---|
| `reports/daily_jobs_YYYY-MM-DD.md` | Top jobs from Track A (Greenhouse/Lever), sorted by tier |
| `reports/bigtech_jobs_YYYY-MM-DD.md` | All qualifying jobs from Track B (Meta, Amazon, Google, etc.), grouped by company |

---

## 🔧 Customization

All settings live in **`config.yaml`** — no code changes needed:

- **`ai.model`** — Switch between `llama3.2` (fast) and `mistral` (thorough)
- **`track_a.greenhouse_companies`** — Add/remove companies on Greenhouse ATS
- **`track_a.lever_companies`** — Add/remove companies on Lever ATS  
- **`track_b.companies`** — Add/remove Big Tech career page URLs
- **`roles`** — Add new role keywords to any tier

### Adding a new company (Track A — Greenhouse)
```yaml
greenhouse_companies:
  - { slug: "newcompany", name: "New Company" }
```

### Adding a new Big Tech company (Track B)
```yaml
track_b:
  companies:
    - name: "Uber"
      base_url: "https://www.uber.com"
      search_url: "https://www.uber.com/us/en/careers/list/?query=data+scientist+new+grad"
      type: "playwright"
```

---

## 🧠 How the AI Filter Works

Each job description is sent to your local Ollama instance with this logic:
- **Returns YES** → job is saved to DB and included in the report
- **Returns NO** → job is discarded (requires citizenship/clearance/no sponsorship)
- **Ambiguous or error** → defaults to **YES** (you never miss an opportunity)

The AI uses `temperature: 0.0` for fully deterministic, consistent responses.

---

## 🐞 Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot connect to Ollama` | Run `ollama serve` in a terminal |
| `Playwright timeout` | A company's site was slow — it'll skip and try again tomorrow |
| `Greenhouse slug not found` | The company changed their ATS — remove from config.yaml |
| `No jobs in report` | Either all were filtered (NO) or already seen — check `logs/` |

---

## 🗺️ Roadmap (V2)

- [ ] Resume match scoring (1–100 fit score via LLM)
- [ ] Auto-fill Greenhouse/Lever application forms
- [ ] Streamlit kanban dashboard (Applied / Interviewing / Rejected)
- [ ] `config.yaml`-driven role and location filters for each company
- [ ] Merged ranked digest combining both tracks
