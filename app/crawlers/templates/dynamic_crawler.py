from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.utils.http_client import fetch_page as http_fetch_page
from app.crawlers.utils.selector_parser import (
    DetailResult,
    parse_detail_html,
    parse_list_items,
)

logger = logging.getLogger(__name__)

_JS_FETCH_SNIPPET = """
async (url) => {
    const resp = await fetch(url);
    return await resp.text();
}
"""

_WINDOW_STATE_SNIPPET = """
() => {
    const states = [];
    const candidates = [
        ["__NEXT_DATA__", window.__NEXT_DATA__],
        ["__NUXT__", window.__NUXT__],
        ["__INITIAL_STATE__", window.__INITIAL_STATE__],
        ["__DATA__", window.__DATA__],
        ["__APOLLO_STATE__", window.__APOLLO_STATE__],
        ["__PRELOADED_STATE__", window.__PRELOADED_STATE__],
    ];
    for (const [name, value] of candidates) {
        if (value !== undefined && value !== null) {
            states.push({name, value});
        }
    }
    return states;
}
"""


class DynamicPageCrawler(BaseCrawler):
    """
    Template crawler for JS-rendered pages via Playwright.
    Uses same selector pattern as StaticHTMLCrawler but renders with Playwright first.

    Config fields (same as StaticHTMLCrawler plus):
      - wait_for: CSS selector or "networkidle" to wait for
      - wait_timeout: milliseconds (default 10000)
      - actions: optional browser actions before parsing the list page
      - next_button / max_pages: optional pagination support for multi-page lists
      - capture_page_json: bool (default False) — attach lightweight page JSON preview
      - detail_use_playwright: bool (default True) — use Playwright or httpx for detail pages
      - detail_fetch_js: bool (default False) — use JS fetch() for detail pages
        (avoids page.goto anti-bot issues; requires same-origin detail URLs)
    """

    async def _fetch_detail_with_js_fetch(
        self, page: Any, detail_url: str, detail_selectors: dict,
    ) -> DetailResult | None:
        """Fetch detail page HTML via JS fetch() in the browser context.

        Shares cookies with the current page, avoids page.goto navigation issues
        caused by anti-bot systems (e.g. Clear-Site-Data headers).
        """
        try:
            detail_html = await page.evaluate(_JS_FETCH_SNIPPET, detail_url)
            return parse_detail_html(detail_html, detail_selectors, detail_url, self.config)
        except Exception as e:
            logger.warning("Failed to JS-fetch detail page %s: %s", detail_url, e)
            return None

    async def _fetch_detail_with_playwright(
        self, page: Any, detail_url: str, detail_selectors: dict, wait_timeout: int,
    ) -> DetailResult | None:
        """Fetch a detail page using Playwright (same context, shares cookies)."""
        try:
            await page.goto(detail_url, wait_until="domcontentloaded", timeout=wait_timeout)
            detail_wait = detail_selectors.get("content", "body")
            try:
                await page.wait_for_selector(detail_wait, timeout=wait_timeout)
            except Exception:
                pass  # Content may already be available or selector optional
            detail_html = await page.content()

            return parse_detail_html(detail_html, detail_selectors, detail_url, self.config)
        except Exception as e:
            logger.warning("Failed to fetch detail page %s: %s", detail_url, e)
            return None

    async def _fetch_detail_with_httpx(
        self, detail_url: str, detail_selectors: dict,
    ) -> DetailResult | None:
        """Fetch a detail page using httpx (faster, for sites without JS protection)."""
        try:
            detail_html = await http_fetch_page(
                detail_url,
                headers=self.config.get("headers"),
                encoding=self.config.get("encoding"),
                request_delay=self.config.get("request_delay"),
            )
            return parse_detail_html(detail_html, detail_selectors, detail_url, self.config)
        except Exception as e:
            logger.warning("Failed to fetch detail page %s: %s", detail_url, e)
            return None

    async def _wait_for_content(self, page: Any, wait_for: str, wait_timeout: int) -> None:
        try:
            if wait_for == "networkidle":
                await page.wait_for_load_state("networkidle", timeout=wait_timeout)
            else:
                await page.wait_for_selector(wait_for, timeout=wait_timeout)
        except Exception as exc:
            logger.warning(
                "Wait condition %r timed out for %s, falling back to current HTML: %s",
                wait_for,
                self.source_id,
                exc,
            )

    async def _run_actions(self, page: Any, actions: list[dict[str, Any]], wait_timeout: int) -> None:
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_type = str(action.get("type") or "").strip().lower()
            selector = action.get("selector")
            delay_ms = int(action.get("delay_ms", action.get("delay", 0)) or 0)
            if action_type == "click" and selector:
                await page.click(selector)
            elif action_type == "fill" and selector:
                await page.fill(selector, str(action.get("value") or ""))
            elif action_type == "scroll":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif action_type == "wait":
                if selector:
                    await page.wait_for_selector(selector, timeout=wait_timeout)
                else:
                    delay_ms = max(delay_ms, int(action.get("milliseconds", 0) or 0))
            if delay_ms > 0:
                await page.wait_for_timeout(delay_ms)

    async def _extract_page_json_preview(self, page: Any, html: str) -> dict[str, Any] | None:
        try:
            states = await page.evaluate(_WINDOW_STATE_SNIPPET)
        except Exception:
            states = None
        if isinstance(states, list) and states:
            state = states[0]
            if isinstance(state, dict):
                return {
                    "source": str(state.get("name") or "window_state"),
                    "preview": self._shrink_json(state.get("value")),
                }

        patterns = [
            ("__NEXT_DATA__", r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'),
            ("__NUXT__", r'window\.__NUXT__\s*=\s*(\{.*?\})\s*;'),
            ("__INITIAL_STATE__", r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;'),
            ("__DATA__", r'window\.__DATA__\s*=\s*(\{.*?\})\s*;'),
        ]
        for source, pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if not match:
                continue
            try:
                parsed = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            return {"source": source, "preview": self._shrink_json(parsed)}
        return None

    @classmethod
    def _shrink_json(cls, value: Any, *, depth: int = 0) -> Any:
        if depth >= 2:
            if isinstance(value, dict):
                return {"type": "object", "size": len(value)}
            if isinstance(value, list):
                return {"type": "array", "size": len(value)}
            return value
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for index, (key, nested) in enumerate(value.items()):
                if index >= 5:
                    result["__truncated__"] = len(value) - 5
                    break
                result[str(key)] = cls._shrink_json(nested, depth=depth + 1)
            return result
        if isinstance(value, list):
            preview = [cls._shrink_json(item, depth=depth + 1) for item in value[:3]]
            if len(value) > 3:
                preview.append({"__truncated__": len(value) - 3})
            return preview
        return value

    async def fetch_and_parse(self) -> list[CrawledItem]:
        from app.crawlers.utils.playwright_pool import get_page

        url = self.config["url"]
        selectors = self.config.get("selectors", {})
        base_url = self.config.get("base_url", url)
        keyword_filter = self.config.get("keyword_filter", [])
        keyword_blacklist = self.config.get("keyword_blacklist", [])
        detail_selectors = self.config.get("detail_selectors")
        detail_use_playwright = self.config.get("detail_use_playwright", True)
        detail_fetch_js = self.config.get("detail_fetch_js", False)
        wait_for = self.config.get("wait_for", "networkidle")
        wait_timeout = self.config.get("wait_timeout", 10000)
        actions = self.config.get("actions") or []
        next_button = self.config.get("next_button")
        max_pages = max(1, int(self.config.get("max_pages", 1)))
        next_page_wait_for = self.config.get("next_page_wait_for", wait_for)
        capture_page_json = bool(self.config.get("capture_page_json"))

        warmup_url = self.config.get("warmup_url")
        storage_state_path = self.config.get("storage_state_path")
        save_storage_state = bool(self.config.get("save_storage_state"))

        async with get_page(
            storage_state_path=storage_state_path,
            save_storage_state=save_storage_state,
        ) as page:
            if warmup_url:
                try:
                    await page.goto(warmup_url, wait_until="domcontentloaded", timeout=wait_timeout)
                except Exception:
                    pass  # warmup may return non-200; we just need the cookies/session

            await page.goto(url, wait_until="domcontentloaded", timeout=wait_timeout)
            await self._wait_for_content(page, wait_for, wait_timeout)
            if actions:
                await self._run_actions(page, actions, wait_timeout)
                await self._wait_for_content(page, wait_for, wait_timeout)

            raw_items_with_page_data: list[tuple[Any, dict[str, Any]]] = []
            seen_urls: set[str] = set()
            for page_number in range(1, max_pages + 1):
                html = await page.content()
                page_json_preview = None
                if capture_page_json:
                    page_json_preview = await self._extract_page_json_preview(page, html)

                soup = BeautifulSoup(html, "lxml")
                parsed_items = parse_list_items(
                    soup, selectors, base_url, keyword_filter, keyword_blacklist
                )
                for raw in parsed_items:
                    if raw.url in seen_urls:
                        continue
                    seen_urls.add(raw.url)
                    raw_items_with_page_data.append(
                        (
                            raw,
                            {
                                "page_number": page_number,
                                "page_json_preview": page_json_preview,
                            },
                        )
                    )

                if not next_button or page_number >= max_pages:
                    break
                try:
                    await page.click(next_button)
                except Exception:
                    break
                await self._wait_for_content(page, next_page_wait_for, wait_timeout)

            request_delay = self.config.get("request_delay", 0)

            items: list[CrawledItem] = []
            for raw, page_data in raw_items_with_page_data:
                content = author = content_hash = content_html = pdf_url = None
                images = None

                if detail_selectors:
                    if request_delay:
                        await asyncio.sleep(request_delay)
                    if detail_fetch_js:
                        detail = await self._fetch_detail_with_js_fetch(
                            page, raw.url, detail_selectors,
                        )
                    elif detail_use_playwright:
                        detail = await self._fetch_detail_with_playwright(
                            page, raw.url, detail_selectors, wait_timeout,
                        )
                    else:
                        detail = await self._fetch_detail_with_httpx(
                            raw.url, detail_selectors,
                        )
                    if detail:
                        if raw.published_at is None:
                            raw.published_at = detail.published_at
                        content = detail.content
                        content_html = detail.content_html
                        author = detail.author
                        content_hash = detail.content_hash
                        pdf_url = detail.pdf_url
                        images = detail.images

                extra = {
                    "page_number": page_data["page_number"],
                }
                if page_data.get("page_json_preview") is not None:
                    extra["page_json_preview"] = page_data["page_json_preview"]
                if pdf_url:
                    extra["pdf_url"] = pdf_url
                if images:
                    extra["images"] = images

                items.append(
                    CrawledItem(
                        title=raw.title,
                        url=raw.url,
                        published_at=raw.published_at,
                        author=author,
                        content=content,
                        content_html=content_html,
                        content_hash=content_hash,
                        source_id=self.source_id,
                        dimension=self.config.get("dimension"),
                        tags=self.config.get("tags", []),
                        extra=extra,
                    )
                )

        return items
