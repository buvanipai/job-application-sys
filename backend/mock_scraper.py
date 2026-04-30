"""Mocked Playwright scraper, Apify+Hunter prospect discovery, Gmail SMTP sender, GCS PDF storage.
These are deterministic stand-ins. Swap with real integrations later without changing the pipeline.
"""
import random
import uuid
from datetime import datetime, timezone

SAMPLE_JOBS = [
    {
        "title": "Senior Backend Engineer",
        "company": "Parallax Systems",
        "url": "https://jobs.parallax.io/senior-backend-engineer",
        "location": "Remote • US",
        "description": (
            "We are hiring a Senior Backend Engineer to build high-throughput Python services on "
            "FastAPI, PostgreSQL, and Kafka. You will own latency-critical APIs, design event-driven "
            "pipelines, and mentor mid-level engineers. Must have 5+ years Python, strong SQL, and "
            "production experience with distributed systems."
        ),
    },
    {
        "title": "Full-Stack Engineer (React + Node)",
        "company": "Lumen Labs",
        "url": "https://lumen.works/careers/fullstack",
        "location": "NYC (Hybrid)",
        "description": (
            "Join a small product team shipping a B2B analytics suite. Stack: React, TypeScript, "
            "Node.js, Postgres, AWS. You will build features end-to-end, from schema to UI. "
            "Bonus: experience with Playwright, data pipelines, and Tailwind."
        ),
    },
    {
        "title": "Machine Learning Engineer",
        "company": "Helix AI",
        "url": "https://helix.ai/jobs/ml-engineer",
        "location": "San Francisco",
        "description": (
            "Helix is building retrieval-augmented assistants for healthcare. We need an MLE comfortable "
            "with LLM evaluation, vector search (pgvector), Python, and fast iteration. Experience with "
            "Claude/OpenAI APIs, prompt evals, and production inference required."
        ),
    },
    {
        "title": "Platform Engineer — Kubernetes",
        "company": "Northwind Cloud",
        "url": "https://northwind.cloud/jobs/platform",
        "location": "Remote • EU",
        "description": (
            "Own our Kubernetes platform across 4 regions. Deep experience with Helm, ArgoCD, "
            "Terraform, and observability (Prometheus, OpenTelemetry) required. You'll design "
            "multi-tenant isolation, cost guardrails, and developer self-service."
        ),
    },
    {
        "title": "Product Engineer",
        "company": "Kettle",
        "url": "https://kettle.so/jobs/product-engineer",
        "location": "Remote",
        "description": (
            "Small team building a delightful CRM for creators. Looking for a generalist product "
            "engineer: React, Next.js, Prisma, Postgres. You care about polish, speed, and shipping "
            "user-facing features weekly. Experience with Stripe + webhooks a plus."
        ),
    },
    {
        "title": "Data Engineer",
        "company": "Loam",
        "url": "https://loam.earth/careers/data-engineer",
        "location": "Remote • US",
        "description": (
            "Climate-tech startup hiring a Data Engineer to own pipelines: dbt, Snowflake, Airflow, "
            "Python. Will partner with scientists on soil-carbon datasets. Strong SQL, dimensional "
            "modeling, and orchestration experience required."
        ),
    },
    {
        "title": "Frontend Engineer — Design Systems",
        "company": "Stitch",
        "url": "https://stitch.design/careers/frontend",
        "location": "Remote",
        "description": (
            "Build a cross-product design system in React + TypeScript + Radix + Tailwind. "
            "Strong accessibility, Storybook, and visual regression testing chops required. "
            "Experience contributing to Shadcn-style libraries a plus."
        ),
    },
    {
        "title": "DevRel Engineer",
        "company": "Relay",
        "url": "https://relay.dev/careers/devrel",
        "location": "Remote",
        "description": (
            "Developer Relations Engineer to create tutorials, demos, and SDKs. Python + JS fluency "
            "required. Public speaking or strong written portfolio expected. You'll own our sample "
            "apps across Next.js and FastAPI."
        ),
    },
]

SAMPLE_PROSPECT_ROLES = [
    "Engineering Manager", "Senior Recruiter", "Technical Recruiter",
    "Director of Engineering", "Head of Talent", "Staff Engineer",
]

FIRST_NAMES = ["Alex", "Jordan", "Sam", "Priya", "Mei", "Diego", "Nora", "Kai", "Rhea", "Ayo"]
LAST_NAMES = ["Ortega", "Singh", "Chen", "Patel", "Müller", "Osei", "Kapoor", "Novak", "Haidari", "Ramos"]


def mock_scrape_jobs(limit: int = 6) -> list[dict]:
    """Mocked Playwright scrape. Picks a random subset and returns fresh copies."""
    picks = random.sample(SAMPLE_JOBS, k=min(limit, len(SAMPLE_JOBS)))
    return [dict(j) for j in picks]


