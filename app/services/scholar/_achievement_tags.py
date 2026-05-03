"""Normalize high-signal achievement tags for scholar list/detail responses."""
from __future__ import annotations

import re
from typing import Any

VENUE_ACHIEVEMENT_TAG_OPTIONS: tuple[str, ...] = (
    "ICML",
    "NeurIPS",
    "ICLR",
    "CVPR",
    "ICCV",
    "ECCV",
    "ACL",
    "EMNLP",
    "NAACL",
    "AAAI",
    "IJCAI",
    "KDD",
    "SIGIR",
    "WWW",
    "CHI",
    "SIGGRAPH",
    "SIGMOD",
    "VLDB",
    "ICDE",
    "SOSP",
    "OSDI",
    "NSDI",
    "USENIX Security",
    "CCS",
    "S&P",
    "NDSS",
    "PLDI",
    "POPL",
    "FOCS",
    "STOC",
    "SODA",
    "Nature",
    "Science",
    "Cell",
)

COMPETITION_ACHIEVEMENT_TAG_OPTIONS: tuple[str, ...] = ("SC Student", "ICPC")

ACHIEVEMENT_TAG_OPTIONS: tuple[str, ...] = (
    *VENUE_ACHIEVEMENT_TAG_OPTIONS,
    *COMPETITION_ACHIEVEMENT_TAG_OPTIONS,
)

_TAG_MATCHERS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "ICML",
        (re.compile(r"\bICML\b"), re.compile("INTERNATIONAL CONFERENCE ON MACHINE LEARNING")),
    ),
    (
        "NeurIPS",
        (
            re.compile(r"\bNEURIPS\b"),
            re.compile(r"\bNIPS\b"),
            re.compile("NEURAL INFORMATION PROCESSING SYSTEMS"),
        ),
    ),
    (
        "ICLR",
        (
            re.compile(r"\bICLR\b"),
            re.compile("INTERNATIONAL CONFERENCE ON LEARNING REPRESENTATIONS"),
        ),
    ),
    ("CVPR", (re.compile(r"\bCVPR\b"), re.compile("COMPUTER VISION AND PATTERN RECOGNITION"))),
    ("ICCV", (re.compile(r"\bICCV\b"), re.compile("INTERNATIONAL CONFERENCE ON COMPUTER VISION"))),
    ("ECCV", (re.compile(r"\bECCV\b"), re.compile("EUROPEAN CONFERENCE ON COMPUTER VISION"))),
    ("ACL", (re.compile(r"\bACL\b"), re.compile("ASSOCIATION FOR COMPUTATIONAL LINGUISTICS"))),
    (
        "EMNLP",
        (
            re.compile(r"\bEMNLP\b"),
            re.compile("EMPIRICAL METHODS IN NATURAL LANGUAGE PROCESSING"),
        ),
    ),
    ("NAACL", (re.compile(r"\bNAACL\b"), re.compile("NORTH AMERICAN CHAPTER OF THE ACL"))),
    ("AAAI", (re.compile(r"\bAAAI\b"), re.compile("AAAI CONFERENCE ON ARTIFICIAL INTELLIGENCE"))),
    (
        "IJCAI",
        (
            re.compile(r"\bIJCAI\b"),
            re.compile("INTERNATIONAL JOINT CONFERENCE ON ARTIFICIAL INTELLIGENCE"),
        ),
    ),
    ("KDD", (re.compile(r"\bKDD\b"), re.compile("KNOWLEDGE DISCOVERY AND DATA MINING"))),
    ("SIGIR", (re.compile(r"\bSIGIR\b"), re.compile("INFORMATION RETRIEVAL"))),
    (
        "WWW",
        (
            re.compile(r"\bWWW\b"),
            re.compile(r"\bTHE WEB CONFERENCE\b"),
            re.compile("WORLD WIDE WEB CONFERENCE"),
        ),
    ),
    ("CHI", (re.compile(r"\bCHI\b"), re.compile("HUMAN FACTORS IN COMPUTING SYSTEMS"))),
    ("SIGGRAPH", (re.compile(r"\bSIGGRAPH\b"),)),
    ("SIGMOD", (re.compile(r"\bSIGMOD\b"),)),
    ("VLDB", (re.compile(r"\bVLDB\b"), re.compile("VERY LARGE DATA BASES"))),
    ("ICDE", (re.compile(r"\bICDE\b"), re.compile("INTERNATIONAL CONFERENCE ON DATA ENGINEERING"))),
    ("SOSP", (re.compile(r"\bSOSP\b"), re.compile("SYMPOSIUM ON OPERATING SYSTEMS PRINCIPLES"))),
    ("OSDI", (re.compile(r"\bOSDI\b"), re.compile("OPERATING SYSTEMS DESIGN AND IMPLEMENTATION"))),
    ("NSDI", (re.compile(r"\bNSDI\b"), re.compile("NETWORKED SYSTEMS DESIGN AND IMPLEMENTATION"))),
    ("USENIX Security", (re.compile(r"\bUSENIX SECURITY\b"), re.compile(r"\bUSENIX SEC\b"))),
    ("CCS", (re.compile(r"\bACM CCS\b"), re.compile(r"\bCCS\b"))),
    (
        "S&P",
        (
            re.compile(r"\bIEEE S P\b"),
            re.compile("IEEE SYMPOSIUM ON SECURITY AND PRIVACY"),
            re.compile(r"\bOAKLAND\b"),
        ),
    ),
    ("NDSS", (re.compile(r"\bNDSS\b"), re.compile("NETWORK AND DISTRIBUTED SYSTEM SECURITY"))),
    (
        "PLDI",
        (re.compile(r"\bPLDI\b"), re.compile("PROGRAMMING LANGUAGE DESIGN AND IMPLEMENTATION")),
    ),
    ("POPL", (re.compile(r"\bPOPL\b"), re.compile("PRINCIPLES OF PROGRAMMING LANGUAGES"))),
    ("FOCS", (re.compile(r"\bFOCS\b"), re.compile("FOUNDATIONS OF COMPUTER SCIENCE"))),
    ("STOC", (re.compile(r"\bSTOC\b"), re.compile("SYMPOSIUM ON THEORY OF COMPUTING"))),
    ("SODA", (re.compile(r"\bSODA\b"), re.compile("SYMPOSIUM ON DISCRETE ALGORITHMS"))),
    ("Nature", (re.compile(r"^NATURE(\s|$)"),)),
    ("Science", (re.compile(r"^SCIENCE(\s|$)"),)),
    ("Cell", (re.compile(r"^CELL(\s|$)"),)),
    ("SC Student", (re.compile(r"\bSC STUDENT\b"), re.compile("STUDENT CLUSTER COMPETITION"))),
    (
        "ICPC",
        (
            re.compile(r"\bICPC\b"),
            re.compile(r"\bACM ICPC\b"),
            re.compile("INTERNATIONAL COLLEGIATE PROGRAMMING CONTEST"),
        ),
    ),
)


