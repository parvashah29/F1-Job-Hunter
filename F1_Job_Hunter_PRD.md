> **Note:** this is the original product brief. The implementation has since changed: Track A uses the Greenhouse/Lever JSON APIs (no Playwright), eligibility is rule-based with an optional LLM, and Track B is best-effort. See README.md for current behaviour.

# Product Requirements Document (PRD): F-1 Job Hunter Agent

## 1. Project Overview
The **F-1 Job Hunter Agent** is an automated, completely free, AI-powered system designed to streamline the job search process for international students on F-1 visas (and OPT/CPT). The system automates the tedious process of scraping job boards, reading job descriptions, and filtering out roles that explicitly deny visa sponsorship, delivering a highly curated list of safe-to-apply jobs **every evening at 7:00 PM** — capturing all fresh listings posted throughout the day.

The agent runs **two parallel scraping tracks**:
- **Track A — ATS & Aggregator Scraper:** Targets smaller/mid-size companies via Greenhouse, Lever, and job aggregators.
- **Track B — Big Tech Direct Careers Scraper:** Targets the official career portals of top-tier MNC companies (Meta, Amazon, Google, Microsoft, Apple, etc.) and produces a separate curated report.

## 2. Target Audience
*   **Primary Users:** International university students or recent graduates in the US on F-1 visas looking for internships or full-time roles (OPT/STEM OPT).
*   **Secondary Users:** Anyone looking to automate job searching with specific keyword inclusions/exclusions without paying for premium job board features or API credits.

## 3. Core Features
*   **Dual-Track Automated Scraping:** Runs two parallel scrapers every evening:
    *   **Track A** scrapes ATS/aggregator boards (Greenhouse, Lever, Wellfound, etc.) for small-to-mid-size companies.
    *   **Track B** directly crawls the official careers portals of top MNC companies (Meta, Amazon, Google, Microsoft, Apple, NVIDIA, Netflix, OpenAI, Salesforce, Adobe, etc.).
*   **Local AI Analysis:** Utilizes a local Large Language Model (LLM) to read the full text of each job description and intelligently determine the likelihood of visa sponsorship.
*   **F-1 Sponsorship Filtering:** Specifically looks for red flags (e.g., "US Citizenship required", "No C2C or Visa Sponsorship") and green flags (e.g., "We sponsor visas", "Global mobility").
*   **Dual Daily Digest Generation:**
    *   `daily_jobs_YYYY-MM-DD.md` — Top 15–20 curated roles from ATS/aggregators.
    *   `bigtech_jobs_YYYY-MM-DD.md` — Top roles from Big Tech / MNC direct career pages, separately listed for easy reference.
*   **Zero Recurring Costs:** Built entirely on open-source and free tools, ensuring no monthly subscriptions for APIs or scraping services.

## 4. Technology Stack
*   **Programming Language:** Python 3.10+
*   **Web Scraping:** 
    *   `Playwright` (for Python) to handle dynamic JavaScript rendering and bypass basic bot protections.
    *   `BeautifulSoup4` for parsing HTML structure once the page is loaded.
*   **Local AI / LLM Engine:**
    *   `Ollama` (Local model runner for macOS)
    *   `Llama 3 8B` or `Phi-3` (Running locally via Ollama for fast, free text analysis)
