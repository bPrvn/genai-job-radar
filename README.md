# GenAI Job Radar

A personal job-hunt agent for Senior GenAI / Applied AI Engineer roles in India.
Every morning it:

1. **Collects jobs** from the careers sites of Apple, Google, Amazon, Nvidia, Atlassian,
   Salesforce, Adobe, Target, ServiceNow, Rubrik, Databricks, Groww, Meesho and CRED
   (their own public job APIs), keeps India-based AI/ML roles, and scores each one 0–100 for fit.
2. **Finds leads** for companies without a public API (Microsoft, Walmart, Uber, JPMorgan,
   Flipkart, Swiggy…) by web search (Tavily, or [`ddgs`](https://pypi.org/project/ddgs/)
   without a key). These are marked *lead · verify*.
3. **Researches interview questions** from RSS feeds (Medium tags), dev.to, Hacker News and
   web search, and pulls the questions out of each article with NVIDIA NIM (or a rule-based
   extractor when no key is set). Questions are grouped by round.
4. **Tracks skills** employers ask for (RAG, agents, evals, fine-tuning…) as a share of open
   roles, day by day.
5. **Reads shortlisted blogs** (Apple ML Research, NVIDIA, Google Research, Hugging Face,
   Uber, Netflix, Swiggy, Flipkart, Chip Huyen, Eugene Yan, Lilian Weng).
6. **Writes a daily AI brief** with NVIDIA NIM: roles to act on, skill trends, five questions
   to practise, reading.

```
 launchd 08:30 ─► scripts/daily.sh ─► backend (Python, SQLite at data/radar.db)
                                       │  careers APIs · web search · RSS · NVIDIA NIM
                                       ▼
                         frontend/public/data/snapshot.json ── git push ──► GitHub Actions
                                                                              │ build + deploy
 Dashboard (React) ◄──────────────────────────────────────────────────────────┘ GitHub Pages
   └─ when the local API (localhost:8000) is running: live mode, status edits, "Run now"
```

The backend and database run only on your Mac. GitHub hosts the dashboard and a read-only
snapshot. The public snapshot leaves out application status, notes and practice ticks
(`PUBLISH_PERSONAL_FIELDS` in `backend/radar/config.py`).

## Setup

```bash
# backend (Python 3.10+)
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # add your keys (see below)
.venv/bin/python -m radar run   # first run: ~5–10 minutes
.venv/bin/python -m radar serve # API on http://localhost:8000

# frontend
cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

Schedule the daily run (08:30 local time; pass `HOUR MINUTE` to change):

```bash
scripts/install-schedule.sh          # clones to ~/dev/genai-job-radar, installs the launchd job
launchctl kickstart gui/$(id -u)/com.genai-job-radar.daily   # run once now
scripts/serve.sh                     # local API on :8000 against the daily job's database
```

macOS does not let scheduled jobs read `~/Desktop`, `~/Documents` or `~/Downloads`, so the
daily job runs from its own clone in `~/dev/genai-job-radar`, which also holds the database
and logs (`data/logs/`). Edit code anywhere, push it, and the next run pulls it. Pull before
you push: the daily job commits `snapshot.json` every morning.

Get the keys (both free) and put them in `backend/.env`:

- `NVIDIA_API_KEY`: [build.nvidia.com](https://build.nvidia.com) → any model → *Get API Key*.
  Writes the daily brief and extracts interview questions.
- `TAVILY_API_KEY` (optional): [tavily.com](https://tavily.com), 1,000 searches a month.
  Without it, web search uses `ddgs`, which search engines often block for automated use.

## Commands

| Command | What it does |
| --- | --- |
| `python -m radar run` | Full run: jobs, web leads, research, skills, AI brief, snapshot |
| `python -m radar run --jobs-only` | Careers sites only, no web search or RSS |
| `python -m radar serve` | Local API for the dashboard's live mode |
| `python -m radar summary` | Print today's brief |
| `python -m radar export` | Rewrite the snapshot from the DB |

## Changing what it looks for

Everything is in [`backend/radar/config.py`](backend/radar/config.py): companies and their
job APIs (`SOURCES`), title filters, locations, skill keyword clusters, RSS feeds, web search
queries and the NIM model. To add a company on Greenhouse, Lever, Workday or SmartRecruiters,
add one line to `SOURCES`.

## Notes

- Only public endpoints are used. Login-walled sites (Glassdoor, LinkedIn, Naukri, Reddit) are
  never fetched; links to them can still appear as web leads.
- Careers sites change their pages. When an adapter breaks, the dashboard lists it under
  "source(s) had problems" and every other source keeps working.
- Fit score: title match (GenAI/LLM > ML), seniority (Staff/Principal penalised), years asked
  vs ~5, preferred cities, and how many of your skills the JD mentions.