def mock_find_prospects(company: str, n: int = 3) -> list[dict]:
    """Mocked Apify + Vibe Prospecting MCP + Hunter.io prospect discovery."""
    slug = "".join(c for c in company.lower() if c.isalnum()) or "company"
    results = []
    for i in range(n):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        role = random.choice(SAMPLE_PROSPECT_ROLES)
        email = f"{first.lower()}.{last.lower()}@{slug}.com"
        results.append({
            "name": f"{first} {last}",
            "role": role,
            "company": company,
            "email": email,
            "linkedin": f"https://linkedin.com/in/{first.lower()}-{last.lower()}-{uuid.uuid4().hex[:4]}",
            "source": random.choice(["apify+hunter (mock)", "vibe-prospecting-mcp (mock)"]),
            "confidence": random.randint(72, 96),
            "priority": random.randint(1, 3),  # 1=highest, 3=lowest
        })
    # Stable priority sort: highest first
    results.sort(key=lambda x: (x["priority"], -x["confidence"]))
    return results


def mock_send_email(to: str, subject: str, body: str) -> dict:
    """Mocked Gmail SMTP send. Returns pseudo delivery receipt."""
    return {
        "delivered": True,
        "provider": "mock-gmail-smtp",
        "message_id": f"<{uuid.uuid4().hex}@mock.gmail>",
        "to": to,
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "bytes": len(body or ""),
    }


def mock_gcs_put_pdf(job_id: str, content: str) -> dict:
    """Mocked GCS PDF upload. Returns a fake signed URL keyed by job_id."""
    object_key = f"cover-letters/{job_id}/{uuid.uuid4().hex[:8]}.pdf"
    return {
        "stored": True,
        "provider": "mock-gcs",
        "bucket": "jobpipeline-artifacts",
        "object_key": object_key,
        "signed_url": f"https://storage.googleapis.com/jobpipeline-artifacts/{object_key}?x-mock=1",
        "size_bytes": len((content or "").encode("utf-8")),
    }


def mock_company_context(company: str) -> str:
    """Mocked company research context (would be a web scraper or API in production)."""
    return (
        f"{company} is a growing technology company known for a strong engineering culture, "
        f"pragmatic product decisions, and a remote-friendly environment. Recent work includes "
        f"platform reliability, developer tooling, and customer-facing analytics. Public "
        f"communication emphasizes craft, ownership, and shipping."
    )


def mock_fetch_url(url: str) -> dict:
    """Mocked Playwright fetch of a job URL. Returns {text, title_hint, company_hint}.
    Matches known sample URLs; otherwise synthesizes a generic JD block.
    """
    for j in SAMPLE_JOBS:
        if j.get("url") and j["url"] == url:
            return {
                "text": (
                    f"{j['title']} at {j['company']}\n"
                    f"Location: {j.get('location','remote')}\n\n"
                    f"{j['description']}"
                ),
                "title_hint": j["title"],
                "company_hint": j["company"],
                "location_hint": j.get("location"),
            }
    # Unknown URL — synthesize a generic page text
    slug = url.rstrip("/").split("/")[-1][:60] or "role"
    host = url.split("/")[2] if "://" in url else "example.com"
    return {
        "text": (
            f"{slug.replace('-', ' ').title()} — {host}\n\n"
            "We are hiring a software engineer to build modern web products. "
            "Stack: Python, TypeScript, React, PostgreSQL, AWS. Remote-friendly, "
            "strong focus on shipping, craft, and collaboration. 3+ years experience preferred."
        ),
        "title_hint": None,
        "company_hint": host.split(".")[0].title(),
        "location_hint": None,
    }


# -------------------- Mock Gmail (replace with real Gmail API when OAuth keys arrive) --------------------

REPLY_TEMPLATES = {
    "ack": (
        "Thanks for applying to {company}! We've received your application and will be in "
        "touch if there's a match."
    ),
    "rejected": (
        "Thank you for your interest in {company}. After careful review we've decided to "
        "move forward with other candidates at this time."
    ),
    "progressing": (
        "Thanks for reaching out! Would love to schedule a quick chat — could you share your "
        "availability for a 30-minute call next week? We'd also like to send a short "
        "take-home assessment."
    ),
    "replied": (
        "Thanks for the note. Happy to chat more — what would be helpful to cover?"
    ),
}


def mock_gmail_synthesize_reply(prospect: dict, campaign: dict, status: str = "progressing") -> dict:
    """Build a synthetic inbound email for testing the reply pipeline.
    In production this is replaced by a real Gmail API list+get loop.
    """
    body = REPLY_TEMPLATES.get(status, REPLY_TEMPLATES["replied"]).format(
        company=(prospect or {}).get("company", "the company")
    )
    return {
        "from_email": (prospect or {}).get("email", "unknown@example.com"),
        "to_email": "you@example.com",
        "subject": "Re: " + (campaign or {}).get("subject", "your message"),
        "body": body,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
