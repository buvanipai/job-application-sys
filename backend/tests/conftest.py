"""Shared fixtures for backend API tests.
Creates real Mongo users + session_tokens (per auth_testing.md) and
returns Bearer-authenticated requests sessions hitting the public REACT_APP_BACKEND_URL.
"""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="session")
def mongo_db():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _make_user(mongo_db, label: str):
    uid = f"test-user-{label}-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"
    token = f"test_session_{uuid.uuid4().hex}"
    mongo_db.users.insert_one({
        "user_id": uid,
        "email": f"{uid}@example.com",
        "name": f"Test {label}",
        "picture": "https://via.placeholder.com/150",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mongo_db.user_sessions.insert_one({
        "user_id": uid,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return uid, token


def _client_for(token: str):
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    return s


@pytest.fixture(scope="session")
def primary_user(mongo_db):
    uid, token = _make_user(mongo_db, "primary")
    yield {"user_id": uid, "token": token, "client": _client_for(token)}
    # cleanup
    for col in ("jobs", "prospects", "campaigns", "skills", "resumes", "user_sessions", "users"):
        mongo_db[col].delete_many({"user_id": uid})
    mongo_db.users.delete_many({"user_id": uid})
    mongo_db.user_sessions.delete_many({"user_id": uid})


@pytest.fixture(scope="session")
def secondary_user(mongo_db):
    uid, token = _make_user(mongo_db, "secondary")
    yield {"user_id": uid, "token": token, "client": _client_for(token)}
    for col in ("jobs", "prospects", "campaigns", "skills", "resumes"):
        mongo_db[col].delete_many({"user_id": uid})
    mongo_db.users.delete_many({"user_id": uid})
    mongo_db.user_sessions.delete_many({"user_id": uid})


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture
def anon_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s
