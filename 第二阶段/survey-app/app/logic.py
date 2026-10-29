# -*- coding: utf-8 -*-
"""校验、跳转、统计。规则存在数据里，不写死某问卷。"""
from __future__ import annotations

from typing import Any


class LogicError(ValueError):
    pass


def parse_number(raw: Any, integer: bool = False) -> float | int:
    if raw is None or raw == "":
        raise LogicError("请填写数字")
    try:
        if integer:
            if isinstance(raw, bool):
                raise LogicError("必须是整数")
            if isinstance(raw, float) and not raw.is_integer():
                raise LogicError("必须是整数")
            if isinstance(raw, str) and ("." in raw.strip()):
                raise LogicError("必须是整数")
            return int(str(raw).strip())
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise LogicError("数字格式不正确") from exc


def validate_answer(question: dict, value: Any, required: bool) -> Any:
    qtype = question.get("type")
    vali = question.get("validation") or {}
    empty = value is None or value == "" or value == []
    if required and empty:
        raise LogicError("这是必答题")
    if empty:
        return None

    if qtype == "single":
        if not isinstance(value, str):
            raise LogicError("单选请选择一个选项")
        if value not in (question.get("options") or []):
            raise LogicError("选项不在题目中")
        return value

    if qtype == "multi":
        if isinstance(value, str):
            chosen = [value] if value else []
        elif isinstance(value, list):
            chosen = [str(x) for x in value]
        else:
            raise LogicError("多选格式不正确")
        opts = question.get("options") or []
        for item in chosen:
            if item not in opts:
                raise LogicError(f"选项不合法：{item}")
        n = len(chosen)
        if vali.get("exact_select") is not None and n != int(vali["exact_select"]):
            raise LogicError(f"必须选择 {vali['exact_select']} 项")
        if vali.get("min_select") is not None and n < int(vali["min_select"]):
            raise LogicError(f"至少选择 {vali['min_select']} 项")
        if vali.get("max_select") is not None and n > int(vali["max_select"]):
            raise LogicError(f"最多选择 {vali['max_select']} 项")
        return chosen

    if qtype == "text":
        text = str(value)
        if vali.get("min_len") is not None and len(text) < int(vali["min_len"]):
            raise LogicError(f"至少 {vali['min_len']} 字")
        if vali.get("max_len") is not None and len(text) > int(vali["max_len"]):
            raise LogicError(f"最多 {vali['max_len']} 字")
        return text

    if qtype == "number":
        num = parse_number(value, integer=bool(vali.get("integer")))
        if vali.get("min") is not None and num < float(vali["min"]):
            raise LogicError(f"不能小于 {vali['min']}")
        if vali.get("max") is not None and num > float(vali["max"]):
            raise LogicError(f"不能大于 {vali['max']}")
        return num

    raise LogicError("未知题型")


def match_when(when: dict, value: Any) -> bool:
    if not when:
        return False
    op = when.get("op")
    if op == "eq":
        return value == when.get("option")
    if op == "includes":
        if isinstance(value, list):
            return when.get("option") in value
        return False
    if op == "eq_number":
        try:
            return float(value) == float(when.get("value"))
        except (TypeError, ValueError):
            return False
    if op == "between":
        try:
            n = float(value)
        except (TypeError, ValueError):
            return False
        lo = when.get("min")
        hi = when.get("max")
        if lo is not None and n < float(lo):
            return False
        if hi is not None and n > float(hi):
            return False
        return True
    return False


def next_item_id(survey: dict, current_item_id: str, value: Any) -> str | None:
    """返回下一题 item_id；'end' 或超出末尾则 None。"""
    items = survey.get("items") or []
    ids = [it["item_id"] for it in items]
    for rule in survey.get("jump_rules") or []:
        if rule.get("from_item") != current_item_id:
            continue
        if match_when(rule.get("when") or {}, value):
            dest = rule.get("to_item")
            if dest in (None, "end"):
                return None
            return dest
    try:
        idx = ids.index(current_item_id)
    except ValueError:
        return None
    if idx + 1 < len(ids):
        return ids[idx + 1]
    return None


def first_item_id(survey: dict) -> str | None:
    items = survey.get("items") or []
    return items[0]["item_id"] if items else None


def summarize_question(question: dict, values: list) -> dict:
    qtype = question.get("type")
    if qtype == "single":
        counts = {opt: 0 for opt in question.get("options") or []}
        n = 0
        for v in values:
            if v in counts:
                counts[v] += 1
                n += 1
        return {
            "type": qtype,
            "options": [{"label": k, "count": c} for k, c in counts.items()],
            "total_answers": n,
        }
    if qtype == "multi":
        counts = {opt: 0 for opt in question.get("options") or []}
        n = 0
        for v in values:
            if not isinstance(v, list):
                continue
            n += 1
            for item in v:
                if item in counts:
                    counts[item] += 1
        return {
            "type": qtype,
            "options": [{"label": k, "count": c} for k, c in counts.items()],
            "total_responses": n,
        }
    if qtype == "text":
        texts = [str(v) for v in values if v is not None and v != ""]
        return {"type": qtype, "values": texts}
    if qtype == "number":
        nums = []
        for v in values:
            try:
                nums.append(float(v))
            except (TypeError, ValueError):
                continue
        avg = sum(nums) / len(nums) if nums else None
        return {"type": qtype, "values": nums, "avg": avg}
    return {"type": qtype, "values": values}
