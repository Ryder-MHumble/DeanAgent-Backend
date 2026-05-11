#!/usr/bin/env python3
"""Render a faculty AI weekly report JSON into HTML and optionally PDF."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
from pathlib import Path
from typing import Any


CSS = r"""
:root {
  --ink:#1a3a5c; --ink-deep:#0f2742; --ink-light:#34547a;
  --accent:#8b2635; --gold:#b8923a; --paper:#faf7f2;
  --paper-warm:#f4efe5; --paper-deep:#ece5d6; --text:#2a2a2a;
  --text-soft:#5a5a5a; --text-muted:#8a8578; --line:rgba(26,58,92,.18);
  --c1:#1a4a7a; --c1-bg:#eaf0f7; --c2:#2d6a4f; --c2-bg:#e8f0eb;
  --c3:#6b3fa0; --c3-bg:#efeaf6; --c4:#a04020; --c4-bg:#f5ebe4;
  --c5:#8b2635; --c5-bg:#f3e8ea;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#e6e1d4;background-image:radial-gradient(circle at 10% 5%,rgba(184,146,58,.06),transparent 40%),radial-gradient(circle at 90% 95%,rgba(26,58,92,.05),transparent 40%);font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;color:var(--text);padding:40px 20px;line-height:1.75;font-size:14.5px}
a{color:inherit;text-decoration:none}
.newspaper{max-width:1100px;margin:0 auto;background:var(--paper);box-shadow:0 8px 40px rgba(0,0,0,.10),0 2px 6px rgba(0,0,0,.05)}
.masthead{padding:36px 60px 24px;border-bottom:1px solid var(--ink)}
.masthead-top{display:flex;justify-content:space-between;align-items:center;font-family:Georgia,serif;font-size:11.5px;color:var(--ink);letter-spacing:2px;text-transform:uppercase;padding-bottom:18px;border-bottom:1px solid var(--line)}
.masthead-top .left{font-style:italic}.masthead-top .right{font-weight:700}
.title-block{text-align:center;padding:30px 0 22px}.title-en{font-family:Georgia,serif;font-style:italic;font-size:13px;color:var(--accent);letter-spacing:5px;margin-bottom:14px;text-transform:uppercase}
.title-cn{font-family:"Noto Serif SC","Songti SC",serif;font-size:54px;font-weight:900;color:var(--ink-deep);letter-spacing:14px;line-height:1;text-indent:14px}
.title-divider{width:60px;height:3px;background:var(--accent);margin:18px auto 14px;position:relative}.title-divider:before,.title-divider:after{content:"";position:absolute;top:1px;width:80px;height:1px;background:var(--ink)}.title-divider:before{right:75px}.title-divider:after{left:75px}
.title-sub{font-family:"Noto Serif SC","Songti SC",serif;font-size:13.5px;color:var(--text-soft);letter-spacing:5px;text-indent:5px}
.masthead-meta{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;padding-top:18px;border-top:1px solid var(--line);font-family:"Noto Serif SC","Songti SC",serif;font-size:12px;color:var(--ink)}
.ornament{color:var(--accent);margin:0 8px}.group{display:flex;align-items:center}
.editorial-note{margin:36px 60px 0;padding:22px 28px;background:var(--paper-warm);border-left:4px solid var(--accent);border-right:1px solid var(--line);font-size:13.5px;color:var(--text-soft);line-height:1.85;position:relative}
.editorial-note:before{content:"编者按 · EDITOR'S NOTE";position:absolute;top:-10px;left:20px;background:var(--paper);padding:0 12px;font-family:"Noto Serif SC","Songti SC",serif;font-size:11px;font-weight:700;color:var(--accent);letter-spacing:2px}
.editorial-note strong{color:var(--ink-deep);font-weight:600}
.summary-section{margin:40px 60px 0}.summary-title{text-align:center;margin-bottom:22px;position:relative}.summary-title:before,.summary-title:after{content:"";position:absolute;top:50%;width:30%;height:1px;background:var(--ink)}.summary-title:before{left:0}.summary-title:after{right:0}
.summary-title h2{display:inline-block;font-family:"Noto Serif SC","Songti SC",serif;font-size:22px;font-weight:700;color:var(--ink-deep);letter-spacing:8px;padding:0 24px;background:var(--paper);text-indent:8px}
.summary-grid{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--ink);background:var(--paper-warm)}
.summary-cell{padding:22px 20px;border-right:1px dashed var(--line);position:relative}.summary-cell:last-child{border-right:none}.summary-cell .num{font-family:Georgia,serif;font-size:32px;font-weight:700;color:var(--accent);line-height:1;margin-bottom:10px}.summary-cell .label{font-family:"Noto Serif SC","Songti SC",serif;font-size:11.5px;font-weight:600;color:var(--ink);letter-spacing:2px;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--line)}.summary-cell .desc{font-size:12.5px;color:var(--text-soft);line-height:1.65}
.content{padding:24px 60px 50px}.section{margin-top:48px;break-inside:auto}.section:first-child{margin-top:32px}.section-header{display:flex;align-items:flex-end;gap:24px;margin-bottom:30px;padding-bottom:18px;border-bottom:3px double var(--ink);position:relative}.section-number{font-family:Georgia,serif;font-style:italic;font-size:84px;font-weight:700;line-height:.85;color:var(--accent);letter-spacing:-2px}.section-meta{flex:1;padding-bottom:6px}.section-tag{display:inline-block;font-family:Georgia,serif;font-size:10.5px;font-weight:700;letter-spacing:3px;color:var(--paper);background:var(--ink);padding:3px 12px;margin-bottom:10px;text-transform:uppercase}.section-title{font-family:"Noto Serif SC","Songti SC",serif;font-size:26px;font-weight:700;color:var(--ink-deep);letter-spacing:3px;line-height:1.2;margin-bottom:6px}.section-sub{font-family:"Noto Serif SC","Songti SC",serif;font-size:12.5px;color:var(--text-muted);font-style:italic;letter-spacing:1px}
.s1 .section-number{color:var(--c1)}.s2 .section-number{color:var(--c2)}.s3 .section-number{color:var(--c3)}.s4 .section-number{color:var(--c4)}.s5 .section-number{color:var(--c5)}
.s1 .section-tag{background:var(--c1)}.s2 .section-tag{background:var(--c2)}.s3 .section-tag{background:var(--c3)}.s4 .section-tag{background:var(--c4)}.s5 .section-tag{background:var(--c5)}
.articles{display:flex;flex-direction:column;gap:32px}.article{display:grid;grid-template-columns:60px 1fr;gap:24px;padding-bottom:32px;border-bottom:1px dotted var(--line);break-inside:avoid}.article:last-child{border-bottom:none;padding-bottom:0}.article-num{font-family:Georgia,serif;font-size:48px;font-weight:700;line-height:.9;color:var(--ink-light);text-align:right;padding-top:4px;border-right:1px solid var(--line);padding-right:18px;margin-right:-12px;letter-spacing:-1px}.s4 .article-num{font-size:36px;padding-top:10px}.article-num .num-tag{display:block;font-family:Georgia,serif;font-style:italic;font-size:10px;font-weight:400;color:var(--text-muted);letter-spacing:1px;margin-top:4px;padding-top:4px;border-top:1px solid var(--line)}
.article-title{font-family:"Noto Serif SC","Songti SC",serif;font-size:19px;font-weight:700;line-height:1.45;color:var(--ink-deep);margin-bottom:10px}.article-title a:hover{text-decoration:underline}.article-source{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--line);font-family:Georgia,serif;font-size:11.5px;font-style:italic;color:var(--text-muted);letter-spacing:1px}.source-badge{display:inline-block;font-family:"Noto Sans SC",sans-serif;font-style:normal;font-size:11px;font-weight:600;letter-spacing:.5px;padding:2px 10px;background:var(--paper-deep);color:var(--ink);border:1px solid var(--line)}
.source-badge.red{background:var(--c5-bg);color:var(--c5);border-color:var(--c5)}.source-badge.blue{background:var(--c1-bg);color:var(--c1);border-color:var(--c1)}.source-badge.green{background:var(--c2-bg);color:var(--c2);border-color:var(--c2)}.source-badge.gold{background:#f5edd6;color:#8b6914;border-color:#b8923a}
.article-body{font-size:14px;color:var(--text);text-align:justify;line-height:1.85}.article-body p{margin-bottom:10px}.article-body strong{color:var(--ink-deep);font-weight:600}.insight{margin-top:16px;padding:14px 18px 14px 22px;background:var(--paper-warm);border-left:3px solid var(--gold);font-size:13px;color:var(--text-soft);line-height:1.75;position:relative}.insight:before{content:"※";color:var(--accent);font-size:16px;margin-right:8px;font-weight:700}.insight strong{color:var(--accent);font-family:"Noto Serif SC","Songti SC",serif;letter-spacing:.5px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}.tag{display:inline-block;font-size:11px;font-weight:500;letter-spacing:.5px;padding:2px 10px;color:var(--text-soft);background:transparent;border:1px solid var(--line)}.tag.primary{color:var(--ink);border-color:var(--ink);background:var(--paper-warm)}.tag.date{font-family:Georgia,serif;font-style:italic}
.data-note{margin:30px 60px;padding:16px 20px;background:var(--paper-warm);border-top:1px solid var(--line);font-size:12px;color:var(--text-soft);line-height:1.8}.footer{margin-top:30px;padding:30px 60px 36px;border-top:6px double var(--ink);background:var(--paper-warm);text-align:center}.footer .footer-title{font-family:"Noto Serif SC","Songti SC",serif;font-size:15px;font-weight:700;color:var(--ink-deep);letter-spacing:3px;margin-bottom:10px}.footer p{font-size:12px;color:var(--text-soft);letter-spacing:.5px;line-height:1.9;margin:4px 0}.footer .editor-line{margin-top:14px;padding-top:14px;border-top:1px solid var(--line);font-family:Georgia,serif;font-style:italic;font-size:11px;color:var(--text-muted);letter-spacing:1.5px}
@page{size:A4;margin:12mm}@media print{body{background:#fff;padding:0}.newspaper{max-width:none;box-shadow:none}.article{break-inside:avoid}.section-header{break-after:avoid}}
@media(max-width:780px){body{padding:20px 10px}.masthead,.summary-section,.editorial-note,.content,.footer,.data-note{padding-left:24px;padding-right:24px}.editorial-note,.summary-section,.data-note{margin-left:0;margin-right:0}.title-cn{font-size:36px;letter-spacing:8px}.summary-grid{grid-template-columns:repeat(2,1fr)}.section-number{font-size:60px}.section-title{font-size:20px}.article{grid-template-columns:40px 1fr;gap:14px}.article-num{font-size:32px;padding-right:10px}}
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def badge_class(index: int, provenance: str) -> str:
    if provenance == "web":
        return "green"
    return ["red", "blue", "gold"][index % 3]


def render_summary(summary: list[dict[str, Any]]) -> str:
    cells = []
    for idx, item in enumerate(summary[:4], start=1):
        cells.append(
            f'<div class="summary-cell"><div class="num">{idx:02d}</div>'
            f'<div class="label">{esc(item.get("label"))}</div>'
            f'<div class="desc">{esc(item.get("desc"))}</div></div>'
        )
    while len(cells) < 4:
        idx = len(cells) + 1
        cells.append(
            f'<div class="summary-cell"><div class="num">{idx:02d}</div>'
            '<div class="label">本 周 要 情</div><div class="desc">待补充</div></div>'
        )
    return "\n".join(cells)


def render_article(item: dict[str, Any], index: int, section_index: int) -> str:
    title = esc(item.get("title"))
    url = esc(item.get("url"))
    provenance = str(item.get("provenance") or "api")
    source_names = item.get("source_names") or ["来源未标注"]
    badges = []
    for badge_index, source in enumerate(source_names[:4]):
        badges.append(
            f'<span class="source-badge {badge_class(badge_index, provenance)}">{esc(source)}</span>'
        )
    date = esc(item.get("published_at") or "")
    body_parts = []
    for paragraph in item.get("body") or []:
        if paragraph:
            body_parts.append(f"<p>{esc(paragraph)}</p>")
    if not body_parts and item.get("summary"):
        body_parts.append(f"<p>{esc(item.get('summary'))}</p>")
    insight = item.get("why_it_matters")
    insight_html = (
        f'<div class="insight"><strong>对教学科研的参考 —— </strong>{esc(insight)}</div>'
        if insight else ""
    )
    tags = item.get("tags") or []
    tag_html = "".join(f'<span class="tag primary">{esc(tag)}</span>' for tag in tags[:5])
    verified = (item.get("verification") or {}).get("status")
    if verified:
        tag_html += f'<span class="tag date">{esc(verified)}</span>'
    num = f"{index:02d}" if section_index != 4 else ("沪" if index == 1 else "深" if index == 2 else f"{index:02d}")
    num_tag = "No. %02d" % index if section_index != 4 else "SISTER"
    return f"""
<div class="article">
  <div class="article-num">{num}<span class="num-tag">{num_tag}</span></div>
  <div class="article-content">
    <h3 class="article-title"><a href="{url}">{title}</a></h3>
    <div class="article-source">
      {''.join(badges)}
      <span>·</span><span>{date}</span>
    </div>
    <div class="article-body">{''.join(body_parts)}</div>
    {insight_html}
    <div class="tags">{tag_html}</div>
  </div>
</div>"""


def render_section(section: dict[str, Any], section_index: int, date_range: str) -> str:
    items = [
        item for item in section.get("items") or []
        if (item.get("verification") or {}).get("status") != "removed"
    ]
    articles = "\n".join(
        render_article(item, idx, section_index)
        for idx, item in enumerate(items[:8], start=1)
    )
    return f"""
<section class="section s{section_index}">
  <div class="section-header">
    <div class="section-number">{esc(section.get("number") or section_index)}</div>
    <div class="section-meta">
      <span class="section-tag">{esc(section.get("tag"))}</span>
      <h2 class="section-title">{esc(section.get("title"))}</h2>
      <div class="section-sub">{esc(section.get("subtitle") or date_range)}</div>
    </div>
  </div>
  <div class="articles">{articles}</div>
</section>"""


def render_html(report: dict[str, Any]) -> str:
    title = report.get("title") or "人工智能信息速递"
    date_range = report.get("date_range_label") or ""
    sections = report.get("sections") or []
    rendered_sections = "\n".join(
        render_section(section, idx, date_range)
        for idx, section in enumerate(sections[:5], start=1)
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} · {esc(report.get("issue_label"))} · 全院教师版</title>
  <style>{CSS}</style>
</head>
<body>
<article class="newspaper">
  <header class="masthead">
    <div class="masthead-top">
      <span class="left">Internal Reference · For Faculty Use Only</span>
      <span class="right">{esc(report.get("volume_label") or "")}</span>
    </div>
    <div class="title-block">
      <div class="title-en">The AI Weekly Herald</div>
      <h1 class="title-cn">{esc(title)}</h1>
      <div class="title-divider"></div>
      <div class="title-sub">聚 焦 人 工 智 能 · 赋 能 教 育 创 新</div>
    </div>
    <div class="masthead-meta">
      <div class="group"><span>{esc(report.get("issue_label") or "")}</span></div>
      <div class="group"><span>{esc(report.get("week_start_label") or "")}</span><span class="ornament">-</span><span>{esc(report.get("week_end_label") or "")}</span></div>
      <div class="group"><span>{esc(report.get("publisher") or "北京中关村学院 · 学工部")}</span></div>
    </div>
  </header>
  <div class="editorial-note">{esc(report.get("editorial_note") or "")}</div>
  <section class="summary-section">
    <div class="summary-title"><h2>本 周 要 情 一 览</h2></div>
    <div class="summary-grid">{render_summary(report.get("summary") or [])}</div>
  </section>
  <div class="content">{rendered_sections}</div>
  <div class="data-note"><strong>数据与校验说明：</strong>{esc(report.get("data_note") or "API 为第一优先级数据源；联网搜索仅作补充；404/不可访问链接已删除。")}</div>
  <footer class="footer">
    <div class="footer-title">人 工 智 能 信 息 速 递</div>
    <p>{esc(report.get("issue_label") or "")} · 全院教师版</p>
    <p>{esc(report.get("publisher") or "北京中关村学院 · 学工部")}</p>
    <div class="editor-line">Curated with rigor, delivered with care</div>
  </footer>
</article>
</body>
</html>"""


async def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1240, "height": 1754})
        await page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        await page.emulate_media(media="print")
        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "12mm", "right": "10mm", "bottom": "12mm", "left": "10mm"},
        )
        await browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_json", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("output/faculty-weekly"))
    parser.add_argument("--html-name", default="ai-weekly-report-for-faculty.html")
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()

    report = json.loads(args.report_json.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    html_path = args.out_dir / args.html_name
    html_path.write_text(render_html(report), encoding="utf-8")
    print(f"HTML: {html_path}")

    if args.pdf:
        pdf_path = html_path.with_suffix(".pdf")
        try:
            asyncio.run(html_to_pdf(html_path, pdf_path))
            print(f"PDF: {pdf_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"PDF conversion failed: {exc}")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
