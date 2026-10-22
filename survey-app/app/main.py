# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import SECRET_KEY, SESSION_MAX_AGE
from .db import get_db
from .logic import LogicError
from .services import (
    SurveyService,
    public_question,
    public_survey,
    public_user,
)

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="问卷系统（大作业一）")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=SESSION_MAX_AGE, same_site="lax")


def svc() -> SurveyService:
    return SurveyService(get_db())


def current_user(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        return None
    return svc().user_by_id(uid)


def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise LogicError("请先登录")
    return user


@app.exception_handler(LogicError)
async def logic_handler(request: Request, exc: LogicError):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    request.session["flash"] = str(exc)
    refer = request.headers.get("referer") or "/"
    return RedirectResponse(refer, status_code=303)


def flash_pop(request: Request) -> str | None:
    return request.session.pop("flash", None)


def ctx(request: Request, **extra):
    data = {"request": request, "user": current_user(request), "flash": flash_pop(request)}
    data.update(extra)
    return data


# ---------- pages ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", ctx(request))


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("auth.html", ctx(request, mode="register"))


@app.post("/register")
def register_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = svc().register(username, password)
    request.session["user_id"] = str(user["_id"])
    request.session["flash"] = "注册成功"
    return RedirectResponse("/surveys", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("auth.html", ctx(request, mode="login"))


@app.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = svc().login(username, password)
    request.session["user_id"] = str(user["_id"])
    return RedirectResponse("/surveys", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/surveys", response_class=HTMLResponse)
def surveys_page(request: Request):
    user = require_user(request)
    return templates.TemplateResponse(
        "surveys.html", ctx(request, surveys=[public_survey(s) for s in svc().my_surveys(user)])
    )


@app.get("/surveys/new", response_class=HTMLResponse)
def survey_new_page(request: Request):
    require_user(request)
    return templates.TemplateResponse("survey_new.html", ctx(request))


@app.post("/surveys/new")
def survey_new_post(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    allow_anonymous: str | None = Form(None),
    allow_multiple: str | None = Form(None),
    deadline: str = Form(""),
):
    user = require_user(request)
    s = svc().create_survey(
        user,
        {
            "title": title,
            "description": description,
            "allow_anonymous": bool(allow_anonymous),
            "allow_multiple": bool(allow_multiple),
            "deadline": deadline,
        },
    )
    return RedirectResponse(f"/surveys/{s['_id']}", status_code=303)


@app.get("/surveys/{sid}", response_class=HTMLResponse)
def survey_detail(request: Request, sid: str):
    user = require_user(request)
    s = svc().get_owned_survey(user, sid)
    qs = svc().list_questions(user, scope="bank")
    attached = svc().attach_questions(s)
    return templates.TemplateResponse(
        "survey_detail.html",
        ctx(
            request,
            survey=public_survey(s),
            attached=attached,
            bank=[public_question(q) for q in qs],
        ),
    )


@app.post("/surveys/{sid}/items")
def survey_add_item(request: Request, sid: str, question_id: str = Form(...), required: str | None = Form(None)):
    user = require_user(request)
    s = svc().get_owned_survey(user, sid)
    items = list(s.get("items") or [])
    items.append({"question_id": question_id, "required": bool(required)})
    svc().set_items(user, sid, items)
    request.session["flash"] = "已加入问卷"
    return RedirectResponse(f"/surveys/{sid}", status_code=303)


@app.post("/surveys/{sid}/jumps")
def survey_add_jump(
    request: Request,
    sid: str,
    from_item: str = Form(...),
    op: str = Form(...),
    option: str = Form(""),
    to_item: str = Form(...),
):
    user = require_user(request)
    s = svc().get_owned_survey(user, sid)
    rules = list(s.get("jump_rules") or [])
    when = {"op": op, "option": option} if op in ("eq", "includes") else {"op": op, "value": option}
    rules.append({"from_item": from_item, "when": when, "to_item": to_item})
    svc().set_jump_rules(user, sid, rules)
    request.session["flash"] = "已添加跳转规则"
    return RedirectResponse(f"/surveys/{sid}", status_code=303)


@app.post("/surveys/{sid}/publish")
def survey_publish(request: Request, sid: str):
    user = require_user(request)
    s = svc().publish(user, sid)
    request.session["flash"] = f"已发布，链接 /survey/{s['slug']}"
    return RedirectResponse(f"/surveys/{sid}", status_code=303)


@app.post("/surveys/{sid}/close")
def survey_close(request: Request, sid: str):
    user = require_user(request)
    svc().close(user, sid)
    request.session["flash"] = "已关闭"
    return RedirectResponse(f"/surveys/{sid}", status_code=303)


@app.get("/surveys/{sid}/stats", response_class=HTMLResponse)
def survey_stats_page(request: Request, sid: str):
    user = require_user(request)
    stats = svc().survey_stats(user, sid)
    return templates.TemplateResponse("stats.html", ctx(request, stats=stats, cross=False))


@app.get("/questions", response_class=HTMLResponse)
def questions_page(request: Request, scope: str = "own"):
    user = require_user(request)
    qs = svc().list_questions(user, scope=scope)
    return templates.TemplateResponse(
        "questions.html", ctx(request, questions=[public_question(q) for q in qs], scope=scope)
    )


@app.get("/questions/new", response_class=HTMLResponse)
def question_new_page(request: Request):
    require_user(request)
    return templates.TemplateResponse("question_form.html", ctx(request, mode="new", question=None))


@app.post("/questions/new")
def question_new_post(
    request: Request,
    qtype: str = Form(...),
    stem: str = Form(...),
    options: str = Form(""),
    category: str = Form(""),
    in_bank: str | None = Form(None),
    min_select: str = Form(""),
    max_select: str = Form(""),
    min_len: str = Form(""),
    max_len: str = Form(""),
    num_min: str = Form(""),
    num_max: str = Form(""),
    integer: str | None = Form(None),
):
    user = require_user(request)
    validation = {}
    if qtype == "multi":
        if min_select:
            validation["min_select"] = int(min_select)
        if max_select:
            validation["max_select"] = int(max_select)
    if qtype == "text":
        if min_len:
            validation["min_len"] = int(min_len)
        if max_len:
            validation["max_len"] = int(max_len)
    if qtype == "number":
        if num_min:
            validation["min"] = float(num_min)
        if num_max:
            validation["max"] = float(num_max)
        validation["integer"] = bool(integer)
    q = svc().create_question(
        user,
        {
            "type": qtype,
            "stem": stem,
            "options": [x.strip() for x in options.split("\n") if x.strip()],
            "category": category,
            "in_bank": bool(in_bank),
            "validation": validation,
        },
    )
    request.session["flash"] = "已创建题目 v1"
    return RedirectResponse(f"/questions/{q['_id']}", status_code=303)


@app.get("/questions/{qid}", response_class=HTMLResponse)
def question_detail(request: Request, qid: str):
    user = require_user(request)
    q = svc().get_question(user, qid)
    vers = svc().versions(user, str(q["logical_id"]))
    usage = svc().question_usage(user, qid)
    return templates.TemplateResponse(
        "question_detail.html",
        ctx(
            request,
            question=public_question(q),
            versions=[public_question(v) for v in vers],
            usage=[public_survey(s, include_items=False) for s in usage],
        ),
    )


@app.post("/questions/{qid}/save")
def question_save_version(
    request: Request,
    qid: str,
    stem: str = Form(...),
    options: str = Form(""),
    category: str = Form(""),
):
    user = require_user(request)
    old = svc().get_question(user, qid)
    payload = {
        "stem": stem,
        "options": [x.strip() for x in options.split("\n") if x.strip()] or old.get("options"),
        "category": category,
        "type": old["type"],
        "validation": old.get("validation") or {},
        "in_bank": old.get("in_bank", True),
    }
    new = svc().save_new_version(user, qid, payload)
    request.session["flash"] = f"已保存为 v{new['version']}，旧问卷仍使用旧版本"
    return RedirectResponse(f"/questions/{new['_id']}", status_code=303)


@app.post("/questions/{qid}/share")
def question_share(request: Request, qid: str, username: str = Form(...)):
    user = require_user(request)
    svc().share_question(user, qid, [username])
    request.session["flash"] = f"已分享给 {username}"
    return RedirectResponse(f"/questions/{qid}", status_code=303)


@app.get("/questions/{qid}/stats-cross", response_class=HTMLResponse)
def question_cross_stats(request: Request, qid: str):
    user = require_user(request)
    stats = svc().cross_question_stats(user, qid)
    return templates.TemplateResponse("stats.html", ctx(request, stats=stats, cross=True))


@app.get("/survey/{slug}", response_class=HTMLResponse)
def fill_page(request: Request, slug: str):
    user = require_user(request)
    s = svc().get_by_slug(slug)
    attached = svc().attach_questions(s)
    return templates.TemplateResponse(
        "fill.html",
        ctx(request, survey=public_survey(s), attached=attached, slug=slug),
    )


@app.post("/survey/{slug}/submit")
async def fill_submit(request: Request, slug: str, anonymous: str | None = Form(None)):
    user = require_user(request)
    form = await request.form()
    s = svc().get_by_slug(slug)
    answers = []
    for it in s.get("items") or []:
        iid = it["item_id"]
        q = svc().db.questions.find_one({"_id": it["question_id"]})
        if q and q["type"] == "multi":
            values = form.getlist(iid)
            answers.append({"item_id": iid, "value": list(values)})
        else:
            answers.append({"item_id": iid, "value": form.get(iid)})
    svc().submit_response(user, slug, answers, anonymous=bool(anonymous))
    request.session["flash"] = "提交成功"
    return RedirectResponse("/", status_code=303)


# ---------- JSON API ----------
@app.post("/api/auth/register")
def api_register(payload: dict):
    user = svc().register(payload.get("username", ""), payload.get("password", ""))
    return {"ok": True, "user": public_user(user)}


@app.post("/api/auth/login")
def api_login(request: Request, payload: dict):
    user = svc().login(payload.get("username", ""), payload.get("password", ""))
    request.session["user_id"] = str(user["_id"])
    return {"ok": True, "user": public_user(user)}


@app.post("/api/auth/logout")
def api_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/auth/me")
def api_me(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "未登录"}, status_code=401)
    return {"ok": True, "user": public_user(user)}


@app.get("/api/questions")
def api_questions(request: Request, scope: str = "own", category: str | None = None):
    user = require_user(request)
    qs = svc().list_questions(user, scope=scope, category=category)
    return {"ok": True, "questions": [public_question(q) for q in qs]}


@app.post("/api/questions")
def api_create_question(request: Request, payload: dict):
    user = require_user(request)
    q = svc().create_question(user, payload)
    return {"ok": True, "question": public_question(q)}


@app.get("/api/questions/{qid}")
def api_get_question(request: Request, qid: str):
    user = require_user(request)
    q = svc().get_question(user, qid)
    return {"ok": True, "question": public_question(q)}


@app.post("/api/questions/{qid}/versions")
def api_new_version(request: Request, qid: str, payload: dict):
    user = require_user(request)
    q = svc().save_new_version(user, qid, payload)
    return {"ok": True, "question": public_question(q), "message": f"已保存为 v{q['version']}"}


@app.get("/api/questions/logical/{logical_id}/versions")
def api_versions(request: Request, logical_id: str):
    user = require_user(request)
    vers = svc().versions(user, logical_id)
    return {"ok": True, "versions": [public_question(v) for v in vers]}


@app.post("/api/questions/{qid}/share")
def api_share(request: Request, qid: str, payload: dict):
    user = require_user(request)
    names = payload.get("usernames") or ([payload.get("username")] if payload.get("username") else [])
    q = svc().share_question(user, qid, [n for n in names if n])
    return {"ok": True, "question": public_question(q)}


@app.get("/api/questions/{qid}/usage")
def api_usage(request: Request, qid: str):
    user = require_user(request)
    usage = svc().question_usage(user, qid)
    return {"ok": True, "surveys": [public_survey(s, include_items=False) for s in usage]}


@app.get("/api/questions/{qid}/stats")
def api_q_stats(request: Request, qid: str):
    user = require_user(request)
    return {"ok": True, **svc().cross_question_stats(user, qid)}


@app.get("/api/surveys")
def api_surveys(request: Request):
    user = require_user(request)
    return {"ok": True, "surveys": [public_survey(s) for s in svc().my_surveys(user)]}


@app.post("/api/surveys")
def api_create_survey(request: Request, payload: dict):
    user = require_user(request)
    s = svc().create_survey(user, payload)
    return {"ok": True, "survey": public_survey(s)}


@app.get("/api/surveys/{sid}")
def api_get_survey(request: Request, sid: str):
    user = require_user(request)
    s = svc().get_owned_survey(user, sid)
    attached = svc().attach_questions(s)
    return {
        "ok": True,
        "survey": public_survey(s),
        "items": [
            {"item": {"item_id": a["item"]["item_id"], "required": a["item"]["required"], "question_id": str(a["item"]["question_id"])},
             "question": public_question(a["question"]) if a["question"] else None}
            for a in attached
        ],
    }


@app.post("/api/surveys/{sid}/items")
def api_set_items(request: Request, sid: str, payload: dict):
    user = require_user(request)
    s = svc().set_items(user, sid, payload.get("items") or [])
    return {"ok": True, "survey": public_survey(s)}


@app.put("/api/surveys/{sid}/jump_rules")
def api_jumps(request: Request, sid: str, payload: dict):
    user = require_user(request)
    s = svc().set_jump_rules(user, sid, payload.get("jump_rules") or [])
    return {"ok": True, "survey": public_survey(s)}


@app.post("/api/surveys/{sid}/publish")
def api_publish(request: Request, sid: str):
    user = require_user(request)
    s = svc().publish(user, sid)
    return {"ok": True, "survey": public_survey(s)}


@app.post("/api/surveys/{sid}/close")
def api_close(request: Request, sid: str):
    user = require_user(request)
    s = svc().close(user, sid)
    return {"ok": True, "survey": public_survey(s)}


@app.get("/api/surveys/{sid}/stats")
def api_survey_stats(request: Request, sid: str):
    user = require_user(request)
    return {"ok": True, **svc().survey_stats(user, sid)}


@app.get("/api/surveys/{sid}/stats/items/{item_id}")
def api_item_stats(request: Request, sid: str, item_id: str):
    user = require_user(request)
    return {"ok": True, "item": svc().item_stats(user, sid, item_id)}


@app.get("/api/fill/{slug}")
def api_fill_get(request: Request, slug: str):
    require_user(request)
    s = svc().get_by_slug(slug)
    attached = svc().attach_questions(s)
    return {
        "ok": True,
        "survey": public_survey(s),
        "items": [
            {
                "item_id": a["item"]["item_id"],
                "required": a["item"]["required"],
                "question": public_question(a["question"]) if a["question"] else None,
            }
            for a in attached
        ],
    }


@app.post("/api/fill/{slug}/next")
def api_fill_next(request: Request, slug: str, payload: dict):
    user = require_user(request)
    out = svc().compute_next(user, slug, payload.get("item_id"), payload.get("value"))
    return {"ok": True, **out}


@app.post("/api/fill/{slug}/submit")
def api_fill_submit(request: Request, slug: str, payload: dict):
    user = require_user(request)
    doc = svc().submit_response(
        user, slug, payload.get("answers") or [], anonymous=bool(payload.get("anonymous"))
    )
    return {"ok": True, "response_id": str(doc["_id"])}
