# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import mongomock
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import set_db  # noqa: E402
from app.main import app  # noqa: E402


def make_db():
    return mongomock.MongoClient().survey_app


def client(db=None):
    set_db(db if db is not None else make_db())
    return TestClient(app)


def auth(c, name="alice", password="pw123"):
    r = c.post("/api/auth/register", json={"username": name, "password": password})
    assert r.status_code == 200, r.text
    r = c.post("/api/auth/login", json={"username": name, "password": password})
    assert r.status_code == 200
    return r.json()["user"]


def test_register_login_me():
    c = client()
    auth(c)
    me = c.get("/api/auth/me").json()
    assert me["ok"] and me["user"]["username"] == "alice"


def test_create_question_and_new_version():
    c = client()
    auth(c)
    r = c.post(
        "/api/questions",
        json={
            "type": "single",
            "stem": "你的性别",
            "options": ["男", "女", "其他"],
            "category": "人口统计",
        },
    )
    q = r.json()["question"]
    assert q["version"] == 1
    r2 = c.post(
        f"/api/questions/{q['id']}/versions",
        json={"stem": "你的生理性别", "options": ["男", "女", "其他"]},
    )
    q2 = r2.json()["question"]
    assert q2["version"] == 2
    assert q2["derived_from"] == q["id"]
    assert q2["logical_id"] == q["logical_id"]
    old = c.get(f"/api/questions/{q['id']}").json()["question"]
    assert old["stem"] == "你的性别"


def test_jump_validate_submit_and_stats():
    c = client()
    auth(c, "owner")
    gender = c.post(
        "/api/questions",
        json={"type": "single", "stem": "性别", "options": ["男", "女"]},
    ).json()["question"]
    age = c.post(
        "/api/questions",
        json={
            "type": "number",
            "stem": "年龄",
            "validation": {"min": 0, "max": 120, "integer": True},
        },
    ).json()["question"]
    fruit = c.post(
        "/api/questions",
        json={
            "type": "multi",
            "stem": "水果",
            "options": ["苹果", "香蕉", "西瓜"],
            "validation": {"min_select": 1, "max_select": 2},
        },
    ).json()["question"]

    s = c.post("/api/surveys", json={"title": "新生调查", "allow_multiple": True}).json()["survey"]
    sid = s["id"]
    c.post(
        f"/api/surveys/{sid}/items",
        json={
            "items": [
                {"item_id": "q1", "question_id": gender["id"], "required": True},
                {"item_id": "q2", "question_id": age["id"], "required": True},
                {"item_id": "q3", "question_id": fruit["id"], "required": True},
            ]
        },
    )
    c.put(
        f"/api/surveys/{sid}/jump_rules",
        json={
            "jump_rules": [
                {"from_item": "q1", "when": {"op": "eq", "option": "男"}, "to_item": "q3"},
            ]
        },
    )
    pub = c.post(f"/api/surveys/{sid}/publish").json()["survey"]
    slug = pub["slug"]

    auth(c, "bob")
    # 选男应跳过年龄；若仍交年龄也应以服务端路径为准——缺少 q2 应成功
    r = c.post(
        f"/api/fill/{slug}/submit",
        json={
            "answers": [
                {"item_id": "q1", "value": "男"},
                {"item_id": "q3", "value": ["苹果"]},
            ]
        },
    )
    assert r.status_code == 200, r.text

    # 多选超限
    bad = c.post(
        f"/api/fill/{slug}/submit",
        json={
            "answers": [
                {"item_id": "q1", "value": "女"},
                {"item_id": "q2", "value": 20},
                {"item_id": "q3", "value": ["苹果", "香蕉", "西瓜"]},
            ]
        },
    )
    assert bad.status_code == 400

    c.post("/api/auth/login", json={"username": "owner", "password": "pw123"})
    st = c.get(f"/api/surveys/{sid}/stats").json()
    assert st["total_responses"] == 1
    q1 = next(x for x in st["items"] if x["item_id"] == "q1")
    assert q1["stats"]["total_answers"] == 1


def test_share_and_usage_and_cross_stats():
    c = client()
    auth(c, "teacher")
    q = c.post(
        "/api/questions",
        json={"type": "number", "stem": "你的年龄", "validation": {"integer": True, "min": 0, "max": 120}},
    ).json()["question"]
    c.post("/api/auth/register", json={"username": "stu", "password": "pw123"})
    sh = c.post(f"/api/questions/{q['id']}/share", json={"username": "stu"})
    assert sh.status_code == 200

    c2 = TestClient(app)
    c2.post("/api/auth/login", json={"username": "stu", "password": "pw123"})
    s = c2.post("/api/surveys", json={"title": "作业问卷"}).json()["survey"]
    c2.post(
        f"/api/surveys/{s['id']}/items",
        json={"items": [{"item_id": "q1", "question_id": q["id"], "required": True}]},
    )
    pub = c2.post(f"/api/surveys/{s['id']}/publish").json()["survey"]
    c2.post(f"/api/fill/{pub['slug']}/submit", json={"answers": [{"item_id": "q1", "value": 19}]})

    usage = c.get(f"/api/questions/{q['id']}/usage").json()
    assert len(usage["surveys"]) == 1
    cross = c.get(f"/api/questions/{q['id']}/stats").json()
    assert cross["stats"]["avg"] == 19
