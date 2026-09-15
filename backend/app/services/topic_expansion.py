"""当用户仅提供课程主题、缺少细节时，由大模型补全可落地的教学内容。"""
import json
import re
from typing import Any, Dict, List, Optional

from .llm_service import llm_service


def _is_sparse(key_points: Optional[List], teaching_text: str) -> bool:
    """判断是否缺少足够上下文，需要自动扩写。"""
    tt = (teaching_text or "").strip()
    if len(tt) >= 40:
        return False
    kps = key_points or []
    if not kps:
        return True
    total_chars = sum(len(str(x).strip()) for x in kps)
    if len(kps) < 2 and total_chars < 30:
        return True
    if total_chars < 50:
        return True
    return False


def _extract_json_from_text(text: str) -> Optional[str]:
    """从LLM返回的文本中提取JSON对象，支持多种格式容错。"""
    if not text or not text.strip():
        return None
    t = text.strip()

    # 1. 去掉 markdown 代码围栏
    if "```json" in t:
        start = t.find("```json") + 7
        end = t.find("```", start)
        if end > start:
            t = t[start:end].strip()
    elif "```" in t:
        start = t.find("```") + 3
        end = t.find("```", start)
        if end > start:
            t = t[start:end].strip()

    # 2. 找到第一个 { 和最后一个 } 之间的内容
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        return t[start:end + 1]

    return None


def _safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """安全解析JSON，带多重容错策略。"""
    if not text or not text.strip():
        return None

    # 策略1：直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 策略2：提取后解析
    extracted = _extract_json_from_text(text)
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    # 策略3：修复常见JSON错误后重试
    if extracted:
        try:
            # 修复：缺少引号的键名
            fixed = re.sub(r'(?<=\{|\s)(\w+)(?=\s*:)', r'"\1"', extracted)
            # 修复：单引号改双引号
            fixed = fixed.replace("'", '"')
            # 修复：尾部多余逗号
            fixed = re.sub(r',\s*}', '}', fixed)
            fixed = re.sub(r',\s*]', ']', fixed)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    return None


def expand_topic_for_instruction(
    topic: str,
    audience: str,
    subject: str,
    duration: int,
    *,
    level: str = "",
    extra_hint: str = "",
) -> Dict[str, Any]:
    """
    为主题生成可直接用于课堂与教案的具体内容（概念、模块、实例、易错点等）。
    返回 dict；失败时返回空 dict。
    """
    if not topic or not str(topic).strip():
        return {}

    hint = (extra_hint or "").strip()
    level_line = f"学段/场景：{level}\n" if level else ""

    prompt = f"""你是资深一线教师与课程设计师。用户可能只提供了课程主题，没有细节。请根据主题自动推理并补全**本节课真实可讲**的具体内容（禁止空话、禁止只写「掌握基本概念」）。

{level_line}课程主题：{topic}
学科/课程：{subject}
面向对象：{audience}
课时时长：{duration} 分钟
补充线索（可无）：{hint if hint else "无"}

请输出**唯一一个合法 JSON 对象**（不要 markdown 代码围栏），字段如下：
{{
  "teaching_synopsis": "用 100-180 字说明本节课讲什么、学完后学生能做什么（可观察的行为）",
  "session_objectives": ["可测目标1", "可测目标2", "可测目标3"],
  "core_concepts": ["每条 25-60 字：概念名 + 一句教师课堂可讲的解释", "至少 5 条"],
  "knowledge_modules_for_slides": ["与 PPT 知识点页对应的模块标题1", "模块标题2", "模块标题3", "可 4-8 个"],
  "classroom_examples": ["2-4 个可在课堂上口述的短例子（含情境）"],
  "guided_questions": ["3-5 个课堂提问，用于启发思考"],
  "misconceptions": ["2-4 个学生易错点及一句话纠正"],
  "formative_assessment": ["1-2 个随堂小测或练习（说清楚测什么）"],
  "board_or_ppt_outline": ["板书或课件建议要点 4-8 条，可与页码思路对应"]
}}

要求：内容必须与「{subject}」和「{topic}」强相关；若主题较宽，请自动聚焦为**一节{duration}分钟课**可完成的子范围。"""

    try:
        raw = llm_service.chat(prompt, [])
        if not raw or not raw.strip():
            print(f"topic_expansion: LLM返回为空 (topic={topic})")
            return {}

        # 检查是否是生成失败的错误消息
        raw_stripped = raw.strip()
        if raw_stripped.startswith("生成失败:") or raw_stripped.startswith("[演示模式]"):
            print(f"topic_expansion: LLM返回错误消息: {raw_stripped[:200]}")
            return {}

        data = _safe_json_parse(raw_stripped)
        if isinstance(data, dict):
            return data
        else:
            print(f"topic_expansion 解析失败: 无法从响应中提取JSON对象。响应前200字：{raw_stripped[:200]}")
    except Exception as e:
        print(f"topic_expansion 解析失败: {e}")

    return {}