*   **Data Storage:** Local `SQLite` database (to keep track of already seen jobs and prevent duplicates).
*   **Automation/Scheduling:** macOS `cron` or `launchd` (or Antigravity's `/schedule` command) for running the Python script daily.

## 5. System Architecture & Workflow
1.  **Trigger:** At **7:00 PM daily**, the scheduler executes `main.py` — capturing all listings posted throughout the workday.
2.  **Parallel Scraping (Two Tracks run concurrently):**
    *   **Track A — ATS/Aggregator Scraper (`scraper_ats.py`):** Playwright navigates Greenhouse, Lever, Wellfound, and other aggregators. Extracts Job Titles, Company Names, Links, and raw Job Description text.
    *   **Track B — Big Tech Direct Careers Scraper (`scraper_bigtech.py`):** Playwright navigates official careers pages of top MNCs. Target companies include:
        *   **Meta** — `metacareers.com`
        *   **Amazon** — `amazon.jobs`
        *   **Google / DeepMind** — `careers.google.com`
        *   **Microsoft** — `careers.microsoft.com`
        *   **Apple** — `jobs.apple.com`
        *   **NVIDIA** — `nvidia.com/en-us/about-nvidia/careers`
        *   **Netflix** — `jobs.netflix.com`
        *   **OpenAI** — `openai.com/careers`
        *   **Salesforce** — `salesforce.com/company/careers`
        *   **Adobe** — `adobe.com/careers`
        *   *(Easily extensible — add any company URL to a config file)*
3.  **Deduplication:** All extracted job links are checked against the local SQLite database. Previously seen links are skipped.
4.  **AI Analysis Module:** Each job description (from both tracks) is passed to the local Ollama instance with a strict binary prompt:
    > [!TIP]
    > *"You are an expert technical recruiter analyzing a job description. Your goal is to determine if an F-1 visa holder on OPT can apply. Return YES if they explicitly offer sponsorship or do not mention citizenship requirements. Return NO if they explicitly require US Citizenship, Green Card, or state 'No Sponsorship'. Only return YES or NO."*
5.  **Filtering & Ranking:** Jobs returning 'NO' are discarded. Jobs returning 'YES' are saved to the SQLite database tagged by their source track.
6.  **Dual Report Generation:**
    *   `daily_jobs_YYYY-MM-DD.md` — Top 15–20 'YES' jobs from **Track A** (ATS/aggregators)
    *   `bigtech_jobs_YYYY-MM-DD.md` — All qualifying 'YES' jobs from **Track B** (Big Tech direct), listed with Company, Title, and direct application link
7.  **Notification:** A single macOS desktop notification fires when both reports are ready, with a summary count (e.g., *"🔥 22 new jobs found: 15 from ATS, 7 from Big Tech"*).

## 6. Challenges & Mitigations
> [!WARNING]
> **Anti-Bot Protections:** Major sites (LinkedIn/Indeed) aggressively block automated scrapers.
*   **Mitigation:** We will target ATS systems directly (Greenhouse/Lever) or use aggregators that are less strictly protected. We will use Playwright to simulate human browsing patterns (delays, scrolling).

> [!CAUTION]
> **LLM Hallucinations:** The local AI might incorrectly flag a job or miss a subtle denial of sponsorship.
*   **Mitigation:** We keep the prompt strictly binary (YES/NO) and instruct the model to default to YES if unsure, ensuring you don't miss potential opportunities. You will still manually review the final 15-20 jobs before applying.

> [!NOTE]
> **Performance / Compute:** Running an LLM locally requires RAM and processing power.
*   **Mitigation:** We will use optimized, quantized models via Ollama which run smoothly on modern Mac hardware without locking up your system.

## 7. Future Enhancements (V2)
*   **Resume Match Scoring:** Have the local LLM also read your resume and assign a "Match Score" (1-100) to each job in the daily digest based on keyword overlap.
*   **Auto-Fill Integration:** Build a script that automatically fills out the standard Greenhouse/Lever application forms using your saved profile data.
*   **Interactive Dashboard:** Replace the Markdown output with a simple local `Streamlit` web app to visually track application statuses (Applied, Interviewing, Rejected) in a kanban board format.
*   **Configurable Company List:** Allow adding/removing Big Tech target companies and custom search keywords (e.g., role type, location, experience level) via a simple `config.yaml` file without touching the code.
*   **Consolidated View:** Merge both Track A and Track B reports into a single ranked digest sorted by AI match score (once Resume Match Scoring is added in V2).
