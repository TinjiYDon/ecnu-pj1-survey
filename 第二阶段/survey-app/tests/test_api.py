# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

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


# ---------- 阶段二：需求变更补齐 ----------

def _mk_number_question(c, stem="年龄"):
    return c.post(
        "/api/questions",
        json={"type": "number", "stem": stem, "validation": {"integer": True, "min": 0, "max": 120}},
    ).json()["question"]


def _mk_survey_with(c, title, question_id):
    s = c.post("/api/surveys", json={"title": title, "allow_multiple": True}).json()["survey"]
    c.post(
        f"/api/surveys/{s['id']}/items",
        json={"items": [{"item_id": "q1", "question_id": question_id, "required": True}]},
    )
    return s


def test_restore_version():
    c = client()
    auth(c)
    q1 = c.post(
        "/api/questions",
        json={"type": "single", "stem": "你的性别", "options": ["男", "女"]},
    ).json()["question"]
    q2 = c.post(
        f"/api/questions/{q1['id']}/versions",
        json={"stem": "你的生理性别", "options": ["男", "女", "其他"]},
    ).json()["question"]

    r = c.post(f"/api/questions/{q1['id']}/restore")
    assert r.status_code == 200, r.text
    q3 = r.json()["question"]
    # 恢复 = 新增一版：内容回到 v1，版本链不断，来源可追溯
    assert q3["version"] == 3
    assert q3["stem"] == "你的性别"
    assert q3["options"] == ["男", "女"]
    assert q3["restored_from"] == q1["id"]
    assert q3["derived_from"] == q2["id"]
    # 旧版保持不可变
    old = c.get(f"/api/questions/{q1['id']}").json()["question"]
    assert old["stem"] == "你的性别" and old["version"] == 1
    # 最新版不能再“恢复自己”
    bad = c.post(f"/api/questions/{q3['id']}/restore")
    assert bad.status_code == 400


def test_family_usage():
    c = client()
    auth(c, "owner")
    q1 = _mk_number_question(c)
    _mk_survey_with(c, "A卷", q1["id"])
    q2 = c.post(
        f"/api/questions/{q1['id']}/versions", json={"stem": "你的年龄"}
    ).json()["question"]
    _mk_survey_with(c, "B卷", q2["id"])

    fam = c.get(f"/api/questions/{q1['id']}/usage?scope=family").json()
    assert fam["scope"] == "family" and len(fam["surveys"]) == 2
    got = {s["title"]: s["versions_used"] for s in fam["surveys"]}
    assert got["A卷"] == [1] and got["B卷"] == [2]
    # 旧的单版本口径不变
    ver = c.get(f"/api/questions/{q1['id']}/usage").json()
    assert ver["scope"] == "version"
    assert len(ver["surveys"]) == 1 and ver["surveys"][0]["title"] == "A卷"


def test_family_cross_stats():
    c = client()
    auth(c, "owner")
    q1 = _mk_number_question(c)
    sa = _mk_survey_with(c, "A卷", q1["id"])
    pa = c.post(f"/api/surveys/{sa['id']}/publish").json()["survey"]
    q2 = c.post(
        f"/api/questions/{q1['id']}/versions", json={"stem": "你的年龄"}
    ).json()["question"]
    sb = _mk_survey_with(c, "B卷", q2["id"])
    pb = c.post(f"/api/surveys/{sb['id']}/publish").json()["survey"]

    c.post(f"/api/fill/{pa['slug']}/submit", json={"answers": [{"item_id": "q1", "value": 20}]})
    c.post(f"/api/fill/{pb['slug']}/submit", json={"answers": [{"item_id": "q1", "value": 40}]})

    fam = c.get(f"/api/questions/{q1['id']}/stats?scope=family").json()
    assert fam["scope"] == "family"
    assert fam["used_in_surveys"] == 2
    assert fam["stats"]["avg"] == 30
    assert len(fam["by_version"]) == 2
    b1 = next(b for b in fam["by_version"] if b["version"] == 1)
    assert b1["stats"]["avg"] == 20 and b1["answers"] == 1
    # 单版本口径仍是旧行为
    one = c.get(f"/api/questions/{q1['id']}/stats").json()
    assert one["scope"] == "version" and one["stats"]["avg"] == 20


def test_bank_latest_and_toggle():
    c = client()
    auth(c)
    q1 = c.post("/api/questions", json={"type": "text", "stem": "自我介绍"}).json()["question"]
    c.post(f"/api/questions/{q1['id']}/versions", json={"stem": "自我介绍 v2"})
    q3 = c.post(f"/api/questions/{q1['id']}/versions", json={"stem": "自我介绍 v3"}).json()["question"]

    # 题库按族只出最新版
    bank = c.get("/api/questions?scope=bank").json()["questions"]
    fam = [q for q in bank if q["logical_id"] == q1["logical_id"]]
    assert len(fam) == 1 and fam[0]["version"] == 3
    # 移出题库（整族生效）
    c.post(f"/api/questions/{q3['id']}/bank", json={"in_bank": False})
    bank2 = c.get("/api/questions?scope=bank").json()["questions"]
    assert all(q["logical_id"] != q1["logical_id"] for q in bank2)
    # 重新加入
    c.post(f"/api/questions/{q3['id']}/bank", json={"in_bank": True})
    bank3 = c.get("/api/questions?scope=bank").json()["questions"]
    assert any(q["logical_id"] == q1["logical_id"] for q in bank3)


def test_version_unique_index():
    db = make_db()
    c = client(db)
    auth(c)
    q1 = c.post("/api/questions", json={"type": "text", "stem": "题"}).json()["question"]
    # (logical_id, version) 唯一索引：手写撞号文档必须被拒
    with pytest.raises(DuplicateKeyError):
        db.questions.insert_one({"logical_id": ObjectId(q1["logical_id"]), "version": 1})
    idx = db.questions.index_information()["logical_id_1_version_1"]
    assert idx.get("unique") is True
