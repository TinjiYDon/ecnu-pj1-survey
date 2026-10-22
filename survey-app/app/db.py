# -*- coding: utf-8 -*-
from pymongo import MongoClient, ASCENDING
from pymongo.database import Database

from .config import MONGO_URI, DB_NAME

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db = _client[DB_NAME]
        ensure_indexes(_db)
    return _db


def set_db(db: Database) -> None:
    """测试用：注入 mongomock 数据库。"""
    global _db, _client
    _db = db
    _client = None
    ensure_indexes(db)


def ensure_indexes(db: Database) -> None:
    db.users.create_index("username", unique=True)
    db.questions.create_index([("logical_id", ASCENDING), ("version", ASCENDING)])
    db.questions.create_index("owner_id")
    db.questions.create_index("category")
    db.questions.create_index("in_bank")
    db.questions.create_index("shared_with")
    db.surveys.create_index("owner_id")
    db.surveys.create_index("slug", unique=True, sparse=True)
    db.surveys.create_index("status")
    db.responses.create_index("survey_id")
    db.responses.create_index("answers.question_id")
    db.responses.create_index([("survey_id", ASCENDING), ("respondent_id", ASCENDING)])
