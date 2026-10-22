# -*- coding: utf-8 -*-
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from .logic import LogicError, first_item_id, next_item_id, summarize_question, validate_answer
from .security import hash_password, verify_password


def now() -> datetime:
    return datetime.now(timezone.utc)


def oid(value: str | ObjectId) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    return ObjectId(str(value))


def public_user(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "username": doc["username"],
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
    }


def public_question(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "logical_id": str(doc["logical_id"]),
        "version": doc["version"],
        "derived_from": str(doc["derived_from"]) if doc.get("derived_from") else None,
        "owner_id": str(doc["owner_id"]),
        "visibility": doc.get("visibility", "private"),
        "shared_with": [str(x) for x in (doc.get("shared_with") or [])],
        "category": doc.get("category") or "",
        "in_bank": bool(doc.get("in_bank")),
        "type": doc["type"],
        "stem": doc["stem"],
        "options": doc.get("options") or [],
        "required_default": bool(doc.get("required_default")),
        "validation": doc.get("validation") or {},
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "deprecated": bool(doc.get("deprecated")),
    }


def public_survey(doc: dict, include_items: bool = True) -> dict:
    data = {
        "id": str(doc["_id"]),
        "owner_id": str(doc["owner_id"]),
        "title": doc.get("title"),
        "description": doc.get("description") or "",
        "allow_anonymous": bool(doc.get("allow_anonymous")),
        "allow_multiple": bool(doc.get("allow_multiple")),
        "deadline": doc["deadline"].isoformat() if doc.get("deadline") else None,
        "status": doc.get("status"),
        "slug": doc.get("slug"),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "published_at": doc["published_at"].isoformat() if doc.get("published_at") else None,
        "jump_rules": doc.get("jump_rules") or [],
    }
    if include_items:
        data["items"] = [
            {
                "item_id": it["item_id"],
                "question_id": str(it["question_id"]),
                "required": bool(it.get("required")),
            }
            for it in (doc.get("items") or [])
        ]
    return data


