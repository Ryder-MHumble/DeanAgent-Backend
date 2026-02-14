"""Batch analyze university source URLs to find correct CSS selectors.

Usage: python scripts/analyze_selectors.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from bs4 import BeautifulSoup


# Common list container patterns used on Chinese university/gov websites
LIST_PATTERNS = [
    # (container_selector, item_selector, title_selector, link_selector, date_selector)
    ("ul.wp_article_list", "li", "a", "a", "span.Article_PublishDate"),
    ("ul.wp_article_list", "li", "a", "a", "span"),
    ("ul.news_list", "li", "a", "a", "span"),
    ("ul.news-list", "li", "a", "a", "span"),
    ("ul.qhrw2_ul", "li", "p.bt", "a", "div.sj"),
    ("div.list_item", "div", "a", "a", "span.date"),
    ("div.news-list", "div.item", "a", "a", "span.date"),
    ("div.news-list", "div.news-item", "a", "a", "span"),
    ("ul.list", "li", "a", "a", "span"),
    ("ul.listTxt", "li", "a", "a", "span"),
    ("ul.u-list", "li", "a", "a", "span"),
    ("div.list", "li", "a", "a", "span"),
    ("div.list-box", "li", "a", "a", "span"),
    ("div.cont_list", "li", "a", "a", "span"),
    ("div.article-list", "div", "a", "a", "span"),
    ("div.listCon", "li", "a", "a", "span"),
]


async def fetch_html(url: str, timeout: float = 15.0) -> str | None:
    """Fetch a URL and return HTML."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, verify=False
        ) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        return f"ERROR: {e}"


def analyze_page(html: str, url: str) -> dict:
    """Analyze a page's HTML to find the best news list selectors."""
    soup = BeautifulSoup(html, "lxml")
    results = {}

    # Try each pattern
    for container_sel, item_sel, title_sel, link_sel, date_sel in LIST_PATTERNS:
        container = soup.select_one(container_sel)
        if not container:
            continue
        items = container.select(f":scope > {item_sel}")
        if len(items) < 2:
            continue

        # Check if items have titles and links
        valid = 0
        samples = []
        for item in items[:5]:
            title_el = item.select_one(title_sel)
            link_el = item.select_one(link_sel)
            if title_el and link_el:
                title = title_el.get_text(strip=True)
                href = link_el.get("href", "")
                date_el = item.select_one(date_sel) if date_sel else None
                date_text = date_el.get_text(separator=" ").strip() if date_el else ""
                if title and href:
                    valid += 1
                    samples.append({
                        "title": title[:60],
                        "href": href[:80],
                        "date": date_text[:30],
                    })

        if valid >= 2:
            results[f"{container_sel} > {item_sel}"] = {
                "total_items": len(items),
                "valid_items": valid,
                "title_sel": title_sel,
                "link_sel": link_sel,
                "date_sel": date_sel,
                "samples": samples,
            }

    # Fallback: try to find any UL with LI items containing links
    if not results:
        for ul in soup.find_all("ul"):
            ul_class = " ".join(ul.get("class", []))
            parent_class = " ".join(ul.parent.get("class", [])) if ul.parent else ""
            lis = ul.find_all("li", recursive=False)
            if len(lis) < 3:
                continue

            valid = 0
            samples = []
            for li in lis[:5]:
                a = li.find("a")
                if a and a.get_text(strip=True) and a.get("href"):
                    valid += 1
                    # Try to find a date element
                    date_text = ""
                    for span in li.find_all(["span", "em", "time", "div"]):
                        text = span.get_text(strip=True)
                        if any(c.isdigit() for c in text) and len(text) < 20:
                            date_text = text
                            break
                    samples.append({
                        "title": a.get_text(strip=True)[:60],
                        "href": a.get("href", "")[:80],
                        "date": date_text[:30],
                    })

            if valid >= 3:
                key = f"ul.{ul_class or '(no-class)'} [parent: {parent_class}]"
                results[key] = {
                    "total_items": len(lis),
                    "valid_items": valid,
                    "title_sel": "a",
                    "link_sel": "a",
                    "date_sel": "(auto-detected)",
                    "samples": samples,
                }

    # Also try DIV-based lists
    if not results:
        for div in soup.find_all("div"):
            div_class = " ".join(div.get("class", []))
            if not div_class:
                continue
            children = div.find_all(recursive=False)
            if len(children) < 3:
                continue
            # Check if children are uniform (same tag)
            tags = [c.name for c in children]
            if len(set(tags)) > 2:
                continue

            valid = 0
            samples = []
            for child in children[:5]:
                a = child.find("a")
                if a and a.get_text(strip=True) and a.get("href"):
                    valid += 1
                    samples.append({
                        "title": a.get_text(strip=True)[:60],
                        "href": a.get("href", "")[:80],
                    })

            if valid >= 3:
                results[f"div.{div_class} > {tags[0]}"] = {
                    "total_items": len(children),
                    "valid_items": valid,
                    "title_sel": "a",
                    "link_sel": "a",
                    "date_sel": "?",
                    "samples": samples,
                }

    return results


