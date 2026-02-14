#!/usr/bin/env python3
"""
Investigate URLs to determine CSS selectors for article list scraping.
For each URL: fetch HTML, parse structure, identify selectors for list_item/title/link/date.
"""

import asyncio
import re
import sys
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

URLS = [
    ("https://www.moe.gov.cn/s78/A16/", "教育部科技司"),
    ("https://jw.beijing.gov.cn/xxgk/", "北京市教委"),
    ("https://edu.sh.gov.cn/", "上海市教委"),
    ("https://jyt.zj.gov.cn/", "浙江省教育厅"),
    ("https://jyt.jiangsu.gov.cn/", "江苏省教育厅"),
    ("https://edu.gd.gov.cn/", "广东省教育厅"),
    ("https://www.cingta.com/", "青塔"),
    ("https://www.thepaper.cn/", "澎湃新闻"),
]

# Patterns that suggest article/content links
ARTICLE_PATTERNS = [
    r'/\d{4}[\-/]\d{2}',       # /2026/01 or /2026-01
    r'/\d{8}/',                 # /20260101/
    r'/info/',
    r'/article/',
    r'/detail/',
    r'/content/',
    r'/jyxw/',                  # 教育新闻
    r'/tzgg/',                  # 通知公告
    r'/gkml/',                  # 公开目录
    r'/xxgk/',                  # 信息公开
    r'/news',
    r'/srcsite/',
    r'/s\d+/',                  # MOE style paths like /s78/
    r't\d+_\d+',               # gov.cn style like t20260101_123456
    r'/\w+/\d{6,}',            # path/id patterns
]


def is_article_link(href: str) -> bool:
    """Check if href looks like an article/content link."""
    if not href:
        return False
    # Exclude anchors, javascript, images, downloads
    if href.startswith(('#', 'javascript:', 'mailto:')):
        return False
    if re.search(r'\.(jpg|png|gif|pdf|doc|xls|zip|rar)$', href, re.I):
        return False
    for pattern in ARTICLE_PATTERNS:
        if re.search(pattern, href):
            return True
    return False


def get_element_selector(element: Tag) -> str:
    """Generate a CSS-like description of an element."""
    tag = element.name
    classes = element.get('class', [])
    eid = element.get('id', '')
    if eid:
        return f"{tag}#{eid}"
    if classes:
        return f"{tag}.{'.'.join(classes)}"
    return tag


def find_date_near_link(item: Tag) -> tuple[str | None, str | None, str | None]:
    """Try to find a date string near an article link element."""
    text = item.get_text(separator=' ', strip=True)

    # Common date patterns
    date_patterns = [
        (r'(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})', '%Y-%m-%d'),
        (r'(\d{4}年\d{1,2}月\d{1,2}日)', '%Y年%m月%d日'),
        (r'(\d{4}\.\d{2}\.\d{2})', '%Y.%m.%d'),
        (r'(\d{2}-\d{2})', None),  # MM-DD, incomplete
    ]

    for pattern, fmt in date_patterns:
        m = re.search(pattern, text)
        if m:
            # Try to find the element containing this date
            date_str = m.group(1)
            # Search for the element
            for child in item.descendants:
                if isinstance(child, Tag) and date_str in child.get_text(strip=True):
                    # Find the most specific element
                    if not any(isinstance(c, Tag) and date_str in c.get_text(strip=True)
                             for c in child.children if isinstance(c, Tag)):
                        selector = get_element_selector(child)
                        return date_str, selector, fmt
            return date_str, "text-extraction", fmt

    return None, None, None