def _normalize_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("&", " AND ").replace("+", " PLUS ")
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().upper()


def _add_matches(text: Any, result: set[str]) -> None:
    normalized = _normalize_text(text)
    if not normalized:
        return
    for tag, patterns in _TAG_MATCHERS:
        if any(pattern.search(normalized) for pattern in patterns):
            result.add(tag)


def extract_achievement_tags(
    *,
    achievement_tags: Any = None,
    representative_publications: list[dict[str, Any]] | None = None,
    awards: list[dict[str, Any]] | None = None,
) -> list[str]:
    result: set[str] = set()

    raw_tags = achievement_tags
    if isinstance(raw_tags, list):
        for raw_tag in raw_tags:
            _add_matches(raw_tag, result)
    elif isinstance(raw_tags, str):
        _add_matches(raw_tags, result)

    for publication in representative_publications or []:
        if not isinstance(publication, dict):
            continue
        _add_matches(
            " ".join(
                str(publication.get(key) or "")
                for key in (
                    "venue",
                    "conference",
                    "journal",
                    "venue_name",
                    "publication_venue",
                    "booktitle",
                )
            ),
            result,
        )

    for award in awards or []:
        if not isinstance(award, dict):
            continue
        _add_matches(
            " ".join(
                str(award.get(key) or "")
                for key in ("title", "level", "grantor", "description")
            ),
            result,
        )

    return [tag for tag in ACHIEVEMENT_TAG_OPTIONS if tag in result]
