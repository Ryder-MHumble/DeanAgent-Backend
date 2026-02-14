#!/usr/bin/env python3
"""
Deep investigation of HTML structure for each URL.
Dumps specific HTML sections to understand exact selector paths.
"""

import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def truncate(s, n=120):
    return s[:n] + "..." if len(s) > n else s


async def fetch(client, url):
    resp = await client.get(url, follow_redirects=True, timeout=30)
    return resp


async def investigate_moe(client):
    """教育部科技司 - need to find actual news list, not sidebar navigation"""
    print("\n" + "=" * 80)
    print("1. 教育部科技司 https://www.moe.gov.cn/s78/A16/")
    print("=" * 80)

    resp = await fetch(client, "https://www.moe.gov.cn/s78/A16/")
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Look for the actual article lists - MOE uses specific class patterns
    # Check for <ul class="siju-list"> or similar
    for ul in soup.find_all('ul', class_=True):
        classes = ' '.join(ul.get('class', []))
        children = [c for c in ul.children if isinstance(c, Tag)]
        if len(children) >= 3:
            print(f"\n<ul class='{classes}'> ({len(children)} items)")
            for li in children[:3]:
                a = li.find('a')
                if a:
                    href = a.get('href', '')
                    text = a.get_text(strip=True)
                    date_span = li.find('span')
                    date_text = date_span.get_text(strip=True) if date_span else ''
                    print(f"  - [{date_text}] {text[:70]} -> {href}")

    # Also check for specific MOE content divs
    for div in soup.find_all('div', class_=re.compile(r'moe-main|lanmu|module|neirong', re.I)):
        classes = ' '.join(div.get('class', []))
        children_tags = [c.name for c in div.children if isinstance(c, Tag)]
        print(f"\n<div class='{classes}'> children: {children_tags[:8]}")

    # Look at the page for sub-page links (A16 might be a landing page)
    # Check for links to actual list pages
    print("\nLinks to list pages:")
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = a.get_text(strip=True)
        if any(x in href for x in ['A16_sjhj', 'A16_kyjd', 'A16_zcwj', 'moe_list', 'jst']):
            print(f"  {text} -> {urljoin('https://www.moe.gov.cn/s78/A16/', href)}")

    # Try a sub-page that might have actual news
    sub_urls = [
        "https://www.moe.gov.cn/s78/A16/A16_sjhj/",
        "https://www.moe.gov.cn/s78/A16/A16_gggs/",
    ]
    for sub_url in sub_urls:
        try:
            resp2 = await fetch(client, sub_url)
            if resp2.status_code == 200:
                soup2 = BeautifulSoup(resp2.text, 'html.parser')
                print(f"\nSub-page: {sub_url} (status {resp2.status_code})")
                for ul in soup2.find_all('ul', class_=True):
                    children = [c for c in ul.children if isinstance(c, Tag)]
                    if len(children) >= 3:
                        classes = ' '.join(ul.get('class', []))
                        print(f"  <ul class='{classes}'> ({len(children)} items)")
                        for li in children[:3]:
                            a = li.find('a')
                            if a:
                                text = a.get_text(strip=True)
                                href = urljoin(sub_url, a.get('href', ''))
                                span = li.find('span')
                                date = span.get_text(strip=True) if span else ''
                                print(f"    [{date}] {truncate(text, 60)} -> {href}")
        except Exception as e:
            print(f"  Error: {e}")


async def investigate_beijing(client):
    """北京市教委"""
    print("\n" + "=" * 80)
    print("2. 北京市教委 https://jw.beijing.gov.cn/xxgk/")
    print("=" * 80)

    resp = await fetch(client, "https://jw.beijing.gov.cn/xxgk/")
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Find the main news lists
    for ul in soup.find_all('ul', class_=re.compile(r'list|mylist', re.I)):
        classes = ' '.join(ul.get('class', []))
        children = [c for c in ul.children if isinstance(c, Tag)]
        if len(children) >= 2:
            print(f"\n<ul class='{classes}'> ({len(children)} items)")
            # Show parent context
            parent = ul.parent
            if parent:
                parent_sel = f"<{parent.name} class='{' '.join(parent.get('class', []))}'>"
                print(f"  Parent: {parent_sel}")

            for li in children[:3]:
                a = li.find('a')
                em = li.find('em')
                span = li.find('span')
                if a:
                    text = a.get_text(strip=True)
                    href = urljoin("https://jw.beijing.gov.cn/xxgk/", a.get('href', ''))
                    date = ''
                    if em:
                        date = em.get_text(strip=True)
                    elif span:
                        date = span.get_text(strip=True)
                    print(f"    [{date}] {truncate(text, 60)} -> {href}")
                # Show raw LI HTML (abbreviated)
                li_html = str(li)[:200]
                print(f"    HTML: {li_html}")