def analyze_list_structure(soup: BeautifulSoup, base_url: str) -> dict:
    """Analyze the page to find article list structures."""
    results = {
        "article_links": [],
        "list_structures": [],
        "recommended": None,
    }

    # Step 1: Find all links that look like articles
    all_links = soup.find_all('a', href=True)
    article_links = []

    for a in all_links:
        href = a.get('href', '')
        abs_href = urljoin(base_url, href)
        title_text = a.get_text(strip=True)

        if is_article_link(abs_href) and title_text and len(title_text) > 4:
            article_links.append({
                'element': a,
                'href': abs_href,
                'title': title_text[:80],
                'parent': a.parent,
            })

    results["article_links"] = article_links

    if not article_links:
        return results

    # Step 2: Find common parent containers (list structures)
    # Group links by their parent/grandparent structure
    parent_groups = {}
    for link_info in article_links:
        a = link_info['element']
        # Try parent, grandparent, great-grandparent as potential list items
        for depth in range(1, 5):
            ancestor = a
            for _ in range(depth):
                if ancestor.parent:
                    ancestor = ancestor.parent
                else:
                    break

            key = (id(ancestor.parent) if ancestor.parent else 0, get_element_selector(ancestor))
            if key not in parent_groups:
                parent_groups[key] = {
                    'container_parent': ancestor.parent,
                    'item_element': ancestor,
                    'item_selector': get_element_selector(ancestor),
                    'links': [],
                    'depth': depth,
                }
            parent_groups[key]['links'].append(link_info)

    # Step 3: Score and rank list structures
    for key, group in parent_groups.items():
        n_links = len(group['links'])
        if n_links < 3:
            continue

        item = group['item_element']
        container = group['container_parent']

        # Check if siblings have similar structure
        if container:
            similar_siblings = container.find_all(item.name, class_=item.get('class'))
            group['sibling_count'] = len(similar_siblings)
        else:
            group['sibling_count'] = n_links

        # Look for date in first item
        date_str, date_sel, date_fmt = find_date_near_link(item)
        group['date_example'] = date_str
        group['date_selector'] = date_sel
        group['date_format'] = date_fmt

        container_selector = get_element_selector(container) if container else "body"

        group['score'] = n_links * 10 + group['sibling_count'] * 5
        group['container_selector'] = container_selector

        results['list_structures'].append(group)

    # Sort by score
    results['list_structures'].sort(key=lambda x: x.get('score', 0), reverse=True)

    # Pick the best structure
    if results['list_structures']:
        best = results['list_structures'][0]
        results['recommended'] = best

    return results


async def investigate_url(client: httpx.AsyncClient, url: str, name: str) -> dict:
    """Investigate a single URL and return analysis results."""
    result = {
        "url": url,
        "name": name,
        "status": None,
        "page_title": None,
        "needs_dynamic": False,
        "selectors": None,
        "samples": [],
        "error": None,
        "notes": [],
    }

    try:
        resp = await client.get(url, follow_redirects=True, timeout=30)
        result["status"] = resp.status_code

        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        # Detect encoding
        content_type = resp.headers.get('content-type', '')
        html = resp.text

        # Check if page is mostly JS-rendered
        soup = BeautifulSoup(html, 'html.parser')

        title_tag = soup.find('title')
        result["page_title"] = title_tag.get_text(strip=True) if title_tag else "No title"

        # Check for JS-heavy indicators
        body = soup.find('body')
        if body:
            body_text = body.get_text(strip=True)
            script_tags = soup.find_all('script')

            # If body has very little text but many scripts, likely JS-rendered
            if len(body_text) < 200 and len(script_tags) > 5:
                result["needs_dynamic"] = True
                result["notes"].append("Page appears to be JavaScript-rendered (minimal body text)")

            # Check for common SPA indicators
            if soup.find('div', id='app') or soup.find('div', id='root'):
                noscript = soup.find('noscript')
                if noscript and '浏览器' in (noscript.get_text() or ''):
                    result["needs_dynamic"] = True
                    result["notes"].append("SPA detected (div#app/root with noscript warning)")

        # Analyze list structure
        analysis = analyze_list_structure(soup, url)

        if not analysis["article_links"]:
            result["notes"].append(f"No article-like links found with standard patterns. Total links: {len(soup.find_all('a', href=True))}")
            # Try broader search
            all_links = soup.find_all('a', href=True)
            sample_hrefs = []
            for a in all_links[:50]:
                href = a.get('href', '')
                text = a.get_text(strip=True)
                if text and len(text) > 4:
                    abs_href = urljoin(url, href)
                    sample_hrefs.append(f"  {text[:60]} -> {abs_href}")
            if sample_hrefs:
                result["notes"].append("Sample links found:\n" + "\n".join(sample_hrefs[:15]))

            if not result["needs_dynamic"]:
                result["needs_dynamic"] = True
                result["notes"].append("May need dynamic rendering to load content")
            return result

        result["notes"].append(f"Found {len(analysis['article_links'])} article-like links")

        if analysis["recommended"]:
            best = analysis["recommended"]

            # Determine relative selectors
            item_sel = best['item_selector']
            container_sel = best['container_selector']

            # For title/link, examine the structure of one item
            sample_item = best['item_element']

            # Find the <a> tag within the item
            first_link = None
            for link_info in best['links'][:1]:
                first_link = link_info['element']

            title_sel = "a"  # default
            link_sel = "a"   # default

            if first_link:
                # Check if title is inside a specific element
                link_parent = first_link.parent
                if link_parent and link_parent != sample_item:
                    if link_parent.name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'span', 'dt', 'dd'):
                        parent_sel = get_element_selector(link_parent)
                        title_sel = f"{parent_sel} > a" if parent_sel != item_sel else "a"
                        link_sel = title_sel

            result["selectors"] = {
                "list_item": f"{container_sel} > {item_sel}" if container_sel != "body" else item_sel,
                "title": title_sel,
                "link": link_sel,
                "date": best.get('date_selector'),
                "date_format": best.get('date_format'),
                "date_example": best.get('date_example'),
            }

            # Collect samples
            for link_info in best['links'][:5]:
                result["samples"].append({
                    "title": link_info['title'],
                    "url": link_info['href'],
                })

        # Additional: dump raw HTML structure hints
        # Find <ul>, <ol>, <div> with class containing 'list'
        list_containers = soup.find_all(['ul', 'ol', 'div', 'table'],
                                         class_=re.compile(r'list|news|article|notice|item|content', re.I))
        if list_containers:
            container_hints = [get_element_selector(c) for c in list_containers[:10]]
            result["notes"].append(f"List-like containers found: {', '.join(container_hints)}")

    except httpx.TimeoutException:
        result["error"] = "Timeout (30s)"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


