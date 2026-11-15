"""What to search for, where, and how to score it. Edit this file to change targets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "radar.db"
SNAPSHOT_PATH = ROOT / "frontend" / "public" / "data" / "snapshot.json"

# Public snapshot (GitHub Pages) leaves out your application status and notes,
# so a public site never shows where you've applied. Set True to include them.
PUBLISH_PERSONAL_FIELDS = False

PROFILE = {
    "years": 5,
    "min_years": 3,   # roles asking for fewer years are flagged "junior"
    "max_years": 8,   # roles asking for more are flagged "stretch"
    "skills": [
        "rag", "llm", "langchain", "langgraph", "agents", "vector", "fastapi",
        "python", "embeddings", "prompt", "evaluation", "aws", "azure", "docker",
    ],
}

SEARCH_TERMS = ["machine learning", "generative ai", "llm", "applied ai", "ai engineer"]

LOCATION_WORDS = ["india", "bengaluru", "bangalore", "hyderabad", "remote - india", "remote, india"]
PREFERRED_CITIES = ["bengaluru", "bangalore", "hyderabad"]

# A role is relevant when its title matches INCLUDE and not EXCLUDE.
TITLE_INCLUDE = [
    r"\bmachine learning\b", r"\bml\b", r"\bai\b", r"\bgen ?ai\b", r"\bgenerative\b",
    r"\bllm", r"\bnlp\b", r"applied scientist", r"data scientist", r"\bmlops\b",
    r"artificial intelligence", r"deep learning",
]
TITLE_EXCLUDE = [
    r"\bintern\b", r"\bdirector\b", r"\bvp\b", r"\bprincipal\b", r"\bsales\b",
    r"\baccount\b", r"\brecruit", r"\bmarketing\b", r"\blegal\b", r"\bmanager\b",
    r"\bpartner\b", r"\bfinance\b", r"\bdesigner\b",
]

# Each source is one adapter in radar/sources. Add companies by appending here.
SOURCES = [
    {"kind": "apple", "company": "Apple"},
    {"kind": "google", "company": "Google"},
    {"kind": "amazon", "company": "Amazon"},
    {"kind": "atlassian", "company": "Atlassian"},
    {"kind": "workday", "company": "Nvidia", "host": "nvidia.wd5", "tenant": "nvidia", "site": "NVIDIAExternalCareerSite"},
    {"kind": "workday", "company": "Salesforce", "host": "salesforce.wd12", "tenant": "salesforce", "site": "External_Career_Site"},
    {"kind": "workday", "company": "Adobe", "host": "adobe.wd5", "tenant": "adobe", "site": "external_experienced"},
    {"kind": "workday", "company": "Target", "host": "target.wd5", "tenant": "target", "site": "targetcareers"},
    {"kind": "smartrecruiters", "company": "ServiceNow", "slug": "ServiceNow"},
    {"kind": "greenhouse", "company": "Rubrik", "slug": "rubrik"},
    {"kind": "greenhouse", "company": "Databricks", "slug": "databricks"},
    {"kind": "greenhouse", "company": "Groww", "slug": "groww"},
    {"kind": "lever", "company": "Meesho", "slug": "meesho"},
    {"kind": "lever", "company": "CRED", "slug": "cred"},
]

TIERS = {
    "Apple": "Top", "Google": "Top", "Amazon": "Top", "Nvidia": "Top", "Atlassian": "Top",
    "Rubrik": "Top", "Databricks": "Top",
    "Salesforce": "GCC", "Adobe": "GCC", "Target": "GCC", "ServiceNow": "GCC",
    "Groww": "Indian product", "Meesho": "Indian product", "CRED": "Indian product",
}

# Skill clusters counted across job descriptions. Label -> regex alternatives.
KEYWORDS = {
    "RAG / retrieval": [r"\brag\b", r"retrieval[- ]augmented", r"retrieval"],
    "Vector DB / search": [r"vector (db|database|store|search)", r"pinecone", r"weaviate", r"faiss", r"milvus", r"pgvector", r"hybrid search", r"elasticsearch", r"opensearch"],
    "LLMs": [r"\bllms?\b", r"large language model", r"\bgpt", r"\bclaude\b", r"\bgemini\b", r"\bllama\b"],
    "Agents / tool use": [r"\bagent(s|ic)?\b", r"tool[- ]calling", r"function calling", r"multi-agent"],
    "LangChain / LangGraph": [r"langchain", r"langgraph", r"llamaindex", r"llama-index"],
    "Fine-tuning": [r"fine[- ]tun", r"\blora\b", r"\bqlora\b", r"\brlhf\b", r"\bpeft\b"],
    "Evaluation": [r"\bevals?\b", r"evaluation", r"llm[- ]as[- ]a?[- ]?judge", r"benchmark"],
    "Prompt engineering": [r"prompt engineering", r"\bprompting\b", r"prompt design"],
    "MLOps / deployment": [r"\bmlops\b", r"model serving", r"inference", r"\bvllm\b", r"triton", r"deployment"],
    "PyTorch": [r"pytorch", r"\btorch\b"],
    "TensorFlow / JAX": [r"tensorflow", r"\bjax\b", r"\bkeras\b"],
    "Python": [r"\bpython\b"],
    "Java / Scala / Go": [r"\bjava\b", r"\bscala\b", r"\bgolang\b", r"\bgo\b(?= |,)"],
    "Swift / Obj-C": [r"\bswift\b", r"objective-c"],
    "Spark / big data": [r"\bspark\b", r"\bhadoop\b", r"\bkafka\b", r"databricks", r"airflow"],
    "Cloud (AWS/Azure/GCP)": [r"\baws\b", r"\bazure\b", r"\bgcp\b", r"google cloud", r"sagemaker", r"bedrock", r"vertex ai"],
    "Kubernetes / Docker": [r"kubernetes", r"\bk8s\b", r"docker", r"container"],
    "APIs / microservices": [r"\bapis?\b", r"microservice", r"rest(ful)?\b", r"grpc", r"fastapi", r"distributed systems"],
    "SQL / data": [r"\bsql\b", r"postgres", r"data pipeline"],
    "NLP": [r"\bnlp\b", r"natural language"],
    "Computer vision": [r"computer vision", r"\bcv\b", r"image"],
    "Recommendation / ranking": [r"recommend", r"ranking", r"personaliz"],
}

# Interview question sources (public APIs only; nothing that needs a login).
QUESTION_QUERIES = [
    "machine learning interview", "LLM interview questions", "GenAI interview",
    "RAG interview", "ML system design interview", "AI engineer interview",
]
DEVTO_TAGS = ["interview", "llm", "genai", "rag", "machinelearning"]

HTTP_TIMEOUT = 25
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

# ---------------------------------------------------------------- RSS feeds
# "questions": articles are mined for interview questions.
# "blog": shortlisted engineering / AI blogs, shown as a daily reading list.
RSS_FEEDS = [
    {"name": "Medium: ML interview", "url": "https://medium.com/feed/tag/machine-learning-interview", "use": "questions"},
    {"name": "Medium: GenAI interview", "url": "https://medium.com/feed/tag/generative-ai-interview", "use": "questions"},
    {"name": "Medium: LLM interview", "url": "https://medium.com/feed/tag/llm-interview", "use": "questions"},
    {"name": "Medium: System design interview", "url": "https://medium.com/feed/tag/system-design-interview", "use": "questions"},
    {"name": "Apple Machine Learning Research", "url": "https://machinelearning.apple.com/rss.xml", "use": "blog"},
    {"name": "NVIDIA Technical Blog", "url": "https://developer.nvidia.com/blog/feed", "use": "blog"},
    {"name": "Google Research", "url": "https://research.google/blog/rss/", "use": "blog"},
    {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml", "use": "blog"},
    {"name": "Netflix Tech Blog", "url": "https://netflixtechblog.com/feed", "use": "blog"},
    {"name": "Swiggy Bytes", "url": "https://bytes.swiggy.com/feed", "use": "blog"},
    {"name": "Flipkart Tech", "url": "https://blog.flipkart.tech/feed", "use": "blog"},
    {"name": "Chip Huyen", "url": "https://huyenchip.com/feed.xml", "use": "blog"},
    {"name": "Eugene Yan", "url": "https://eugeneyan.com/rss/", "use": "blog"},
    {"name": "Lilian Weng", "url": "https://lilianweng.github.io/index.xml", "use": "blog"},
]

# Job-board RSS feeds, parsed daily so new roles aren't missed. Add any real RSS feed URL here.
# NOTE: Naukri and Hirist do NOT publish public RSS feeds (naukri /jobs-rss = 404; hirist returns
# HTML, not a feed) and their robots.txt forbids scraping, so they can't be ingested this way.
# These are remote-first boards that DO expose RSS; location is filtered loosely so India-eligible
# remote roles come through. Each entry: {name, url}.
JOB_RSS_FEEDS = [
    {"name": "WeWorkRemotely", "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss"},
    {"name": "WeWorkRemotely DevOps", "url": "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"},
]
# RSS leads keep roles whose title matches; set True to also require an India/remote location hint.
JOB_RSS_REQUIRE_INDIA = False

# ---------------------------------------------------------------- Web search agent
# Uses Tavily (free 1,000 searches/month, tavily.com) when TAVILY_API_KEY is in backend/.env,
# otherwise the free `ddgs` package. ~23 searches per daily run.
# Companies without a public jobs API: found through web search as "leads" (unverified).
WEB_JOB_COMPANIES = ["Microsoft", "Walmart Global Tech", "Uber", "JPMorgan Chase", "Goldman Sachs",
                     "American Express", "Intuit", "Flipkart", "Swiggy", "PhonePe", "Razorpay", "Sarvam AI"]
WEB_JOB_QUERIES = ["{company} generative AI machine learning engineer jobs India"]
# Search results that are listing / aggregator pages, not one job.
WEB_LEAD_EXCLUDE = r"\d+\s+(open|openings|jobs|roles|vacancies)|jobs (&|and) careers|jobs in (india|bengaluru|bangalore|hyderabad)|careers page|salary|salaries|interview"
# Several query angles per company → more pages from the scrape-friendly sites (igotanoffer,
# InterviewQuery, GeeksforGeeks, InterviewBit, DataFord, engineering blogs). Login-walled sites
# that forbid automated access (LinkedIn, Glassdoor, AmbitionBox) are filtered by NO_FETCH_DOMAINS.
WEB_QUESTION_QUERY = "{company} machine learning engineer interview experience questions"  # kept for compatibility
WEB_QUESTION_QUERIES = [
    "{company} machine learning engineer interview questions",
    "{company} generative AI engineer interview experience",
    "{company} GenAI LLM interview questions rounds",
]
WEB_QUESTION_COMPANIES = ["Apple", "Google", "Microsoft", "Amazon", "Nvidia", "Atlassian", "Salesforce",
                          "Adobe", "Walmart Global Tech", "Uber", "Flipkart"]
WEB_TIMELIMIT = "m"        # d / w / m / y: only results from the last month
WEB_QUESTION_TIMELIMIT = "y"
WEB_BACKEND = "yandex"     # ddgs primary engine (free). Yandex answers automated queries where
WEB_BACKEND_FALLBACKS = ["brave", "mojeek"]  # quick extra tries (duckduckgo's html endpoint hangs, so it's out)
WEB_RETRIES = 3            # retry the engines this many times (yandex soft-rate-limits after rapid queries)
WEB_PACE_SECONDS = (2.5, 4.5)  # random wait before each search attempt, to stay under the rate limit
WEB_HTTP_TIMEOUT = 12      # per search-engine request
# Never fetched or mined (login walls / terms forbid scraping). Links from them can still appear as leads.
NO_FETCH_DOMAINS = ["glassdoor.", "linkedin.com", "naukri.com", "indeed.", "ambitionbox.com", "reddit.com", "quora.com"]
WEB_RESULTS_PER_QUERY = 6
WEB_PAGES_TO_READ = 30     # articles fetched and mined for questions per run (broader company coverage)

# ---------------------------------------------------------------- NVIDIA NIM (daily summary + question extraction)
# Key comes from NVIDIA_API_KEY in backend/.env (never committed). Without a key the
# pipeline still runs: questions use the rule-based extractor and the summary is a template.
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
