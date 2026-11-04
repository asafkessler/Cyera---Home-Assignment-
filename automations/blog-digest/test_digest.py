"""Unit tests for the digest's parsing, state and ticket-building logic (no network, no AI)."""
import json
from pathlib import Path

import httpx
import pytest

import digest

BLOG = "https://blog.example.com/blog"

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Blog</title>
<item><title>Newest post</title><link>https://blog.example.com/blog/newest</link><pubDate>Tue, 04 Nov 2026 08:00:00 GMT</pubDate></item>
<item><title>Older post</title><link>https://blog.example.com/blog/older</link></item>
</channel></rss>"""

INDEX_HTML = """<html><body><nav><a href="/blog">Blog</a><a href="/blog/tag/nhi">tag</a></nav>
<main>
<a href="/blog/first-article?utm=x">First</a>
<a href="https://blog.example.com/blog/second-article">Second</a>
<a href="/blog/first-article">First again</a>
<a href="/blog/page/2">Next</a>
<a href="https://elsewhere.example.org/blog/foreign">Foreign</a>
</main></body></html>"""

ARTICLE_HTML = """<html><head><title>Ignored title</title>
<meta property="og:title" content="First article title">
<meta property="article:published_time" content="2026-11-03T10:00:00Z"></head>
<body><header>Site header</header><nav>menu</nav>
<article><h1>First article title</h1><p>Paragraph one about service accounts.</p>
<script>var x = 1;</script><p>Paragraph   two is   here.</p></article>
<footer>footer text</footer></body></html>"""


def _client(routes: dict[str, httpx.Response]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(str(request.url), httpx.Response(404, text="nope"))
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_feed_is_preferred_and_first_item_is_used():
    http = _client({
        f"{BLOG}/rss.xml": httpx.Response(200, text=RSS, headers={"content-type": "application/rss+xml"}),
        "https://blog.example.com/blog/newest": httpx.Response(200, text=ARTICLE_HTML),
    })
    post = digest.fetch_latest_post(BLOG, http)
    assert post.title == "Newest post"
    assert post.url == "https://blog.example.com/blog/newest"
    assert post.published == "Tue, 04 Nov 2026 08:00:00 GMT"
    assert "Paragraph one about service accounts." in post.text


def test_html_fallback_picks_first_article_link_and_reads_metadata():
    http = _client({
        BLOG: httpx.Response(200, text=INDEX_HTML),
        "https://blog.example.com/blog/first-article": httpx.Response(200, text=ARTICLE_HTML),
    })
    post = digest.fetch_latest_post(BLOG, http)
    assert post.url == "https://blog.example.com/blog/first-article"   # query string stripped, listing links skipped
    assert post.title == "First article title"                         # og:title beats <title>
    assert post.published == "2026-11-03T10:00:00Z"
    assert "Site header" not in post.text and "var x" not in post.text and "footer text" not in post.text
    assert "Paragraph two is here." in post.text                                 # whitespace normalised


def test_no_posts_is_a_clear_error():
    http = _client({BLOG: httpx.Response(200, text="<html><body><a href='/about'>About</a></body></html>")})
    with pytest.raises(digest.DigestError, match="Could not find any blog post"):
        digest.fetch_latest_post(BLOG, http)


def test_atom_feed_is_supported():
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom post</title>
    <link href="https://blog.example.com/blog/atom-post"/><published>2026-01-01T00:00:00Z</published></entry></feed>"""
    assert digest._parse_feed(atom) == ("Atom post", "https://blog.example.com/blog/atom-post", "2026-01-01T00:00:00Z")


def test_build_finding_shape():
    post = digest.Post(title="T" * 300, url="https://x/blog/p", published="2026-01-01", text="...")
    finding = digest.build_finding(post, "- a\n- b", "SCRUM")
    assert finding["project_key"] == "SCRUM"
    assert finding["summary"].startswith("NHI Blog Digest: ") and len(finding["summary"]) <= 255
    assert "Source: https://x/blog/p" in finding["description"] and "Published: 2026-01-01" in finding["description"]
    assert finding["issue_type"] == "Task"


def test_create_ticket_surfaces_api_errors():
    http = _client({"http://api/api/v1/findings": httpx.Response(401, json={"error": {"code": "invalid_api_key", "message": "bad key", "details": {}}})})
    with pytest.raises(digest.DigestError, match="401 invalid_api_key"):
        digest.create_ticket({"x": 1}, api_url="http://api", api_key="k", http=http)


def test_summarize_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(digest.DigestError, match="ANTHROPIC_API_KEY is not set"):
        digest.summarize(digest.Post("t", "u", None, "text"), model="m")


def test_state_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    assert digest.load_state(path) == {}
    digest.save_state(path, {"last_post_url": "u", "issue_key": "SCRUM-1"})
    assert json.loads(path.read_text())["issue_key"] == "SCRUM-1"
    assert digest.load_state(path)["last_post_url"] == "u"


WEBFLOW_HTML = """<html><head><title>Oasis and Cyera to Build Next-Gen AI Security Platform</title>
<meta property="og:title" content="Oasis and Cyera to Build Next-Gen AI Security Platform"></head>
<body>
<div class="nav"><a href="/demo">Request a Demo</a><a href="/resources">Resource Center</a><a href="/blog">/Blog</a><a href="/">/</a></div>
<h1>Building The Next-Generation AI Security Platform</h1>
<div class="hidden"><h1>Building The Next-Generation AI Security Platform</h1></div>
<div class="author"><div>Danny Brickman</div><div>Co-founder &amp; CEO</div></div>
<div class="meta"><div>Published on</div><div>Jul 28, 2026</div><div>Updated</div><div>Jul 28, 2026</div></div>
<div class="w-richtext">
<p>Today, Oasis Security steps into a new phase of acceleration. We have signed a letter of intent to be acquired by Cyera.</p>
<p>AI agents have moved from pilots into production faster than any identity model was built to handle.</p>
<h2>What this means</h2>
<ul><li>Access and data are the two control points.</li><li>Go</li></ul>
</div>
<div class="footer"><a href="/privacy">Privacy policy</a></div>
</body></html>"""


def test_webflow_page_without_article_wrapper():
    text = digest._extract_article_text(WEBFLOW_HTML)
    lines = text.splitlines()
    assert lines[0] == "Building The Next-Generation AI Security Platform"   # title once, duplicate dropped
    assert "Request a Demo" not in text and "Resource Center" not in text and "Privacy policy" not in text
    assert "Danny Brickman" not in text and "Published on" not in text        # short non-content blocks dropped
    assert "letter of intent to be acquired by Cyera" in text
    assert "What this means" in text and "Access and data are the two control points." in text
    assert "Go" not in lines                                                   # one-word list item dropped


def test_published_date_fallbacks():
    assert digest._published_date(WEBFLOW_HTML) == "Jul 28, 2026"
    assert digest._published_date('<script type="application/ld+json">{"datePublished": "2026-07-28T10:00:00Z"}</script>') == "2026-07-28T10:00:00Z"
    assert digest._published_date('<time datetime="2026-01-02">Jan 2</time>') == "2026-01-02"
    assert digest._published_date("<p>nothing</p>") is None
