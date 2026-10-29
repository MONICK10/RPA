# Deterministic, offline keyword → category mapping.

import re

from core.contract import normalise_skill_name

SKILL_KEYWORDS = {
    "DSA":   ["data structure", "algorithm", "complexity", "big-o", "dynamic programming",
              "graph", "tree", "sorting", "searching", "leetcode", "problem solving skills"],
    "COD":   ["python", "java", "c++", "golang", "go", "javascript", "typescript", "rust",
              "c#", "scala", "kotlin", "ruby", "php", "coding", "programming"],
    "OOD":   ["object oriented", "oop", "design pattern", "solid principle", "inheritance",
              "polymorphism", "encapsulation", "uml", "class design"],
    "APTI":  ["analytical", "quantitative", "logical reasoning", "aptitude",
              "problem-solving", "critical thinking"],
    "COMM":  ["communication", "stakeholder", "presentation", "documentation", "collaborate",
              "cross-functional", "written and verbal", "teamwork", "mentoring"],
    "AI":    ["machine learning", "deep learning", "llm", "genai", "generative ai", "nlp",
              "tensorflow", "pytorch", "scikit", "hugging face", "langchain", "rag",
              "prompt engineering", "computer vision", "model training", "ai"],
    "CLOUD": ["aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "terraform",
              "ci/cd", "cicd", "jenkins", "devops", "deployment", "microservice",
              "serverless", "lambda", "cloud"],
    "SQL":   ["sql", "mysql", "postgres", "postgresql", "oracle db", "database", "query",
              "data modeling", "schema", "etl", "warehouse", "snowflake", "bigquery",
              "power bi", "tableau", "dashboard", "nosql", "mongodb"],
    "SWE":   ["software engineering", "git", "version control", "code review", "testing",
              "unit test", "agile", "scrum", "sdlc", "debugging", "refactor",
              "maintainable", "production"],
    "SYSD":  ["system design", "architecture", "scalab", "distributed", "load balanc",
              "caching", "high availability", "throughput", "latency", "message queue",
              "kafka", "api design"],
    "NETW":  ["networking", "tcp", "http", "dns", "rest api", "socket", "protocol",
              "firewall", "load balancer", "cdn", "grpc"],
    "OS":    ["operating system", "linux", "unix", "process", "thread", "concurrency",
              "memory management", "shell", "bash", "multithread", "scheduling"],
}


# Keywords whose naive .title() output reads wrong (acronyms, brand casing,
# symbol-bearing terms). Anything not listed here falls back to .title().
DISPLAY_NAMES = {
    "ai": "AI", "llm": "LLM", "genai": "GenAI", "nlp": "NLP", "rag": "RAG",
    "sql": "SQL", "nosql": "NoSQL", "mongodb": "MongoDB", "etl": "ETL",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "mysql": "MySQL",
    "oracle db": "Oracle DB", "aws": "AWS", "gcp": "GCP", "ci/cd": "CI/CD",
    "cicd": "CI/CD", "uml": "UML", "sdlc": "SDLC", "oop": "OOP", "tcp": "TCP",
    "http": "HTTP", "dns": "DNS", "cdn": "CDN", "grpc": "gRPC",
    "api design": "API Design", "rest api": "REST API", "power bi": "Power BI",
    "tensorflow": "TensorFlow", "pytorch": "PyTorch", "scikit": "scikit-learn",
    "hugging face": "Hugging Face", "big-o": "Big O", "c++": "C++", "c#": "C#",
    "go": "Go", "php": "PHP", "sla": "SLA", "kafka": "Kafka",
}


def _display_name(keyword: str) -> str:
    keyword = keyword.strip()
    return DISPLAY_NAMES.get(keyword, keyword.title())


def _keyword_pattern(keyword: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(keyword.strip()) + r"\b")


def count_keyword_occurrences(text_lower: str, keyword: str) -> int:
    """Word-boundary occurrence count — avoids matching inside unrelated
    words (e.g. "rag" inside "coverage")."""
    return len(_keyword_pattern(keyword).findall(text_lower))


def keyword_in_text(text_lower: str, keyword: str) -> bool:
    return _keyword_pattern(keyword).search(text_lower) is not None


def _confidence_for_count(count: int) -> str:
    if count >= 3:
        return "high"
    if count == 2:
        return "medium"
    return "low"


def extract_skills(text: str, source_hint: str = "") -> list[dict]:
    """Scan text for keywords, return validated skill objects."""
    if not text:
        return []

    lowered = text.lower()
    found = {}  # normalised_name -> skill dict

    for category, keywords in SKILL_KEYWORDS.items():
        for keyword in keywords:
            match = _keyword_pattern(keyword).search(lowered)
            if match is None:
                continue
            count = count_keyword_occurrences(lowered, keyword)

            first_idx = match.start()
            start = max(0, first_idx - 60)
            end = min(len(text), first_idx + len(keyword) + 60)
            evidence = re.sub(r"\s+", " ", text[start:end]).strip()

            skill_name = _display_name(keyword)
            confidence = _confidence_for_count(count)
            key = normalise_skill_name(skill_name)

            candidate = {
                "skill_name": skill_name,
                "category_code": category,
                "evidence": evidence,
                "confidence": confidence,
            }

            existing = found.get(key)
            if existing is None or _rank(confidence) > _rank(existing["confidence"]):
                found[key] = candidate

    return sorted(found.values(), key=lambda s: (s["category_code"], s["skill_name"]))


def _rank(confidence: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}[confidence]