async def investigate_url_detailed(client: httpx.AsyncClient, url: str, name: str) -> dict:
    """More detailed investigation - dump key HTML sections."""
    result = await investigate_url(client, url, name)

    # If we got the page, also dump some structural info
    if result["status"] == 200 and not result["error"]:
        try:
            resp = await client.get(url, follow_redirects=True, timeout=30)
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find elements with IDs or classes that suggest content areas
            content_hints = []
            for tag in soup.find_all(True, class_=True):
                classes = ' '.join(tag.get('class', []))
                if re.search(r'list|news|article|notice|content|main|center|body', classes, re.I):
                    children_count = len([c for c in tag.children if isinstance(c, Tag)])
                    if children_count >= 3:
                        selector = get_element_selector(tag)
                        child_tags = [c.name for c in tag.children if isinstance(c, Tag)][:5]
                        content_hints.append(f"  {selector} ({children_count} children: {child_tags})")

            if content_hints:
                result["notes"].append("Content area candidates:\n" + "\n".join(content_hints[:10]))

            # Check for iframes (some gov sites use iframes)
            iframes = soup.find_all('iframe')
            if iframes:
                iframe_srcs = [f.get('src', 'no-src') for f in iframes]
                result["notes"].append(f"Iframes found: {iframe_srcs}")

        except Exception:
            pass

    return result


async def main():
    print("=" * 100)
    print("URL SELECTOR INVESTIGATION")
    print("=" * 100)

    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        # Process URLs sequentially to be polite
        for url, name in URLS:
            print(f"\n{'='*100}")
            print(f"INVESTIGATING: {name} ({url})")
            print(f"{'='*100}")

            result = await investigate_url_detailed(client, url, name)

            print(f"\nStatus: {result['status']}")
            print(f"Page Title: {result['page_title']}")
            print(f"Needs Dynamic Rendering: {result['needs_dynamic']}")

            if result['error']:
                print(f"ERROR: {result['error']}")

            if result['selectors']:
                print(f"\nRecommended Selectors:")
                for key, val in result['selectors'].items():
                    print(f"  {key}: {val}")

            if result['samples']:
                print(f"\nSample Articles ({len(result['samples'])}):")
                for i, s in enumerate(result['samples'][:3], 1):
                    print(f"  {i}. {s['title']}")
                    print(f"     {s['url']}")

            if result['notes']:
                print(f"\nNotes:")
                for note in result['notes']:
                    print(f"  - {note}")

            print()

            # Small delay between requests
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
