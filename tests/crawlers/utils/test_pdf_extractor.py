"""Tests for PDF URL extraction."""
from bs4 import BeautifulSoup
import pytest

from app.crawlers.utils.pdf_extractor import extract_pdf_url


def test_extract_with_css_selector():
    """Test extraction using CSS selector from config."""
    html = """
    <html>
        <div class="attachments">
            <a href="/files/document.pdf">下载附件</a>
        </div>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    config = {"pdf_selector": "div.attachments a[href$='.pdf']"}

    result = extract_pdf_url(soup, "https://example.com/page", "Test Title", config)

    assert result == "https://example.com/files/document.pdf"


def test_extract_with_relative_url():
    """Test relative URL conversion to absolute."""
    html = '<a href="../docs/paper.pdf">PDF</a>'
    soup = BeautifulSoup(html, "html.parser")
    config = {"pdf_selector": "a"}

    result = extract_pdf_url(soup, "https://example.com/news/article", "Title", config)

    assert result == "https://example.com/docs/paper.pdf"


def test_extract_returns_none_when_no_pdf():
    """Test returns None when no PDF found."""
    html = "<html><body>No PDFs here</body></html>"
    soup = BeautifulSoup(html, "html.parser")
    config = {}

    result = extract_pdf_url(soup, "https://example.com", "Title", config)

    assert result is None


def test_extract_smart_match_basic():
    """Test smart matching finds PDF link."""
    html = """
    <html>
        <body>
            <a href="https://example.com/paper.pdf">Download PDF</a>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    config = {}  # No explicit selector, use smart matching

    result = extract_pdf_url(soup, "https://example.com", "Paper Title", config)

    assert result == "https://example.com/paper.pdf"