async def investigate_shanghai(client):
    """上海市教委"""
    print("\n" + "=" * 80)
    print("3. 上海市教委 https://edu.sh.gov.cn/")
    print("=" * 80)

    resp = await fetch(client, "https://edu.sh.gov.cn/")
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Look at the news list sections
    for ul in soup.find_all('ul', class_=re.compile(r'list-cell', re.I)):
        classes = ' '.join(ul.get('class', []))
        children = [c for c in ul.children if isinstance(c, Tag)]
        if children:
            print(f"\n<ul class='{classes}'> ({len(children)} items)")
            parent = ul.parent
            if parent:
                pclass = ' '.join(parent.get('class', []))
                print(f"  Parent: <{parent.name} class='{pclass}'>")

            for li in children[:3]:
                a = li.find('a')
                span = li.find('span')
                if a:
                    text = a.get_text(strip=True)
                    href = urljoin("https://edu.sh.gov.cn/", a.get('href', ''))
                    date = span.get_text(strip=True) if span else ''
                    print(f"    [{date}] {truncate(text, 60)} -> {href}")
                li_html = str(li)[:250]
                print(f"    HTML: {li_html}")

    # Check for specific news section divs
    for div in soup.find_all('div', class_=re.compile(r'hp-news|gsgg', re.I)):
        classes = ' '.join(div.get('class', []))
        print(f"\n<div class='{classes}'>")
        for a in div.find_all('a', href=True)[:5]:
            text = a.get_text(strip=True)
            href = urljoin("https://edu.sh.gov.cn/", a.get('href', ''))
            if text and len(text) > 4:
                print(f"    {truncate(text, 70)} -> {href}")


async def investigate_zhejiang(client):
    """浙江省教育厅"""
    print("\n" + "=" * 80)
    print("4. 浙江省教育厅 https://jyt.zj.gov.cn/")
    print("=" * 80)

    resp = await fetch(client, "https://jyt.zj.gov.cn/")
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Check Education2-news sections
    for div in soup.find_all('div', class_=re.compile(r'Education2-news|content-list|listPublic', re.I)):
        classes = ' '.join(div.get('class', []))
        print(f"\n<div class='{classes}'>")
        for a in div.find_all('a', href=True)[:5]:
            text = a.get_text(strip=True)
            href = urljoin("https://jyt.zj.gov.cn/", a.get('href', ''))
            if text:
                print(f"    {truncate(text, 70)} -> {href}")

    # Check for <ul> with items
    for ul in soup.find_all('ul'):
        parent = ul.parent
        if parent and parent.get('id') and 'list' in parent.get('id', '').lower():
            parent_id = parent.get('id')
            children = [c for c in ul.children if isinstance(c, Tag)]
            if children:
                print(f"\nUL inside #{parent_id} ({len(children)} items)")
                for li in children[:3]:
                    a = li.find('a')
                    span = li.find('span')
                    if a:
                        text = a.get_text(strip=True)
                        href = urljoin("https://jyt.zj.gov.cn/", a.get('href', ''))
                        date = span.get_text(strip=True) if span else ''
                        print(f"    [{date}] {truncate(text, 60)} -> {href}")
                    li_html = str(li)[:250]
                    print(f"    HTML: {li_html}")