class SurveyService:
    def __init__(self, db: Database):
        self.db = db

    # ---------- users ----------
    def register(self, username: str, password: str) -> dict:
        username = (username or "").strip()
        if not username or not password:
            raise LogicError("用户名和密码不能为空")
        if self.db.users.find_one({"username": username}):
            raise LogicError("用户名已存在")
        doc = {
            "username": username,
            "password_hash": hash_password(password),
            "created_at": now(),
        }
        res = self.db.users.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc

    def login(self, username: str, password: str) -> dict:
        user = self.db.users.find_one({"username": (username or "").strip()})
        if not user or not verify_password(password, user.get("password_hash") or ""):
            raise LogicError("用户名或密码错误")
        return user

    def user_by_id(self, user_id) -> dict | None:
        return self.db.users.find_one({"_id": oid(user_id)})

    def user_by_name(self, username: str) -> dict | None:
        return self.db.users.find_one({"username": username.strip()})

    # ---------- questions ----------
    def can_view_question(self, user: dict, q: dict) -> bool:
        uid = user["_id"]
        if q["owner_id"] == uid:
            return True
        if uid in (q.get("shared_with") or []):
            return True
        return False

    def can_use_question(self, user: dict, q: dict) -> bool:
        return self.can_view_question(user, q)

    def create_question(self, owner: dict, payload: dict) -> dict:
        qtype = payload.get("type")
        if qtype not in ("single", "multi", "text", "number"):
            raise LogicError("题型不支持")
        stem = (payload.get("stem") or "").strip()
        if not stem:
            raise LogicError("题干不能为空")
        options = payload.get("options") or []
        if qtype in ("single", "multi") and len(options) < 2:
            raise LogicError("选择题至少两个选项")
        if qtype in ("text", "number"):
            options = []
        logical_id = ObjectId()
        doc = {
            "logical_id": logical_id,
            "version": 1,
            "derived_from": None,
            "owner_id": owner["_id"],
            "visibility": "private",
            "shared_with": [],
            "category": (payload.get("category") or "").strip(),
            "in_bank": bool(payload.get("in_bank", True)),
            "type": qtype,
            "stem": stem,
            "options": [str(x).strip() for x in options if str(x).strip()],
            "required_default": bool(payload.get("required_default", True)),
            "validation": payload.get("validation") or {},
            "created_at": now(),
            "deprecated": False,
        }
        res = self.db.questions.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc

    def save_new_version(self, owner: dict, base_id: str, payload: dict) -> dict:
        old = self.db.questions.find_one({"_id": oid(base_id)})
        if not old:
            raise LogicError("题目不存在")
        if old["owner_id"] != owner["_id"]:
            raise LogicError("只能修改自己的题目；被分享的题请另存为自己的新题")
        latest = self.db.questions.find({"logical_id": old["logical_id"]}).sort("version", -1).limit(1)
        latest = list(latest)[0]
        new_ver = int(latest["version"]) + 1
        stem = (payload.get("stem") or old["stem"]).strip()
        qtype = payload.get("type") or old["type"]
        options = payload.get("options") if payload.get("options") is not None else old.get("options")
        if qtype in ("text", "number"):
            options = []
        doc = {
            "logical_id": old["logical_id"],
            "version": new_ver,
            "derived_from": old["_id"],
            "owner_id": owner["_id"],
            "visibility": old.get("visibility", "private"),
            "shared_with": list(old.get("shared_with") or []),
            "category": payload.get("category", old.get("category") or ""),
            "in_bank": bool(payload.get("in_bank", old.get("in_bank", True))),
            "type": qtype,
            "stem": stem,
            "options": [str(x).strip() for x in (options or []) if str(x).strip()],
            "required_default": bool(payload.get("required_default", old.get("required_default", True))),
            "validation": payload.get("validation", old.get("validation") or {}),
            "created_at": now(),
            "deprecated": False,
        }
        res = self.db.questions.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc

    def list_questions(self, user: dict, scope: str = "own", category: str | None = None) -> list[dict]:
        uid = user["_id"]
        if scope == "shared":
            query: dict[str, Any] = {"shared_with": uid}
        elif scope == "bank":
            query = {
                "$or": [{"owner_id": uid}, {"shared_with": uid}],
                "in_bank": True,
            }
        else:
            query = {"owner_id": uid}
        if category:
            query["category"] = category
        return list(self.db.questions.find(query).sort("created_at", -1))

    def get_question(self, user: dict, qid: str) -> dict:
        q = self.db.questions.find_one({"_id": oid(qid)})
        if not q or not self.can_view_question(user, q):
            raise LogicError("题目不存在或无权查看")
        return q

    def versions(self, user: dict, logical_id: str) -> list[dict]:
        docs = list(self.db.questions.find({"logical_id": oid(logical_id)}).sort("version", 1))
        if not docs or not self.can_view_question(user, docs[0]):
            raise LogicError("无权查看该题历史")
        return docs

    def share_question(self, owner: dict, qid: str, usernames: list[str]) -> dict:
        q = self.get_question(owner, qid)
        if q["owner_id"] != owner["_id"]:
            raise LogicError("只能分享自己的题目")
        ids = list(q.get("shared_with") or [])
        for name in usernames:
            u = self.user_by_name(name)
            if not u:
                raise LogicError(f"用户不存在：{name}")
            if u["_id"] != owner["_id"] and u["_id"] not in ids:
                ids.append(u["_id"])
        self.db.questions.update_many(
            {"logical_id": q["logical_id"]},
            {"$set": {"shared_with": ids, "visibility": "shared" if ids else "private"}},
        )
        q["shared_with"] = ids
        q["visibility"] = "shared" if ids else "private"
        return q

    def question_usage(self, user: dict, qid: str) -> list[dict]:
        q = self.get_question(user, qid)
        surveys = list(self.db.surveys.find({"items.question_id": q["_id"]}))
        return surveys

    # ---------- surveys ----------
    def create_survey(self, owner: dict, payload: dict) -> dict:
        title = (payload.get("title") or "").strip()
        if not title:
            raise LogicError("问卷标题不能为空")
        deadline = payload.get("deadline")
        if isinstance(deadline, str) and deadline.strip():
            deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        elif not deadline:
            deadline = None
        doc = {
            "owner_id": owner["_id"],
            "title": title,
            "description": payload.get("description") or "",
            "allow_anonymous": bool(payload.get("allow_anonymous")),
            "allow_multiple": bool(payload.get("allow_multiple")),
            "deadline": deadline,
            "status": "draft",
            "slug": secrets.token_urlsafe(8),
            "created_at": now(),
            "published_at": None,
            "items": [],
            "jump_rules": [],
        }
        res = self.db.surveys.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc

    def my_surveys(self, owner: dict) -> list[dict]:
        return list(self.db.surveys.find({"owner_id": owner["_id"]}).sort("created_at", -1))

    def get_owned_survey(self, owner: dict, sid: str) -> dict:
        s = self.db.surveys.find_one({"_id": oid(sid), "owner_id": owner["_id"]})
        if not s:
            raise LogicError("问卷不存在")
        return s

    def update_survey_meta(self, owner: dict, sid: str, payload: dict) -> dict:
        s = self.get_owned_survey(owner, sid)
        fields = {}
        for key in ("title", "description", "allow_anonymous", "allow_multiple"):
            if key in payload:
                fields[key] = payload[key]
        if "deadline" in payload:
            d = payload["deadline"]
            if isinstance(d, str) and d.strip():
                fields["deadline"] = datetime.fromisoformat(d.replace("Z", "+00:00"))
            else:
                fields["deadline"] = None
        if fields:
            self.db.surveys.update_one({"_id": s["_id"]}, {"$set": fields})
            s.update(fields)
        return s

    def set_items(self, owner: dict, sid: str, items: list[dict]) -> dict:
        s = self.get_owned_survey(owner, sid)
        if s.get("status") != "draft":
            raise LogicError("已发布问卷不能改题目列表")
        built = []
        for i, raw in enumerate(items, start=1):
            q = self.get_question(owner, str(raw["question_id"]))
            if not self.can_use_question(owner, q):
                raise LogicError("无权使用该题目")
            built.append(
                {
                    "item_id": raw.get("item_id") or f"q{i}",
                    "question_id": q["_id"],
                    "required": bool(raw.get("required", q.get("required_default", True))),
                }
            )
        self.db.surveys.update_one({"_id": s["_id"]}, {"$set": {"items": built}})
        s["items"] = built
        return s

    def set_jump_rules(self, owner: dict, sid: str, rules: list[dict]) -> dict:
        s = self.get_owned_survey(owner, sid)
        if s.get("status") != "draft":
            raise LogicError("已发布问卷不能改跳转规则")
        item_ids = {it["item_id"] for it in (s.get("items") or [])}
        cleaned = []
        for r in rules:
            src = r.get("from_item")
            dest = r.get("to_item")
            if src not in item_ids:
                raise LogicError(f"跳转起点不存在：{src}")
            if dest not in item_ids and dest != "end":
                raise LogicError(f"跳转终点不存在：{dest}")
            cleaned.append(
                {"from_item": src, "when": r.get("when") or {}, "to_item": dest}
            )
        self.db.surveys.update_one({"_id": s["_id"]}, {"$set": {"jump_rules": cleaned}})
        s["jump_rules"] = cleaned
        return s

    def publish(self, owner: dict, sid: str) -> dict:
        s = self.get_owned_survey(owner, sid)
        if not s.get("items"):
            raise LogicError("没有题目，无法发布")
        self.db.surveys.update_one(
            {"_id": s["_id"]},
            {"$set": {"status": "published", "published_at": now()}},
        )
        s["status"] = "published"
        return s

    def close(self, owner: dict, sid: str) -> dict:
        s = self.get_owned_survey(owner, sid)
        self.db.surveys.update_one({"_id": s["_id"]}, {"$set": {"status": "closed"}})
        s["status"] = "closed"
        return s

    def get_by_slug(self, slug: str) -> dict:
        s = self.db.surveys.find_one({"slug": slug})
        if not s:
            raise LogicError("问卷不存在")
        return s

    def attach_questions(self, survey: dict) -> list[dict]:
        out = []
        for it in survey.get("items") or []:
            q = self.db.questions.find_one({"_id": it["question_id"]})
            out.append({"item": it, "question": q})
        return out

    # ---------- fill ----------
    def _fillable(self, survey: dict) -> None:
        if survey.get("status") != "published":
            raise LogicError("问卷未开放填写")
        dl = survey.get("deadline")
        if dl:
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            if now() > dl:
                raise LogicError("已过截止时间")

    def existing_response(self, survey: dict, user: dict) -> dict | None:
        return self.db.responses.find_one(
            {"survey_id": survey["_id"], "respondent_id": user["_id"]}
        )

    def submit_response(self, user: dict, slug: str, answers: list[dict], anonymous: bool = False) -> dict:
        survey = self.get_by_slug(slug)
        self._fillable(survey)
        if not survey.get("allow_multiple") and self.existing_response(survey, user):
            raise LogicError("你已经提交过这份问卷")
        if anonymous and not survey.get("allow_anonymous"):
            raise LogicError("本问卷不允许匿名")

        item_map = {it["item_id"]: it for it in survey.get("items") or []}
        q_cache: dict[str, dict] = {}
        path = []
        current = first_item_id(survey)
        given = {a.get("item_id"): a.get("value") for a in answers}

        while current:
            it = item_map.get(current)
            if not it:
                raise LogicError("跳转目标无效")
            qid = str(it["question_id"])
            if qid not in q_cache:
                q_cache[qid] = self.db.questions.find_one({"_id": it["question_id"]})
            q = q_cache[qid]
            if current not in given:
                raise LogicError(f"缺少题目作答：{current}")
            cleaned = validate_answer(q, given[current], bool(it.get("required")))
            path.append(
                {
                    "item_id": current,
                    "question_id": it["question_id"],
                    "value": cleaned,
                }
            )
            current = next_item_id(survey, current, cleaned)

        doc = {
            "survey_id": survey["_id"],
            "respondent_id": user["_id"],
            "anonymous": bool(anonymous),
            "submitted_at": now(),
            "answers": path,
        }
        res = self.db.responses.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc

    def compute_next(self, user: dict, slug: str, item_id: str, value: Any) -> dict:
        survey = self.get_by_slug(slug)
        self._fillable(survey)
        it = next((x for x in survey.get("items") or [] if x["item_id"] == item_id), None)
        if not it:
            raise LogicError("题目不存在")
        q = self.db.questions.find_one({"_id": it["question_id"]})
        cleaned = validate_answer(q, value, bool(it.get("required")))
        nxt = next_item_id(survey, item_id, cleaned)
        return {"value": cleaned, "next_item_id": nxt}

    # ---------- stats ----------
    def survey_stats(self, owner: dict, sid: str) -> dict:
        s = self.get_owned_survey(owner, sid)
        resps = list(self.db.responses.find({"survey_id": s["_id"]}))
        items_out = []
        for it in s.get("items") or []:
            q = self.db.questions.find_one({"_id": it["question_id"]})
            values = []
            for r in resps:
                for a in r.get("answers") or []:
                    if a.get("item_id") == it["item_id"]:
                        values.append(a.get("value"))
            items_out.append(
                {
                    "item_id": it["item_id"],
                    "question": public_question(q) if q else None,
                    "stats": summarize_question(q or {}, values),
                }
            )
        return {"survey": public_survey(s), "total_responses": len(resps), "items": items_out}

    def item_stats(self, owner: dict, sid: str, item_id: str) -> dict:
        all_stats = self.survey_stats(owner, sid)
        for it in all_stats["items"]:
            if it["item_id"] == item_id:
                return it
        raise LogicError("题目不在问卷中")

    def cross_question_stats(self, user: dict, qid: str) -> dict:
        q = self.get_question(user, qid)
        if q["owner_id"] != user["_id"]:
            raise LogicError("仅题目所有者可查看跨卷统计")
        values = []
        for r in self.db.responses.find({"answers.question_id": q["_id"]}):
            for a in r.get("answers") or []:
                if a.get("question_id") == q["_id"]:
                    values.append(a.get("value"))
        usage = self.question_usage(user, qid)
        return {
            "question": public_question(q),
            "used_in_surveys": len(usage),
            "stats": summarize_question(q, values),
        }
