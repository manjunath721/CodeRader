"""
Synthetic demo workspace builder (Documentation/DEMO_GUIDE.md).

Builds a real local Git repository with deliberately engineered properties,
then runs it through the real ingestion + analysis pipeline (the same code
path a real repository would use) — so every number the demo shows is
genuinely computed, not hard-coded.

`ensure_demo_project` is idempotent: if a demo project with a complete
analysis run already exists it is returned as-is, so the demo workspace is
always available without accumulating duplicates. Only `is_demo` projects
are ever considered — real user projects are never touched.
"""
import os
import tempfile
from datetime import datetime, timedelta

from git import Actor, Repo
from sqlalchemy.orm import Session

from app.models.project import Project, Repository
from app.services.analysis_pipeline import run_analysis
from app.services.query_service import get_latest_complete_run

DEMO_PROJECT_NAME = "CodeRadar Demo"

# 10-person synthetic team.
TEAM = {
    "Rahul": "rahul@example.com",
    "Priya": "priya@example.com",
    "Akash": "akash@example.com",
    "Bob": "bob@example.com",
    "Divya": "divya@example.com",
    "Kiran": "kiran@example.com",
    "Meera": "meera@example.com",
    "Arjun": "arjun@example.com",
    "Sana": "sana@example.com",
    "Vikram": "vikram@example.com",
}


def _complex_payment_func(i: int) -> str:
    return (
        f"def process_payment_{i}(amount, card, opts):\n"
        "    if amount > 0:\n"
        "        for attempt in range(3):\n"
        "            if card and opts:\n"
        "                for rule in opts:\n"
        "                    if rule == 'strict':\n"
        "                        return True\n"
        "    return False\n"
    )


def _complex_search_func(i: int) -> str:
    return (
        f"def rank_{i}(query, docs, boost):\n"
        "    scored = []\n"
        "    for d in docs:\n"
        "        if query in d:\n"
        "            for term in query.split():\n"
        "                if term in d:\n"
        "                    scored.append((d, boost))\n"
        "    scored.sort(key=lambda x: x[1])\n"
        "    return scored\n"
    )


