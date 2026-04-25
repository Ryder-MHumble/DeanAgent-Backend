from __future__ import annotations

from typing import Any

import pytest

from app.crawlers.base import CrawlStatus
from app.crawlers.parsers.competition_source import CompetitionSourceCrawler
from app.crawlers.parsers.evidence_only_source import EvidenceOnlySourceCrawler
from app.crawlers.parsers.github_talent_source import GitHubTalentSourceCrawler
from app.crawlers.parsers.paper_author_source import PaperAuthorSourceCrawler


def _assert_talent_signal(item: Any, *, signal_type: str, record_status: str) -> None:
    signal = item.extra["talent_signal"]
    assert signal["signal_type"] == signal_type
    assert signal["record_status"] == record_status

    required_keys = {
        "signal_type",
        "candidate_name",
        "university",
        "department",
        "email",
        "track",
        "record_status",
        "confidence",
        "identity_hints",
        "source_metrics",
        "evidence_title",
        "evidence_url",
        "notes",
    }
    assert set(signal.keys()) == required_keys
    assert signal["evidence_url"]


@pytest.mark.asyncio
async def test_competition_source_parses_rank_table_as_partial_signal(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch_page(url: str, **_kwargs):
        assert url == "https://example.com/leaderboard"
        return """
        <table>
          <tbody>
            <tr>
              <td class="rank">1</td>
              <td class="name">Alice Chen</td>
              <td class="university">浙江大学</td>
              <td class="award">Gold</td>
              <td class="team">ZJU Alpha</td>
            </tr>
          </tbody>
        </table>
        """

    monkeypatch.setattr(
        "app.crawlers.parsers.competition_source.fetch_page",
        fake_fetch_page,
    )

    crawler = CompetitionSourceCrawler(
        {
            "id": "icpc_rankings",
            "name": "ICPC Rankings",
            "dimension": "talent_scout",
            "entity_family": "competition",
            "capture_mode": "semi_structured",
            "fallback_mode": "evidence_only",
            "adapter_key": "rank_table",
            "sheet_name": "ICPC",
            "seed_urls": ["https://example.com/leaderboard"],
            "track": "algorithm",
            "competition_name": "ICPC World Finals",
            "season_year": 2026,
            "selectors": {
                "row": "tr",
                "candidate_name": ".name",
                "university": ".university",
                "award_level": ".award",
                "ranking": ".rank",
                "team_name": ".team",
            },
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    _assert_talent_signal(items[0], signal_type="competition", record_status="partial")
    assert items[0].extra["competition_name"] == "ICPC World Finals"
    assert items[0].extra["season_year"] == 2026
    assert items[0].extra["award_level"] == "Gold"
    assert items[0].extra["ranking"] == "1"
    assert items[0].extra["team_name"] == "ZJU Alpha"


@pytest.mark.asyncio
async def test_competition_source_auto_parses_chinese_award_table(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    async def fake_fetch_page(url: str, **_kwargs):
        calls.append(url)
        if url == "https://example.com/home":
            return "<html><body><p>蓝桥杯主页，没有获奖表格</p></body></html>"
        return """
        <html><body>
          <h1>热烈祝贺2025年蓝桥杯省赛获奖</h1>
          <table>
            <tbody>
              <tr>
                <td>序号</td>
                <td>姓名</td>
                <td>二级学院</td>
                <td>科目</td>
                <td>组别</td>
                <td>导师</td>
                <td>等次</td>
                <td>备注</td>
              </tr>
              <tr>
                <td>1</td>
                <td>李陈星</td>
                <td>数学与计算机学院（大数据学院）</td>
                <td>C/C++程序设计</td>
                <td>大学 B组</td>
                <td>刘彬</td>
                <td>一等奖</td>
                <td>入围全国决赛</td>
              </tr>
              <tr>
                <td>2</td>
                <td>张珂媛</td>
                <td>数学与计算机学院（大数据学院）</td>
                <td>C/C++程序设计</td>
                <td>大学 B组</td>
                <td>刘彬</td>
                <td>一等奖</td>
                <td>入围全国决赛</td>
              </tr>
            </tbody>
          </table>
        </body></html>
        """

    monkeypatch.setattr(
        "app.crawlers.parsers.competition_source.fetch_page",
        fake_fetch_page,
    )

    crawler = CompetitionSourceCrawler(
        {
            "id": "lanqiao",
            "name": "蓝桥杯",
            "dimension": "talent_scout",
            "entity_family": "competition",
            "capture_mode": "semi_structured",
            "fallback_mode": "evidence_only",
            "adapter_key": "rank_table",
            "sheet_name": "LanQiao",
            "seed_urls": [
                "https://example.com/home",
                {
                    "url": "https://example.com/lanqiao-awards",
                    "source_university": "攀枝花学院",
                },
            ],
            "track": "algorithm",
            "competition_name": "蓝桥杯",
            "season_year": 2025,
        }
    )

    items = await crawler.fetch_and_parse()

    assert calls == ["https://example.com/home", "https://example.com/lanqiao-awards"]
    assert [item.title for item in items] == ["李陈星", "张珂媛"]
    _assert_talent_signal(items[0], signal_type="competition", record_status="partial")
    assert items[0].url == "https://example.com/lanqiao-awards"
    assert items[0].extra["competition_name"] == "蓝桥杯"
    assert items[0].extra["season_year"] == 2025
    assert items[0].extra["award_level"] == "一等奖"
    assert items[0].extra["ranking"] == "1"
    assert items[0].extra["subject"] == "C/C++程序设计"
    assert items[0].extra["competition_group"] == "大学 B组"
    assert items[0].extra["instructor"] == "刘彬"
    assert items[0].extra["notes"] == "入围全国决赛"
    assert items[0].extra["talent_signal"]["university"] == "攀枝花学院"
    assert items[0].extra["talent_signal"]["department"] == "数学与计算机学院（大数据学院）"


@pytest.mark.asyncio
async def test_competition_source_cleans_name_with_student_id_from_award_table(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch_page(url: str, **_kwargs):
        assert url == "https://example.com/sues-awards"
        return """
        <table>
          <tr>
            <td>竞赛代码</td>
            <td>竞赛名称</td>
            <td>学生（姓名：学号）</td>
            <td>指导教师</td>
            <td>省市获奖</td>
            <td>国家获奖</td>
            <td>授予部门</td>
          </tr>
          <tr>
            <td>B1-9</td>
            <td>蓝桥杯全国软件和信息技术专业人才大赛</td>
            <td>许龙飞：028122023</td>
            <td>单亮</td>
            <td>一等奖</td>
            <td>二等奖</td>
            <td>工业和信息化部人才交流中心</td>
          </tr>
        </table>
        """

    monkeypatch.setattr(
        "app.crawlers.parsers.competition_source.fetch_page",
        fake_fetch_page,
    )

    crawler = CompetitionSourceCrawler(
        {
            "id": "lanqiao",
            "name": "蓝桥杯",
            "dimension": "talent_scout",
            "entity_family": "competition",
            "capture_mode": "semi_structured",
            "fallback_mode": "evidence_only",
            "adapter_key": "rank_table",
            "sheet_name": "LanQiao",
            "seed_urls": [
                {
                    "url": "https://example.com/sues-awards",
                    "source_university": "上海工程技术大学",
                },
            ],
            "track": "software_engineering",
            "competition_name": "蓝桥杯",
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    assert items[0].title == "许龙飞"
    assert items[0].extra["award_level"] == "二等奖"
    assert items[0].extra["provincial_award_level"] == "一等奖"
    assert items[0].extra["instructor"] == "单亮"
    assert items[0].extra["talent_signal"]["university"] == "上海工程技术大学"


@pytest.mark.asyncio
async def test_competition_source_parses_tianchi_rank_list_api(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch_json(url: str, **kwargs):
        assert url == "https://tianchi.aliyun.com/v3/proxy/competition/api/race/rank/list"
        assert kwargs["params"] == {"raceId": "532406", "pageNum": "1"}
        return {
            "data": {
                "list": [
                    {
                        "teamName": "nick9969620957-37208",
                        "rank": 1,
                        "score": 0.1490945787217,
                        "teamLeaderOrganization": "西安电子科技大学",
                        "gmtSubmit": "2025-11-18 22:44:22",
                        "teamMemberList": [
                            {
                                "nickName": "若有眠",
                                "userId": 1095280908110,
                                "isStudent": True,
                            }
                        ],
                    }
                ],
                "total": 1,
                "pageSize": 20,
            }
        }

    monkeypatch.setattr(
        "app.crawlers.parsers.competition_source.fetch_json",
        fake_fetch_json,
    )

    crawler = CompetitionSourceCrawler(
        {
            "id": "aliyun_tianchi",
            "name": "阿里天池",
            "dimension": "talent_scout",
            "entity_family": "competition",
            "capture_mode": "structured",
            "fallback_mode": "evidence_only",
            "adapter_key": "tianchi_rank_list",
            "sheet_name": "AliyunTianchi",
            "race_id": "532406",
            "max_pages": 1,
            "seed_urls": [
                "https://tianchi.aliyun.com/competition/entrance/532406/rankRange",
            ],
            "track": "data_mining",
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    _assert_talent_signal(items[0], signal_type="competition", record_status="structured")
    assert items[0].title == "若有眠"
    assert items[0].url == "https://tianchi.aliyun.com/competition/entrance/532406/rankRange"
    assert items[0].extra["competition_name"] == "阿里天池"
    assert items[0].extra["ranking"] == "1"
    assert items[0].extra["team_name"] == "nick9969620957-37208"
    assert items[0].extra["score"] == 0.1490945787217
    assert items[0].extra["talent_signal"]["university"] == "西安电子科技大学"
    assert items[0].extra["talent_signal"]["identity_hints"]["user_id"] == 1095280908110


@pytest.mark.asyncio
async def test_competition_source_parses_lanqiao_official_archive(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch_bytes(url: str, **_kwargs):
        assert url == "https://example.com/lanqiao.rar"
        return b"rar-bytes"

    def fake_extract_archive(_archive_bytes: bytes):
        return [
            (
                "软件赛/软件赛-CC++程序设计大学B组总决赛获奖名单.pdf",
                """
                第十五届蓝桥杯全国软件和信息技术专业人才大赛全国总决赛
                C/C++程序设计大学 B 组获奖名单
                准考证号 学校名称 考生姓名 科目名称 奖项
                15549481 深圳大学 张艺轩 C/C++程序设计大学 B 组 一等奖
                15543107 无锡学院（南京信息工程大学滨江
                学院） 王同学 C/C++程序设计大学 B 组 二等奖
                2024 年 6 月 2 日
                """,
            )
        ]

    monkeypatch.setattr(
        "app.crawlers.parsers.competition_source.fetch_bytes",
        fake_fetch_bytes,
    )
    monkeypatch.setattr(
        CompetitionSourceCrawler,
        "_extract_archive_pdf_texts",
        staticmethod(fake_extract_archive),
    )

    crawler = CompetitionSourceCrawler(
        {
            "id": "lanqiao",
            "name": "蓝桥杯",
            "dimension": "talent_scout",
            "entity_family": "competition",
            "capture_mode": "structured",
            "fallback_mode": "evidence_only",
            "adapter_key": "lanqiao_archive",
            "sheet_name": "LanQiao",
            "seed_urls": [
                {
                    "url": "https://example.com/lanqiao.rar",
                    "evidence_title": "第十五届蓝桥杯全国总决赛获奖名单归档",
                    "season_year": 2024,
                },
            ],
            "tracks": ["algorithm"],
            "competition_name": "第十五届蓝桥杯全国总决赛",
        }
    )

    items = await crawler.fetch_and_parse()

    assert [item.title for item in items] == ["张艺轩", "王同学"]
    _assert_talent_signal(items[0], signal_type="competition", record_status="structured")
    assert items[0].extra["competition_name"] == "第十五届蓝桥杯全国总决赛"
    assert items[0].extra["season_year"] == 2024
    assert items[0].extra["award_level"] == "一等奖"
    assert items[0].extra["subject"] == "C/C++程序设计大学 B 组"
    assert items[0].extra["exam_no"] == "15549481"
    assert items[0].extra["source_pdf"] == "软件赛/软件赛-CC++程序设计大学B组总决赛获奖名单.pdf"
    assert items[0].extra["talent_signal"]["university"] == "深圳大学"
    assert items[1].extra["talent_signal"]["university"] == "无锡学院（南京信息工程大学滨江学院）"
    assert "%E8%BD%AF%E4%BB%B6%E8%B5%9B" in items[0].url


@pytest.mark.asyncio
async def test_competition_source_parses_kaggle_rankings_v2(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch_payload(self):
        return {
            "userRankings": [
                {
                    "currentRanking": 1,
                    "displayName": "yuanzhe zhou",
                    "userId": 4578277,
                    "userUrl": "/yuanzhezhou",
                    "tier": "GRANDMASTER",
                    "tierForAchievementType": "GRANDMASTER",
                    "points": 158742,
                    "totalGoldMedals": 14,
                    "totalSilverMedals": 16,
                    "totalBronzeMedals": 13,
                }
            ],
            "totalUserRankings": 14402,
        }

    monkeypatch.setattr(
        CompetitionSourceCrawler,
        "_fetch_kaggle_rankings_payload",
        fake_fetch_payload,
    )

    crawler = CompetitionSourceCrawler(
        {
            "id": "kaggle_grandmaster",
            "name": "Kaggle Grandmaster",
            "dimension": "talent_scout",
            "entity_family": "competition",
            "capture_mode": "structured",
            "fallback_mode": "evidence_only",
            "adapter_key": "kaggle_rankings_v2",
            "sheet_name": "KaggleGM",
            "seed_urls": ["https://www.kaggle.com/rankings?group=competitions"],
            "tracks": ["ml"],
            "max_results": 10,
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    _assert_talent_signal(items[0], signal_type="competition", record_status="structured")
    assert items[0].title == "yuanzhe zhou"
    assert items[0].url == "https://www.kaggle.com/yuanzhezhou"
    assert items[0].extra["award_level"] == "GRANDMASTER"
    assert items[0].extra["ranking"] == "1"
    assert items[0].extra["points"] == 158742
    assert items[0].extra["talent_signal"]["identity_hints"]["kaggle_user_id"] == 4578277
    assert items[0].extra["talent_signal"]["source_metrics"]["gold_medals"] == 14


@pytest.mark.asyncio
async def test_competition_source_falls_back_to_blocked_evidence_when_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch_json(*_args, **_kwargs):
        raise RuntimeError("auth required")

    monkeypatch.setattr(
        "app.crawlers.parsers.competition_source.fetch_json",
        fake_fetch_json,
    )

    crawler = CompetitionSourceCrawler(
        {
            "id": "aliyun_tianchi",
            "name": "阿里天池",
            "dimension": "talent_scout",
            "entity_family": "competition",
            "capture_mode": "structured",
            "fallback_mode": "evidence_only",
            "adapter_key": "json_records",
            "sheet_name": "Tianchi",
            "seed_urls": ["https://example.com/tianchi"],
            "track": "data_mining",
            "requires_auth": True,
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    _assert_talent_signal(items[0], signal_type="competition", record_status="blocked")
    assert "auth required" in items[0].extra["talent_signal"]["notes"]


@pytest.mark.asyncio
async def test_paper_author_source_parses_structured_author_records(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch_json(url: str, **_kwargs):
        assert url == "https://example.com/papers"
        return {
            "data": [
                {
                    "candidate_name": "Bob Li",
                    "university": "清华大学",
                    "department": "计算机系",
                    "paper_title": "Efficient Foundation Models",
                    "venue": "NeurIPS",
                    "venue_year": 2025,
                    "author_order": 1,
                    "paper_count_in_scope": 3,
                    "citation_count": 42,
                    "dblp_pid": "123/456",
                    "evidence_url": "https://example.com/papers/1",
                }
            ]
        }

    monkeypatch.setattr(
        "app.crawlers.parsers.paper_author_source.fetch_json",
        fake_fetch_json,
    )

    crawler = PaperAuthorSourceCrawler(
        {
            "id": "semantic_scholar_author",
            "name": "Semantic Scholar Author",
            "dimension": "talent_scout",
            "entity_family": "paper_author",
            "capture_mode": "structured",
            "fallback_mode": "evidence_only",
            "adapter_key": "paper_json",
            "sheet_name": "SemanticScholar",
            "seed_urls": ["https://example.com/papers"],
            "track": "foundation_models",
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    _assert_talent_signal(items[0], signal_type="paper_author", record_status="structured")
    assert items[0].extra["venue"] == "NeurIPS"
    assert items[0].extra["venue_year"] == 2025
    assert items[0].extra["paper_title"] == "Efficient Foundation Models"
    assert items[0].extra["citation_count"] == 42


@pytest.mark.asyncio
async def test_github_talent_source_parses_contributor_records(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_fetch_json(url: str, **_kwargs):
        assert url == "https://example.com/contributors"
        return {
            "items": [
                {
                    "candidate_name": "Carol Zhang",
                    "github_login": "carol-ai",
                    "repo_full_name": "openai/example",
                    "contributions": 18,
                    "followers": 1200,
                    "company": "Research Lab",
                    "blog": "https://carol.example.com",
                    "evidence_url": "https://github.com/carol-ai",
                }
            ]
        }

    monkeypatch.setattr(
        "app.crawlers.parsers.github_talent_source.fetch_json",
        fake_fetch_json,
    )

    crawler = GitHubTalentSourceCrawler(
        {
            "id": "github_ai_repo_contributors",
            "name": "GitHub AI Repo Contributors",
            "dimension": "talent_scout",
            "entity_family": "github_talent",
            "capture_mode": "structured",
            "fallback_mode": "evidence_only",
            "adapter_key": "github_contributors",
            "sheet_name": "GitHubContribs",
            "seed_urls": ["https://example.com/contributors"],
            "track": "open_source",
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    _assert_talent_signal(items[0], signal_type="github_contributor", record_status="structured")
    assert items[0].extra["github_login"] == "carol-ai"
    assert items[0].extra["repo_full_name"] == "openai/example"
    assert items[0].extra["contributions"] == 18


@pytest.mark.asyncio
async def test_evidence_only_source_emits_blocked_rows_without_fetch():
    crawler = EvidenceOnlySourceCrawler(
        {
            "id": "openreview_author",
            "name": "OpenReview Author",
            "dimension": "talent_scout",
            "entity_family": "paper_author",
            "capture_mode": "evidence_only",
            "fallback_mode": "evidence_only",
            "adapter_key": "manual_seed",
            "sheet_name": "OpenReview",
            "seed_urls": [
                "https://openreview.net/group?id=ICLR.cc/2026/Conference",
            ],
            "track": "ml_conference",
            "requires_auth": True,
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    _assert_talent_signal(items[0], signal_type="paper_author", record_status="blocked")


@pytest.mark.asyncio
async def test_talent_scout_run_does_not_count_blocked_row_as_candidate():
    crawler = EvidenceOnlySourceCrawler(
        {
            "id": "openreview_author",
            "name": "OpenReview Author",
            "dimension": "talent_scout",
            "entity_family": "paper_author",
            "capture_mode": "evidence_only",
            "fallback_mode": "evidence_only",
            "adapter_key": "manual_seed",
            "sheet_name": "OpenReview",
            "seed_urls": [
                "https://openreview.net/group?id=ICLR.cc/2026/Conference",
            ],
            "track": "ml_conference",
            "requires_auth": True,
        }
    )

    result = await crawler.run()

    assert result.status == CrawlStatus.NO_NEW_CONTENT
    assert result.items_total == 0
    assert result.items_new == 0
    assert len(result.items) == 1
    assert result.items[0].extra["talent_signal"]["record_status"] == "blocked"