async def investigate_jiangsu(client):
    """江苏省教育厅"""
    print("\n" + "=" * 80)
    print("5. 江苏省教育厅 https://jyt.jiangsu.gov.cn/")
    print("=" * 80)

    resp = await fetch(client, "https://jyt.jiangsu.gov.cn/")
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Check for news lists
    for ul in soup.find_all('ul', class_=re.compile(r'list', re.I)):
        classes = ' '.join(ul.get('class', []))
        children = [c for c in ul.children if isinstance(c, Tag)]
        if len(children) >= 3:
            print(f"\n<ul class='{classes}'> ({len(children)} items)")
            parent = ul.parent
            if parent:
                pclass = ' '.join(parent.get('class', []))
                print(f"  Parent: <{parent.name} class='{pclass}'>")

            for li in children[:3]:
                a = li.find('a')
                span = li.find('span')
                if a:
                    text = a.get_text(strip=True)
                    href = urljoin("https://jyt.jiangsu.gov.cn/", a.get('href', ''))
                    date = span.get_text(strip=True) if span else ''
                    print(f"    [{date}] {truncate(text, 60)} -> {href}")
                li_html = str(li)[:300]
                print(f"    HTML: {li_html}")

    # Check the news div
    for div in soup.find_all('div', class_=re.compile(r'news|listL', re.I)):
        classes = ' '.join(div.get('class', []))
        print(f"\n<div class='{classes}'>")
        for a in div.find_all('a', href=True)[:5]:
            text = a.get_text(strip=True)
            if text and len(text) > 4:
                href = urljoin("https://jyt.jiangsu.gov.cn/", a.get('href', ''))
                print(f"    {truncate(text, 70)} -> {href}")


async def investigate_guangdong(client):
    """广东省教育厅"""
    print("\n" + "=" * 80)
    print("6. 广东省教育厅 https://edu.gd.gov.cn/")
    print("=" * 80)

    resp = await fetch(client, "https://edu.gd.gov.cn/")
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Check for main news/list sections
    for ul in soup.find_all('ul', class_=re.compile(r'list', re.I)):
        classes = ' '.join(ul.get('class', []))
        children = [c for c in ul.children if isinstance(c, Tag)]
        if len(children) >= 3:
            print(f"\n<ul class='{classes}'> ({len(children)} items)")
            parent = ul.parent
            if parent:
                pclass = ' '.join(parent.get('class', []))
                pid = parent.get('id', '')
                print(f"  Parent: <{parent.name} class='{pclass}' id='{pid}'>")

            for li in children[:3]:
                a = li.find('a')
                span = li.find('span')
                if a:
                    text = a.get_text(strip=True)
                    href = urljoin("https://edu.gd.gov.cn/", a.get('href', ''))
                    date = span.get_text(strip=True) if span else ''
                    print(f"    [{date}] {truncate(text, 60)} -> {href}")
                li_html = str(li)[:300]
                print(f"    HTML: {li_html}")

    # Check section / gsgg divs
    for div in soup.find_all('div', class_=re.compile(r'gsgg|zwgk|section|newsList', re.I)):
        classes = ' '.join(div.get('class', []))
        children = [c for c in div.children if isinstance(c, Tag)]
        if len(children) >= 2:
            print(f"\n<div class='{classes}'> ({len(children)} children)")
            for a in div.find_all('a', href=True)[:3]:
                text = a.get_text(strip=True)
                if text and len(text) > 4:
                    href = urljoin("https://edu.gd.gov.cn/", a.get('href', ''))
                    print(f"    {truncate(text, 70)} -> {href}")