def build_demo_repo() -> str:
    """Creates the synthetic git history and returns the repo directory."""
    d = tempfile.mkdtemp(prefix="coderesilience_demo_")
    repo = Repo.init(d)
    base = datetime(2026, 1, 10)

    def commit(path: str, content: str, author: str, when: datetime, msg: str) -> None:
        full = os.path.join(d, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "a") as f:
            f.write(content)
        repo.index.add([path])
        os.environ["GIT_AUTHOR_DATE"] = when.isoformat()
        os.environ["GIT_COMMITTER_DATE"] = when.isoformat()
        repo.index.commit(msg, author=Actor(author, TEAM[author]), committer=Actor(author, TEAM[author]))

    # --- payment: Rahul dominant (concentrated knowledge, high risk), sparse docs ---
    for i in range(18):
        commit(
            "src/payment/gateway.py", _complex_payment_func(i),
            "Rahul", base + timedelta(days=i * 8), f"payment gateway work {i}",
        )
    commit(
        "src/payment/gateway.py", "\n# priya patch\ndef refund(amount):\n    return -amount\n",
        "Priya", base + timedelta(days=150), "priya payment refund fix",
    )

    # --- billing: imports payment.gateway (real dependency edge), Rahul + Priya + Divya ---
    commit(
        "src/billing/invoice.py", "from src.payment.gateway import process_payment_0\n\n",
        "Rahul", base + timedelta(days=18), "billing: wire up payment gateway",
    )
    for i in range(4):
        commit(
            "src/billing/invoice.py",
            f"def create_invoice_{i}(user):\n    if user:\n        return True\n    return False\n",
            "Rahul", base + timedelta(days=20 + i * 15), f"billing work {i}",
        )
    for i in range(4):
        commit(
            "src/billing/invoice.py",
            f"def credit_{i}(user):\n    return user\n",
            "Priya", base + timedelta(days=30 + i * 15), f"priya billing work {i}",
        )
    commit(
        "src/billing/invoice.py", "def invoice_note(txt):\n    return txt.strip()\n",
        "Divya", base + timedelta(days=120), "divya billing note helper",
    )

    # --- checkout: imports billing.invoice (real edge), Akash-led with Kiran ---
    commit(
        "src/checkout/flow.py", "from src.billing.invoice import create_invoice_0\n\n",
        "Akash", base + timedelta(days=24), "checkout: wire up billing",
    )
    for i in range(6):
        commit(
            "src/checkout/flow.py",
            f"def checkout_step_{i}(cart):\n    if cart:\n        return True\n    return False\n",
            "Akash", base + timedelta(days=25 + i * 10), f"checkout work {i}",
        )
    for i in range(3):
        commit(
            "src/checkout/flow.py",
            f"def validate_{i}(cart):\n    return bool(cart)\n",
            "Kiran", base + timedelta(days=60 + i * 12), f"kiran checkout validation {i}",
        )

    # --- auth: well-documented, spread across 6 developers (low risk) ---
    for i, name in enumerate(["Rahul", "Priya", "Akash", "Bob", "Divya", "Sana", "Kiran", "Meera"]):
        commit(
            "src/auth/login.py",
            f'"""Authentication helper {i} — validates credentials against the directory."""\n'
            f"def authenticate_{i}(user, pw):\n"
            '    """Return True when the credential pair is valid."""\n'
            "    if user and pw:\n"
            "        return True\n"
            "    return False\n",
            name, base + timedelta(days=i * 6), f"auth work {i}",
        )

    # --- notifications: Meera-led, depends on payment + billing (fan-in demo) ---
    commit(
        "src/notifications/dispatch.py",
        "from src.payment.gateway import process_payment_0\n"
        "from src.billing.invoice import create_invoice_0\n\n",
        "Meera", base + timedelta(days=40), "notifications: wire up payment + billing events",
    )
    for i in range(7):
        commit(
            "src/notifications/dispatch.py",
            f"def notify_{i}(user, msg):\n    if user and msg:\n        return True\n    return False\n",
            "Meera", base + timedelta(days=42 + i * 9), f"notifications work {i}",
        )
    for i in range(2):
        commit(
            "src/notifications/dispatch.py",
            f"def digest_{i}(users):\n    return list(users)\n",
            "Priya", base + timedelta(days=90 + i * 10), f"priya notification digest {i}",
        )

    # --- reporting: Divya + Sana shared (healthy spread), depends on billing + checkout ---
    commit(
        "src/reporting/summary.py",
        '"""Monthly reporting rollups over billing and checkout data."""\n'
        "from src.billing.invoice import create_invoice_0\n"
        "from src.checkout.flow import checkout_step_0\n\n",
        "Divya", base + timedelta(days=50), "reporting: wire up billing + checkout",
    )
    for i in range(4):
        commit(
            "src/reporting/summary.py",
            f'"""Aggregate helper {i}."""\n'
            f"def build_summary_{i}(rows):\n"
            '    """Summarize rows into totals."""\n'
            "    total = 0\n"
            "    for r in rows:\n"
            "        total += 1\n"
            "    return total\n",
            "Divya" if i % 2 == 0 else "Sana", base + timedelta(days=55 + i * 11),
            f"reporting aggregate {i}",
        )
    for i in range(4):
        commit(
            "src/reporting/summary.py",
            f'"""Export helper {i}."""\n'
            f"def export_{i}(rows):\n"
            '    """Export rows to CSV."""\n'
            "    return [str(r) for r in rows]\n",
            "Sana" if i % 2 == 0 else "Divya", base + timedelta(days=60 + i * 11),
            f"reporting export {i}",
        )
    commit(
        "src/reporting/summary.py",
        "def quarter(q):\n    return (q - 1) // 3 + 1\n",
        "Kiran", base + timedelta(days=130), "kiran quarter helper",
    )

    # --- search: Vikram solo (second bus-factor-1 area), depends on auth + reporting ---
    commit(
        "src/search/index.py",
        "from src.auth.login import authenticate_0\n"
        "from src.reporting.summary import build_summary_0\n\n",
        "Vikram", base + timedelta(days=70), "search: wire up auth + reporting",
    )
    for i in range(10):
        commit(
            "src/search/index.py", _complex_search_func(i),
            "Vikram", base + timedelta(days=72 + i * 7), f"search ranking work {i}",
        )
    commit(
        "src/search/index.py", "def tokenize(q):\n    return q.lower().split()\n",
        "Sana", base + timedelta(days=145), "sana tokenizer patch",
    )

    # --- deployment: thin docs, Bob + Arjun (doc-gap demo, no internal deps) ---
    for i in range(3):
        commit(
            "src/deployment/deploy.py",
            f"def stage_{i}(env):\n    if env == 'prod':\n        for retry in range(2):\n            pass\n    return env\n",
            "Bob", base + timedelta(days=100 + i * 10), f"deployment work {i}",
        )
    for i in range(2):
        commit(
            "src/deployment/deploy.py",
            f"def rollback_{i}(env):\n    return env\n",
            "Arjun", base + timedelta(days=115 + i * 10), f"arjun rollback {i}",
        )

    return d


def ensure_demo_project(db: Session) -> dict:
    """Idempotent demo bootstrap: reuse a fully-analyzed demo project if one
    exists, otherwise build + analyze a fresh one. Never touches non-demo
    projects."""
    existing = (
        db.query(Project)
        .filter(Project.is_demo.is_(True))
        .order_by(Project.created_at.desc())
        .all()
    )
    for demo in existing:
        run = get_latest_complete_run(db, demo.id)
        if run is not None:
            return {
                "project_id": str(demo.id),
                "analysis_run_id": str(run.id),
                "status": "complete",
                "created": False,
            }

    repo_path = build_demo_repo()
    project = Project(
        name=DEMO_PROJECT_NAME,
        description="Synthetic demo workspace (10 developers, 8 modules) — repository-derived estimates.",
        is_demo=True,
    )
    db.add(project)
    db.flush()
    db.add(Repository(project_id=project.id, url=repo_path, provider="local"))
    db.commit()

    run = run_analysis(db, project)
    return {
        "project_id": str(project.id),
        "analysis_run_id": str(run.id),
        "status": run.status,
        "created": True,
    }