async def analyze_source(source: dict) -> dict:
    """Analyze a single source."""
    source_id = source["id"]
    url = source["url"]
    enabled = source.get("is_enabled", True)

    print(f"\n{'='*60}")
    print(f"Source: {source_id} ({'ENABLED' if enabled else 'DISABLED'})")
    print(f"URL: {url}")

    html = await fetch_html(url)
    if html is None or html.startswith("ERROR:"):
        print(f"  FETCH FAILED: {html}")
        return {"id": source_id, "status": "fetch_failed", "error": html}

    print(f"  HTML length: {len(html)}")

    # Check if current selectors work
    current_selectors = source.get("selectors", {})
    soup = BeautifulSoup(html, "lxml")
    current_list_sel = current_selectors.get("list_item", "")
    current_items = soup.select(current_list_sel) if current_list_sel else []
    print(f"  Current selector '{current_list_sel}': {len(current_items)} items")

    if current_items:
        valid = 0
        for item in current_items[:5]:
            title_sel = current_selectors.get("title", "a")
            title_el = item.select_one(title_sel)
            if title_el and title_el.get_text(strip=True):
                valid += 1
        print(f"  Current selector valid items (of first 5): {valid}")
        if valid >= 2:
            print(f"  ✅ Current selectors WORK!")
            # Show samples
            for item in current_items[:3]:
                title_el = item.select_one(current_selectors.get("title", "a"))
                title = title_el.get_text(strip=True)[:50] if title_el else "?"
                print(f"    - {title}")
            return {"id": source_id, "status": "working", "items": len(current_items)}

    # Analyze for better selectors
    print(f"  ❌ Current selectors don't work. Analyzing...")
    analysis = analyze_page(html, url)

    if analysis:
        best_key = max(analysis, key=lambda k: analysis[k]["valid_items"])
        best = analysis[best_key]
        print(f"  📋 Best match: {best_key}")
        print(f"     Items: {best['total_items']}, Valid: {best['valid_items']}")
        for s in best["samples"][:3]:
            print(f"     - [{s.get('date', '')}] {s['title']}")
            print(f"       href: {s['href']}")
        return {
            "id": source_id,
            "status": "needs_fix",
            "best_selector": best_key,
            "analysis": best,
            "all_matches": {k: v["valid_items"] for k, v in analysis.items()},
        }
    else:
        print(f"  ⚠️ No suitable list found. Page may use JS rendering or non-standard layout.")
        # Show page title for debugging
        title = soup.find("title")
        print(f"  Page title: {title.get_text(strip=True) if title else 'N/A'}")
        return {"id": source_id, "status": "no_list_found"}


async def main():
    import yaml

    sources_file = Path(__file__).resolve().parent.parent / "sources" / "universities.yaml"
    with open(sources_file) as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    print(f"Analyzing {len(sources)} university sources...\n")

    results = []
    for source in sources:
        result = await analyze_source(source)
        results.append(result)
        await asyncio.sleep(0.5)  # Be polite

    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    working = [r for r in results if r["status"] == "working"]
    needs_fix = [r for r in results if r["status"] == "needs_fix"]
    fetch_failed = [r for r in results if r["status"] == "fetch_failed"]
    no_list = [r for r in results if r["status"] == "no_list_found"]

    print(f"✅ Working: {len(working)}")
    for r in working:
        print(f"   - {r['id']} ({r.get('items', 0)} items)")

    print(f"\n🔧 Needs selector fix: {len(needs_fix)}")
    for r in needs_fix:
        print(f"   - {r['id']}: {r['best_selector']}")

    print(f"\n❌ Fetch failed: {len(fetch_failed)}")
    for r in fetch_failed:
        print(f"   - {r['id']}: {r.get('error', '')[:60]}")

    print(f"\n⚠️ No list found (may need JS/dynamic): {len(no_list)}")
    for r in no_list:
        print(f"   - {r['id']}")


if __name__ == "__main__":
    asyncio.run(main())
