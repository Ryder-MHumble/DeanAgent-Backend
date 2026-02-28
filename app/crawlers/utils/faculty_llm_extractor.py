"""LLM-enhanced faculty field extractor.

Uses LLM to intelligently extract and map faculty information from raw HTML/text
to ScholarRecord schema fields. Handles complex cases like:
- Separating name from title (e.g., "张亚勤创始院长/讲席教授" → name="张亚勤", position="创始院长/讲席教授")
- Extracting research areas from long bio text
- Parsing education background
- Identifying academic titles and honors
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.services.llm_service import call_llm_json, LLMError

logger = logging.getLogger(__name__)


EXTRACTION_SYSTEM_PROMPT = """你是一个专业的学术信息提取助手。你的任务是从高校教师个人主页的文本内容中提取结构化信息。

提取规则：
1. **姓名分离**：如果姓名和职称混在一起（如"张亚勤创始院长/讲席教授"），只提取纯姓名部分
2. **职称提取**：提取所有职称信息（教授/副教授/研究员/院长等），多个职称用逗号分隔
3. **研究方向**：从简介中提取研究领域关键词，返回数组
4. **学术头衔**：识别院士/长江学者/杰青/优青等荣誉称号
5. **教育背景**：提取博士/硕士毕业院校和年份
6. **联系方式**：提取邮箱、电话、办公室地址

输出格式：严格的 JSON 对象，包含以下字段（如果信息不存在则为空字符串或空数组）：
{
  "name": "纯姓名（中文）",
  "name_en": "英文姓名（如果有）",
  "position": "职称（多个用逗号分隔）",
  "research_areas": ["研究方向1", "研究方向2"],
  "academic_titles": ["学术头衔1", "学术头衔2"],
  "is_academician": true/false,
  "bio": "个人简介（提取主要段落，去除冗余）",
  "email": "邮箱地址",
  "phone": "电话",
  "office": "办公室地址",
  "phd_institution": "博士毕业院校",
  "phd_year": "博士毕业年份"
}

注意：
- 只提取明确存在的信息，不要推测或编造
- 研究方向要具体（如"机器学习"而非"人工智能"）
- 学术头衔只包含正式称号（院士/长江学者/杰青/优青/国家特聘专家等）
"""


async def extract_faculty_fields_with_llm(
    raw_name: str,
    raw_bio: str,
    raw_position: str = "",
    detail_html_text: str = "",
) -> dict[str, Any]:
    """Use LLM to extract and refine faculty fields from raw crawled data.

    Args:
        raw_name: Raw name text from list page (may contain title)
        raw_bio: Raw bio text from list or detail page
        raw_position: Raw position text from list page (optional)
        detail_html_text: Full text content from detail page (optional)

    Returns:
        Dict with extracted fields matching ScholarRecord schema
    """
    # Construct prompt with all available information
    prompt_parts = [
        "请从以下教师信息中提取结构化数据：\n",
        f"**原始姓名字段**: {raw_name}",
    ]

    if raw_position:
        prompt_parts.append(f"**原始职称字段**: {raw_position}")

    if raw_bio:
        prompt_parts.append(f"**简介**: {raw_bio[:500]}")  # Limit bio length

    if detail_html_text:
        # Extract meaningful text, limit length
        clean_text = _clean_html_text(detail_html_text)
        prompt_parts.append(f"**详情页内容**: {clean_text[:1500]}")

    prompt = "\n\n".join(prompt_parts)

    try:
        result = await call_llm_json(
            prompt=prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=2000,
        )

        # Validate and normalize result
        if not isinstance(result, dict):
            logger.warning("LLM returned non-dict result for %s", raw_name)
            return _fallback_extraction(raw_name, raw_bio, raw_position)

        # Ensure all required fields exist with correct types
        normalized = {
            "name": str(result.get("name", raw_name)),
            "name_en": str(result.get("name_en", "")),
            "position": str(result.get("position", raw_position)),
            "research_areas": _ensure_list(result.get("research_areas", [])),
            "academic_titles": _ensure_list(result.get("academic_titles", [])),
            "is_academician": bool(result.get("is_academician", False)),
            "bio": str(result.get("bio", raw_bio)),
            "email": str(result.get("email", "")),
            "phone": str(result.get("phone", "")),
            "office": str(result.get("office", "")),
            "phd_institution": str(result.get("phd_institution", "")),
            "phd_year": str(result.get("phd_year", "")),
        }

        logger.info("LLM extracted fields for %s: position=%s, research_areas=%d, titles=%d",
                    normalized["name"], normalized["position"],
                    len(normalized["research_areas"]), len(normalized["academic_titles"]))

        return normalized

    except LLMError as e:
        logger.warning("LLM extraction failed for %s: %s", raw_name, e)
        return _fallback_extraction(raw_name, raw_bio, raw_position)
    except Exception as e:
        logger.error("Unexpected error in LLM extraction for %s: %s", raw_name, e)
        return _fallback_extraction(raw_name, raw_bio, raw_position)


def _clean_html_text(html_text: str) -> str:
    """Clean HTML text by removing excessive whitespace and common noise."""
    # Remove multiple spaces/newlines
    text = re.sub(r'\s+', ' ', html_text)
    # Remove common navigation/footer text patterns
    text = re.sub(r'(版权所有|Copyright|联系我们|Contact|返回|Back|首页|Home).*', '', text)
    return text.strip()


def _ensure_list(value: Any) -> list[str]:
    """Ensure value is a list of strings."""
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value:
        return [value]
    return []


def _fallback_extraction(raw_name: str, raw_bio: str, raw_position: str) -> dict[str, Any]:
    """Fallback extraction using simple heuristics when LLM fails."""
    # Try to separate name from title using common patterns
    name = raw_name
    position = raw_position

    # Pattern: "姓名 职称" or "姓名职称"
    if not position:
        # Look for common title keywords
        title_pattern = r'(.+?)(教授|副教授|研究员|副研究员|讲师|助理教授|院长|副院长|主任|副主任|所长|副所长)'
        match = re.match(title_pattern, raw_name)
        if match:
            name = match.group(1).strip()
            position = match.group(2).strip()

    return {
        "name": name,
        "name_en": "",
        "position": position,
        "research_areas": [],
        "academic_titles": [],
        "is_academician": False,
        "bio": raw_bio,
        "email": "",
        "phone": "",
        "office": "",
        "phd_institution": "",
        "phd_year": "",
    }
