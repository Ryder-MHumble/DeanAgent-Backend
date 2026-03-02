"""LLM enrichment for paper industry transformation analysis."""
from __future__ import annotations

import logging

from app.services.llm_service import LLMError, call_llm_json

logger = logging.getLogger(__name__)

MODEL = "google/gemini-3-flash-preview"

SYSTEM_PROMPT = """你是一位专门评估科研成果产业转化潜力的分析师，
服务于中关村人工智能研究院（ZGCAI）。

你的任务是分析一篇学生论文，输出其产业转化潜力的结构化分析卡片。

【评级标准】
A档（主动跟进）：成果类型为应用型 + 研究方向在第一梯队
B档（保持关注）：应用型+第二梯队；或第一梯队但偏理论
C档（暂不处理）：纯理论型 或 方向在第三梯队

【成果类型判断】
- 应用型：含系统/工具/平台/benchmark/dataset/开源代码/demo/prototype等工程实现内容
- 理论型：纯数学证明/综述类论文/算法改进但无新应用场景/基础科学研究
- 混合型：有实验验证的算法改进，有一定应用潜力但未达到应用型标准

【商业热度梯队】
第一梯队（明确市场需求）：大模型应用层（RAG/Agent/AI编程/代码生成）、具身智能/机器人、
  自动驾驶、AI for Science（药物发现/材料科学）、AI安全/对齐
第二梯队（商业化早期）：多模态理解与生成、合成生物学、脑机接口、量子计算应用层、卫星遥感/空天信息、数字孪生
第三梯队（商业化路径不清晰）：纯基础模型架构研究、纯理论机器学习、传统CV/NLP的增量改进

【输出JSON格式（必须严格遵守）】
{
  "grade": "A或B或C",
  "grade_reason": "判断原因（1-2句话，说明命中了哪些正向/负向信号）",
  "content_type": "applied或theoretical或mixed",
  "commercialization_tier": 1或2或3,
  "tech_summary": "用非学术语言描述这个研究解决了什么问题（1句话，给不懂技术的人看）",
  "transformation_directions": ["方向A：面向XX的XX产品，目标客户是XX", "方向B：..."],
  "maturity_level": "接近可用或需要工程化或还在早期",
  "negotiation_angle": "第一次找学生/导师聊时建议的切入角度（1-2句话，具体一些）",
  "recommendation_reason": "综合推荐理由（2-3句话，说服业务人员去主动跟进）"
}

重要注意事项：
- C档论文的 tech_summary/transformation_directions/maturity_level/
  negotiation_angle/recommendation_reason 必须为 null
- 输出必须是合法的 JSON，不得包含任何 markdown 格式或代码块标记
- transformation_directions 为列表，包含 1-3 个方向
"""


async def enrich_paper(
    title: str,
    abstract: str | None,
    venue: str | None,
    publication_date: str | None,
) -> dict:
    """Run LLM analysis on a single paper.

    Returns a validated enrichment dict with grade + analysis fields.
    Falls back to a safe C-grade default on any failure.
    """
    abstract_text = abstract if abstract else "（摘要未获取，请仅基于标题进行分析）"
    venue_text = venue if venue else "未知"

    user_prompt = (
        f"论文标题：{title}\n"
        f"摘要：{abstract_text}\n"
        f"发表日期：{publication_date or '未知'}\n"
        f"发表场所/期刊/会议：{venue_text}"
    )

    try:
        raw = await call_llm_json(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
            model=MODEL,
            temperature=0.1,
            max_tokens=1000,
            stage="paper_transfer",
            article_title=title,
            dimension="paper_transfer",
        )
        if not isinstance(raw, dict):
            logger.warning("LLM returned non-dict response for '%s', using default", title[:50])
            return _default_enrichment()
        return _validate(raw)
    except (LLMError, Exception) as e:
        logger.warning("LLM enrichment failed for '%s': %s", title[:50], e)
        return _default_enrichment()


def _validate(raw: dict) -> dict:
    """Validate and normalize LLM response dict."""
    grade = raw.get("grade", "C")
    if grade not in ("A", "B", "C"):
        grade = "C"

    result: dict = {
        "grade": grade,
        "grade_reason": str(raw.get("grade_reason") or ""),
        "content_type": raw.get("content_type", "mixed"),
        "commercialization_tier": int(raw.get("commercialization_tier") or 3),
        "tech_summary": None,
        "transformation_directions": None,
        "maturity_level": None,
        "negotiation_angle": None,
        "recommendation_reason": None,
    }

    if grade in ("A", "B"):
        result["tech_summary"] = raw.get("tech_summary") or None
        dirs = raw.get("transformation_directions")
        result["transformation_directions"] = dirs if isinstance(dirs, list) else None
        ml = raw.get("maturity_level") or ""
        result["maturity_level"] = (
            ml if ml in ("接近可用", "需要工程化", "还在早期") else None
        )
        result["negotiation_angle"] = raw.get("negotiation_angle") or None
        result["recommendation_reason"] = raw.get("recommendation_reason") or None

    return result


def _default_enrichment() -> dict:
    return {
        "grade": "C",
        "grade_reason": "LLM 分析失败，默认归为 C 档",
        "content_type": "mixed",
        "commercialization_tier": 3,
        "tech_summary": None,
        "transformation_directions": None,
        "maturity_level": None,
        "negotiation_angle": None,
        "recommendation_reason": None,
    }