async def investigate_cingta(client):
    """青塔 - likely SPA, check page structure"""
    print("\n" + "=" * 80)
    print("7. 青塔 https://www.cingta.com/")
    print("=" * 80)

    resp = await fetch(client, "https://www.cingta.com/")
    soup = BeautifulSoup(resp.text, 'html.parser')

    body = soup.find('body')
    body_text = body.get_text(strip=True) if body else ''
    print(f"Body text length: {len(body_text)}")
    print(f"Body text (first 500): {body_text[:500]}")

    # Check for script tags that might reveal API endpoints
    scripts = soup.find_all('script', src=True)
    print(f"\nScript sources ({len(scripts)}):")
    for s in scripts[:10]:
        print(f"  {s.get('src', '')}")

    # Check for meta tags / data
    for meta in soup.find_all('meta'):
        name = meta.get('name', '') or meta.get('property', '')
        content = meta.get('content', '')
        if name and content:
            print(f"  meta[{name}] = {truncate(content, 60)}")

    # Try their news/article page
    alt_urls = [
        "https://www.cingta.com/detail/",
        "https://www.cingta.com/news",
        "https://www.cingta.com/article",
    ]
    for alt_url in alt_urls:
        try:
            resp2 = await fetch(client, alt_url)
            print(f"\n{alt_url}: HTTP {resp2.status_code}")
            if resp2.status_code == 200:
                soup2 = BeautifulSoup(resp2.text, 'html.parser')
                t = soup2.find('title')
                print(f"  Title: {t.get_text(strip=True) if t else 'N/A'}")
                body2 = soup2.find('body')
                text2 = body2.get_text(strip=True) if body2 else ''
                print(f"  Body text length: {len(text2)}")
        except Exception as e:
            print(f"  Error: {e}")


async def investigate_thepaper(client):
    """澎湃新闻"""
    print("\n" + "=" * 80)
    print("8. 澎湃新闻 https://www.thepaper.cn/")
    print("=" * 80)

    resp = await fetch(client, "https://www.thepaper.cn/")
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Look at the main content structure
    # ThePaper uses React/Next.js with hashed class names
    # Let's find card/article containers
    print("Looking for card/article containers...")

    for div in soup.find_all('div', class_=re.compile(r'card|article|news', re.I)):
        classes = ' '.join(div.get('class', []))
        links = div.find_all('a', href=True)
        article_links = [a for a in links if 'newsDetail' in a.get('href', '')]
        if article_links:
            print(f"\n<div class='{truncate(classes, 80)}'> ({len(article_links)} article links)")
            for a in article_links[:2]:
                text = a.get_text(strip=True)
                href = urljoin("https://www.thepaper.cn/", a.get('href', ''))
                print(f"    {truncate(text, 70)} -> {href}")
            # Show inner structure
            first_link = article_links[0]
            parent_html = str(first_link.parent)[:300]
            print(f"    Parent HTML: {parent_html}")

    # Also check for h2/h3 with links
    print("\nArticle links from h2/h3:")
    for heading in soup.find_all(['h2', 'h3']):
        a = heading.find('a', href=True)
        if a and 'newsDetail' in a.get('href', ''):
            href = urljoin("https://www.thepaper.cn/", a.get('href', ''))
            text = a.get_text(strip=True)
            heading_class = ' '.join(heading.get('class', []))
            print(f"  <{heading.name} class='{heading_class}'> {truncate(text, 60)} -> {href}")

    # Check for the list container
    print("\nAll newsDetail links with parent context:")
    news_links = soup.find_all('a', href=re.compile(r'newsDetail_forward'))
    for a in news_links[:8]:
        text = a.get_text(strip=True)
        href = a.get('href', '')
        a_class = ' '.join(a.get('class', []))
        parent = a.parent
        parent_class = ' '.join(parent.get('class', [])) if parent else ''
        grandparent = parent.parent if parent else None
        gp_class = ' '.join(grandparent.get('class', [])) if grandparent else ''
        if text:
            print(f"  [{a_class}] {truncate(text, 50)}")
            print(f"    parent: <{parent.name if parent else '?'} class='{parent_class}'>")
            print(f"    grandparent: <{grandparent.name if grandparent else '?'} class='{gp_class}'>")


async def main():
    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        await investigate_moe(client)
        await asyncio.sleep(0.5)
        await investigate_beijing(client)
        await asyncio.sleep(0.5)
        await investigate_shanghai(client)
        await asyncio.sleep(0.5)
        await investigate_zhejiang(client)
        await asyncio.sleep(0.5)
        await investigate_jiangsu(client)
        await asyncio.sleep(0.5)
        await investigate_guangdong(client)
        await asyncio.sleep(0.5)
        await investigate_cingta(client)
        await asyncio.sleep(0.5)
        await investigate_thepaper(client)


if __name__ == "__main__":
    asyncio.run(main())
