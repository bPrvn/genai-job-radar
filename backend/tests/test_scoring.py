from radar import research, scoring


def test_title_filter():
    assert scoring.title_relevant("Senior Applied AI Engineer - AiDP")
    assert scoring.title_relevant("Machine Learning Engineer 3")
    assert scoring.title_relevant("Lead Engineer - Gen AI")
    assert not scoring.title_relevant("Account Executive, AI Sales")
    assert not scoring.title_relevant("Software Engineering Intern - ML")
    assert not scoring.title_relevant("Backend Engineer")


def test_location():
    assert scoring.location_ok("Bengaluru, Karnataka, India")
    assert scoring.location_ok("Hyderabad")
    assert not scoring.location_ok("Seattle, WA, USA")


def test_years_takes_first_requirement():
    jd = "Minimum qualifications: 8 years of experience in software development. 5 years with ML."
    assert scoring.min_years(jd) == 8
    assert scoring.min_years("3+ years of professional experience") == 3
    assert scoring.min_years("no experience requirement") is None


def test_fit_prefers_genai_mid_senior():
    good = scoring.fit_score("Senior GenAI Engineer", "Bengaluru, India", "RAG LLM python fastapi agents", 5)
    stretch = scoring.fit_score("Staff ML Engineer", "Bengaluru, India", "python", 10)
    assert good > 80 > stretch


def test_keywords():
    kws = scoring.keywords("Build RAG pipelines with LangGraph agents on AWS, evaluate with LLM-as-judge")
    assert {"RAG / retrieval", "LangChain / LangGraph", "Agents / tool use", "Cloud (AWS/Azure/GCP)", "Evaluation"} <= set(kws)


def test_rule_extractor_and_rounds():
    text = """Round 2
    1. How would you design a RAG system for 10M documents?
    2. Explain the KV cache in transformers.
    Tell me about a time you disagreed with your manager?
    We had lunch."""
    qs = research.rule_extract(text)
    assert len(qs) == 2  # the behavioural line has no technical word; lunch is not a question
    assert research.classify(qs[0]) == "LLM system design"
    assert research.classify(qs[1]) == "GenAI depth"
    assert research.classify("Tell me about a time you failed") == "Behavioural"


def test_question_cleanup():
    assert research.clean_question("**Question 8:** How to use stop sequence in LLMs?") == "How to use stop sequence in LLMs?"
    assert research.clean_question("Q3. What is RAG?") == "What is RAG?"
    assert research.rule_extract("What it fixes:** latency and database load for repeated reads.") == []
    assert research.classify("What is a context window in LLM architecture?") == "GenAI depth"
    assert research.classify("How do you handle an API request failure?") == "Backend"
