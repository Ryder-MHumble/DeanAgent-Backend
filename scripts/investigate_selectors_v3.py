#!/usr/bin/env python3
"""
Focused investigation on specific pages that need more analysis:
1. MOE A16 sub-pages (actual article lists)
2. ThePaper sidebar/channel pages
3. Shanghai sub-pages with news lists
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


def truncate(s, n=100):
    return s[:n] + "..." if len(s) > n else s


async def fetch(client, url):
    resp = await client.get(url, follow_redirects=True, timeout=30)
    return resp


async def moe_subpages(client):
    """Check MOE A16 sub-pages for actual article lists"""
    print("=" * 80)
    print("MOE A16 Sub-pages Investigation")
    print("=" * 80)

    # The main A16 page is a landing page. Try to find actual list pages
    sub_urls = [
        ("https://www.moe.gov.cn/s78/A16/tongzhi/", "通知"),
        ("https://www.moe.gov.cn/s78/A16/A16_sjhj/", "数据汇聚"),
        ("https://www.moe.gov.cn/s78/A16/A16_gggs/", "公告公示"),
        ("https://www.moe.gov.cn/s78/A16/moe_2798/", "科技动态"),
        ("https://www.moe.gov.cn/s78/A16/moe_2796/", "文件规定"),
    ]

    for url, name in sub_urls:
        try:
            resp = await fetch(client, url)
            print(f"\n--- {name}: {url} (HTTP {resp.status_code}) ---")
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.find('title')
            print(f"Title: {title.get_text(strip=True) if title else 'N/A'}")

            # Look for article lists
            for ul in soup.find_all('ul', class_=True):
                classes = ' '.join(ul.get('class', []))
                children = [c for c in ul.children if isinstance(c, Tag)]
                if len(children) >= 3 and children[0].name == 'li':
                    print(f"\n  <ul class='{classes}'> ({len(children)} li items)")
                    parent = ul.parent
                    if parent:
                        pclass = ' '.join(parent.get('class', []))
                        print(f"  Parent: <{parent.name} class='{pclass}'>")
                    for li in children[:3]:
                        a = li.find('a')
                        span = li.find('span')
                        if a:
                            text = a.get_text(strip=True)
                            href = urljoin(url, a.get('href', ''))
                            date = span.get_text(strip=True) if span else ''
                            print(f"    [{date}] {truncate(text, 60)} -> {href}")
                        # Show raw HTML
                        li_html = str(li)[:250]
                        print(f"    RAW: {li_html}")

        except Exception as e:
            print(f"  Error: {e}")


async def thepaper_channels(client):
    """Check ThePaper channel pages that might have cleaner list structures"""
    print("\n" + "=" * 80)
    print("ThePaper Channel Pages Investigation")
    print("=" * 80)

    # ThePaper has channel pages like /channel_25951 (education)
    channel_urls = [
        ("https://www.thepaper.cn/channel_25951", "教育家"),
        ("https://www.thepaper.cn/list_25769", "科技"),
    ]

    for url, name in channel_urls:
        try:
            resp = await fetch(client, url)
            print(f"\n--- {name}: {url} (HTTP {resp.status_code}) ---")
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find all newsDetail links
            news_links = soup.find_all('a', href=re.compile(r'newsDetail_forward'))
            print(f"  Found {len(news_links)} newsDetail links")

            # Check the structure around them
            for a in news_links[:5]:
                text = a.get_text(strip=True)
                href = a.get('href', '')
                a_class = ' '.join(a.get('class', []))

                # Walk up to find repeating container
                item = a
                for _ in range(5):
                    if item.parent:
                        item = item.parent
                        item_class = ' '.join(item.get('class', []))
                        siblings = item.parent.find_all(item.name, class_=item.get('class')) if item.parent else []
                        if len(siblings) >= 3:
                            print(f"\n  Repeating container: <{item.name} class='{truncate(item_class, 60)}'> ({len(siblings)} siblings)")
                            break

                if text:
                    print(f"  [{a_class}] {truncate(text, 60)}")

            # Also check for __NEXT_DATA__ or similar
            scripts = soup.find_all('script', id='__NEXT_DATA__')
            if scripts:
                print(f"\n  Found __NEXT_DATA__ (SSR data available)")
                data_text = scripts[0].get_text()[:500]
                print(f"  Preview: {data_text}")

        except Exception as e:
            print(f"  Error: {e}")


async def shanghai_news_page(client):
    """Check Shanghai education news sub-pages"""
    print("\n" + "=" * 80)
    print("Shanghai Education News Sub-pages")
    print("=" * 80)

    urls = [
        ("https://edu.sh.gov.cn/xwzx_bsxw/", "本市新闻"),
        ("https://edu.sh.gov.cn/xxgk2_zdgz_xxxsgz_01/", "信息公开"),
    ]

    for url, name in urls:
        try:
            resp = await fetch(client, url)
            print(f"\n--- {name}: {url} (HTTP {resp.status_code}) ---")
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.find('title')
            print(f"Title: {title.get_text(strip=True) if title else 'N/A'}")

            # Find article lists
            for ul in soup.find_all('ul', class_=True):
                classes = ' '.join(ul.get('class', []))
                children = [c for c in ul.children if isinstance(c, Tag)]
                if len(children) >= 3:
                    print(f"\n  <ul class='{classes}'> ({len(children)} li items)")
                    for li in children[:3]:
                        a = li.find('a')
                        span = li.find('span')
                        if a:
                            text = a.get_text(strip=True)
                            href = urljoin(url, a.get('href', ''))
                            date = span.get_text(strip=True) if span else ''
                            print(f"    [{date}] {truncate(text, 60)}")
                        li_html = str(li)[:200]
                        print(f"    RAW: {li_html}")

        except Exception as e:
            print(f"  Error: {e}")


async def zhejiang_news_list(client):
    """Check Zhejiang news list page (col/col1543973)"""
    print("\n" + "=" * 80)
    print("Zhejiang Education News List Pages")
    print("=" * 80)

    urls = [
        ("https://jyt.zj.gov.cn/col/col1543973/index.html", "教育动态"),
        ("https://jyt.zj.gov.cn/col/col1532970/index.html", "最新文件"),
    ]

    for url, name in urls:
        try:
            resp = await fetch(client, url)
            print(f"\n--- {name}: {url} (HTTP {resp.status_code}) ---")
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.find('title')
            print(f"Title: {title.get_text(strip=True) if title else 'N/A'}")

            # Check for list structures
            for ul in soup.find_all('ul'):
                children = [c for c in ul.children if isinstance(c, Tag)]
                if len(children) >= 5 and children[0].name == 'li':
                    parent = ul.parent
                    parent_class = ' '.join(parent.get('class', [])) if parent else ''
                    parent_id = parent.get('id', '') if parent else ''
                    ul_class = ' '.join(ul.get('class', []))
                    print(f"\n  <ul class='{ul_class}'> in <{parent.name if parent else '?'} class='{parent_class}' id='{parent_id}'> ({len(children)} items)")
                    for li in children[:3]:
                        a = li.find('a')
                        span = li.find('span')
                        if a:
                            text = a.get_text(strip=True)
                            href = urljoin(url, a.get('href', ''))
                            date = span.get_text(strip=True) if span else ''
                            print(f"    [{date}] {truncate(text, 60)}")
                        li_html = str(li)[:250]
                        print(f"    RAW: {li_html}")

        except Exception as e:
            print(f"  Error: {e}")


async def main():
    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        await moe_subpages(client)
        await asyncio.sleep(0.5)
        await thepaper_channels(client)
        await asyncio.sleep(0.5)
        await shanghai_news_page(client)
        await asyncio.sleep(0.5)
        await zhejiang_news_list(client)


if __name__ == "__main__":
    asyncio.run(main())