def enrich_for_ppt(
    topic: str,
    duration: int,
    audience: str,
    subject: str,
    key_points: Optional[List],
    reference_docs: Optional[List],
) -> Dict[str, Any]:
    """
    为 PPT 流水线准备 key_points 与 teaching_content。
    返回: key_points, teaching_content, expansion
    """
    kp_in = [str(x).strip() for x in (key_points or []) if str(x).strip()]
    base_tc = " ".join(kp_in)
    refs = [str(x).strip() for x in (reference_docs or []) if str(x).strip()]
    ref = "\n\n".join(refs)
    if ref:
        base_tc = f"{base_tc}\n\n【参考资料摘录】\n{ref}".strip()

    expansion: Dict[str, Any] = {}
    if _is_sparse(kp_in, base_tc):
        expansion = expand_topic_for_instruction(
            topic, audience, subject, duration, extra_hint=ref
        )

    if not expansion:
        tc = base_tc if base_tc else f"课程主题：{topic}；学科：{subject}；对象：{audience}。"
        return {"key_points": kp_in, "teaching_content": tc, "expansion": {}}

    parts: List[str] = []
    syn = expansion.get("teaching_synopsis") or ""
    if syn:
        parts.append(syn)
    objs = expansion.get("session_objectives") or []
    if objs:
        parts.append("本课学习目标：" + "；".join(str(x) for x in objs[:6]))
    concepts = expansion.get("core_concepts") or []
    if concepts:
        parts.append("核心要点：" + " ".join(str(x) for x in concepts[:10]))
    exs = expansion.get("classroom_examples") or []
    if exs:
        parts.append("课堂实例：" + " ".join(str(x) for x in exs[:5]))
    mis = expansion.get("misconceptions") or []
    if mis:
        parts.append("易错辨析：" + " ".join(str(x) for x in mis[:5]))
    fq = expansion.get("formative_assessment") or []
    if fq:
        parts.append("过程性评价：" + " ".join(str(x) for x in fq[:3]))

    teaching_content = "\n".join(parts)

    kp_out = list(kp_in)
    for c in concepts:
        cs = str(c).strip()
        if cs and cs not in kp_out and len(kp_out) < 16:
            kp_out.append(cs)

    if len(kp_out) < 4 and concepts:
        kp_out = [str(x).strip() for x in concepts[:12] if str(x).strip()]

    return {"key_points": kp_out, "teaching_content": teaching_content, "expansion": expansion}


def enrich_for_lesson_plan(
    level: str,
    subject: str,
    topic: str,
    duration: int,
    requirements: str,
) -> str:
    """在教案需求过短時拼接可落地的扩写，供后续 Prompt 使用。"""
    req = (requirements or "").strip()
    if len(req) >= 50:
        return req

    exp = expand_topic_for_instruction(
        topic, "学生", subject, duration, level=level, extra_hint=req
    )
    if not exp:
        return req

    lines = [req] if req else []
    lines.append("\n【系统根据主题补全的具体教学线索（请融入教案各模块，可改写）】")
    if exp.get("teaching_synopsis"):
        lines.append("教学概要：" + str(exp["teaching_synopsis"]))
    if exp.get("session_objectives"):
        lines.append("可测目标：" + "；".join(str(x) for x in exp["session_objectives"][:6]))
    if exp.get("core_concepts"):
        lines.append("核心概念与讲法：" + " ".join(str(x) for x in exp["core_concepts"][:8]))
    if exp.get("guided_questions"):
        lines.append("课堂提问：" + " ".join(str(x) for x in exp["guided_questions"][:6]))
    if exp.get("misconceptions"):
        lines.append("易错与纠错：" + " ".join(str(x) for x in exp["misconceptions"][:5]))
    if exp.get("board_or_ppt_outline"):
        lines.append("板书/课件线索：" + " ".join(str(x) for x in exp["board_or_ppt_outline"][:8]))
    return "\n".join(lines).strip()
