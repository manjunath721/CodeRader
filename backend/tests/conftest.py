import os
import tempfile
from datetime import datetime, timedelta

import pytest
from git import Actor, Repo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - registers all tables
from app.core.db import Base


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def synthetic_repo():
    """
    A small local Git repo with two modules and a deliberately skewed
    contribution pattern (mirrors docs/demo.md), for pipeline integration tests.
    """
    d = tempfile.mkdtemp()
    repo = Repo.init(d)
    base = datetime(2026, 1, 15)

    def commit(path: str, content: str, author: str, email: str, when: datetime, msg: str) -> None:
        full = os.path.join(d, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "a") as f:
            f.write(content)
        repo.index.add([path])
        os.environ["GIT_AUTHOR_DATE"] = when.isoformat()
        os.environ["GIT_COMMITTER_DATE"] = when.isoformat()
        repo.index.commit(msg, author=Actor(author, email), committer=Actor(author, email))

    for i in range(8):
        commit(
            "src/payment/charge.py",
            f"def f{i}(x):\n    if x:\n        return x\n    return 0\n",
            "Rahul", "rahul@example.com", base + timedelta(days=i * 20), f"payment work {i}",
        )
    commit(
        "src/payment/charge.py", "def refund(x):\n    return -x\n",
        "Priya", "priya@example.com", base + timedelta(days=150), "priya payment fix",
    )
    for i, (name, email) in enumerate(
        [("Rahul", "rahul@example.com"), ("Priya", "priya@example.com"),
         ("Akash", "akash@example.com"), ("Bob", "bob@example.com")]
    ):
        commit(
            "src/auth/login.py",
            f"def a{i}(u,p):\n    if u and p:\n        return True\n    return False\n",
            name, email, base + timedelta(days=i * 5), f"auth work {i}",
        )
    return d
