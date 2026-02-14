"""Targeted investigation of each university source — tries sub-pages and identifies correct selectors.

Usage: python scripts/investigate_sources.py
"""
import asyncio
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Article link patterns (year-based URLs, /info/ paths, etc.)
ARTICLE_LINK_RE = re.compile(
    r"(info/\d+/\d+|/\d{4}/\d{2,4}/|/20[12]\d|article|detail|content|/t\d{8}_)"
)


async def fetch(url: str, timeout: float = 15.0) -> tuple[str | None, str | None]:
    """Fetch URL. Returns (html, error)."""
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, verify=False
        ) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
            final_url = str(resp.url)
            return resp.text, None
    except Exception as e:
        return None, str(e)[:100]


def find_article_lists(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Find all list-like structures containing article links."""
    results = []

    # Find all links that look like article links
    article_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urljoin(base_url, href)
        if ARTICLE_LINK_RE.search(href) or ARTICLE_LINK_RE.search(full_url):
            article_links.append(a)

    if not article_links:
        return results

    # Group article links by their common parent containers
    parent_groups = {}
    for a in article_links:
        # Walk up to find a list-like parent
        parent = a.parent
        for _ in range(6):
            if parent is None:
                break
            siblings = parent.find_all(recursive=False)
            if len(siblings) >= 3:
                parent_id = id(parent)
                if parent_id not in parent_groups:
                    parent_groups[parent_id] = {
                        "element": parent,
                        "tag": parent.name,
                        "class": " ".join(parent.get("class", [])),
                        "links": [],
                    }
                parent_groups[parent_id]["links"].append(a)
                break
            parent = parent.parent

    for group in parent_groups.values():
        if len(group["links"]) < 2:
            continue

        el = group["element"]
        # Determine list item selector
        children = el.find_all(recursive=False)
        child_tags = [c.name for c in children]
        most_common_tag = max(set(child_tags), key=child_tags.count) if child_tags else "div"

        # Build samples
        samples = []
        for a in group["links"][:5]:
            title = a.get_text(strip=True)[:80]
            href = a.get("href", "")

            # Find date near this link
            date_text = ""
            item = a.parent
            for _ in range(3):
                if item is None:
                    break
                for date_el in item.find_all(["span", "em", "time", "div", "td", "p"]):
                    dt = date_el.get_text(strip=True)
                    if re.match(r"^\d{4}[-./]\d{1,2}[-./]?\d{0,2}$", dt):
                        date_text = dt
                        break
                    if re.match(r"^\d{1,2}[-./]\d{1,2}$", dt):
                        date_text = dt
                        break
                if date_text:
                    break
                item = item.parent

            samples.append({"title": title, "href": href, "date": date_text})

        # Build CSS selector for the container
        container_sel = el.name
        if el.get("class"):
            container_sel += "." + ".".join(el["class"])

        results.append({
            "container": container_sel,
            "item_tag": most_common_tag,
            "article_count": len(group["links"]),
            "samples": samples,
        })

    # Sort by article count
    results.sort(key=lambda x: x["article_count"], reverse=True)
    return results


# Map of source_id -> list of URLs to try (homepage + sub-pages)
SOURCE_URLS = {
    "tsinghua_news": [
        "https://www.tsinghua.edu.cn/news/zhsx.htm",
        "https://www.tsinghua.edu.cn/news/zxdt.htm",
    ],
    "pku_news": [
        "https://news.pku.edu.cn/xwzh/index.htm",
        "https://news.pku.edu.cn/ttxw/index.htm",
    ],
    "ustc_news": [
        "https://news.ustc.edu.cn/xwbl.htm",
        "https://news.ustc.edu.cn/zhxw.htm",
    ],
    "zju_news": [
        "https://www.zju.edu.cn/main.htm",
        "https://www.zju.edu.cn/38199/list.htm",
        "https://www.zju.edu.cn/2025/list.htm",
    ],
    "fudan_news": [
        "https://news.fudan.edu.cn/",
        "https://news.fudan.edu.cn/sdbd/list.htm",
    ],
    "moe_renshi": [
        "https://www.moe.gov.cn/jyb_xwfb/s271/",
    ],
    "moe_renshi_si": [
        "https://www.moe.gov.cn/s78/A04/",
        "https://www.moe.gov.cn/s78/A04/tongzhi/",
    ],
    "baai_news": [
        "https://www.baai.ac.cn/",
        "https://hub.baai.ac.cn/",
    ],
    "tsinghua_air": [
        "https://air.tsinghua.edu.cn/",
        "https://air.tsinghua.edu.cn/xwgg.htm",
    ],
    "shlab_news": [
        "https://www.shlab.org.cn/",
        "https://www.shlab.org.cn/news",
    ],
    "zhejianglab_news": [
        "https://www.zhejianglab.com/",
        "https://www.zhejianglab.com/news",
    ],
    "pcl_news": [
        "https://www.pcl.ac.cn/",
        "https://www.pcl.ac.cn/html/941/",
        "https://www.pcl.ac.cn/html/896/",
    ],
    "ia_cas_news": [
        "http://www.ia.cas.cn/",
        "http://www.ia.cas.cn/xwzx/",
        "http://www.ia.cas.cn/xwzx/yw/",
    ],
    "ict_cas_news": [
        "https://www.ict.ac.cn/",
        "https://www.ict.ac.cn/xwgg/",
        "https://www.ict.ac.cn/xwgg/xw/",
    ],
    "cas_news": [
        "https://www.cas.cn/",
        "https://www.cas.cn/yw/",
    ],
    "cae_news": [
        "https://www.cae.cn/",
        "https://www.cae.cn/cae/html/main/col48/column_48_1.html",
    ],
    "nosta_news": [
        "https://www.nosta.gov.cn/",
    ],
    "jyb_news": [
        "https://www.jyb.cn/",
        "http://www.jyb.cn/",
    ],
}


async def investigate_source(source_id: str, urls: list[str]) -> dict:
    """Try multiple URLs for a source, find the best one with article links."""
    print(f"\n{'='*60}")
    print(f"Investigating: {source_id}")

    best = None
    for url in urls:
        html, err = await fetch(url)
        if err or html is None:
            print(f"  ❌ {url} -> {err}")
            continue

        if len(html) < 500:
            print(f"  ⚠️ {url} -> very short HTML ({len(html)} chars), likely JS or redirect")
            continue

        soup = BeautifulSoup(html, "lxml")
        title = soup.find("title")
        page_title = title.get_text(strip=True)[:40] if title else "N/A"

        lists = find_article_lists(soup, url)
        total_articles = sum(l["article_count"] for l in lists)

        print(f"  📄 {url}")
        print(f"     Title: {page_title}, HTML: {len(html)}, Article lists: {len(lists)}, Articles: {total_articles}")

        if lists:
            best_list = lists[0]
            print(f"     Best: {best_list['container']} > {best_list['item_tag']} ({best_list['article_count']} articles)")
            for s in best_list["samples"][:3]:
                print(f"       [{s['date']}] {s['title'][:50]}")
                print(f"         -> {s['href'][:70]}")

            if best is None or total_articles > best.get("total_articles", 0):
                best = {
                    "url": url,
                    "page_title": page_title,
                    "total_articles": total_articles,
                    "best_list": best_list,
                    "all_lists": lists,
                }

        await asyncio.sleep(0.3)

    if best:
        print(f"  ✅ BEST: {best['url']}")
        bl = best["best_list"]
        print(f"     Container: {bl['container']}")
        print(f"     Item tag: {bl['item_tag']}")
        return {"id": source_id, "status": "found", **best}
    else:
        print(f"  ❌ No article lists found on any URL. Likely needs Playwright/dynamic mode.")
        return {"id": source_id, "status": "needs_dynamic"}


async def main():
    results = []
    for source_id, urls in SOURCE_URLS.items():
        result = await investigate_source(source_id, urls)
        results.append(result)

    # Summary
    print(f"\n\n{'='*60}")
    print("INVESTIGATION SUMMARY")
    print(f"{'='*60}")

    found = [r for r in results if r["status"] == "found"]
    needs_dynamic = [r for r in results if r["status"] == "needs_dynamic"]

    print(f"\n✅ Found article lists ({len(found)}):")
    for r in found:
        bl = r["best_list"]
        print(f"  {r['id']}:")
        print(f"    url: {r['url']}")
        print(f"    container: {bl['container']} > {bl['item_tag']}")
        print(f"    articles: {bl['article_count']}")

    print(f"\n⚠️ Needs dynamic/Playwright ({len(needs_dynamic)}):")
    for r in needs_dynamic:
        print(f"  {r['id']}")


if __name__ == "__main__":
    asyncio.run(main())
