#!/usr/bin/env python3
"""
NHI Blog Digest: fetch the latest post from a blog, summarize it with Claude,
and report it as a ticket through IdentityHub's public API.

The automation is an ordinary external client of the app: it knows nothing
about the database or the Jira credentials, only an IdentityHub API key.

    python digest.py                 # full run
    python digest.py --print-post    # fetch only: show which post would be used (no AI, no ticket)
    python digest.py --dry-run       # fetch + summarize, print the ticket, do not create it
    python digest.py --force         # run even if this post was already reported

Configuration (environment variables):
    ANTHROPIC_API_KEY      required for the summary
    IDENTITYHUB_API_KEY    required to create the ticket (create one in the app under "API keys")
    IDENTITYHUB_API_URL    default http://localhost:8000
    JIRA_PROJECT_KEY       default SCRUM
    BLOG_URL               default https://www.oasis.security/blog
    DIGEST_MODEL           default claude-opus-5-5
    DIGEST_STATE_FILE      default ./state.json (remembers the last reported post)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx

DEFAULT_BLOG_URL = "https://www.oasis.security/blog"
DEFAULT_MODEL = "claude-opus-5-5"
FEED_PATHS = ["rss.xml", "feed", "feed.xml", "atom.xml", "/rss.xml", "/feed", "/feed.xml", "/blog/rss.xml", "/blog/feed"]
USER_AGENT = "IdentityHub-BlogDigest/1.0 (+https://github.com/asafkessler/identityhub-jira-integration)"
MAX_ARTICLE_CHARS = 40_000  # plenty for a blog post; keeps the prompt bounded


class DigestError(Exception):
    """A failure with a message meant for the person reading the log."""


@dataclass
class Post:
    title: str
    url: str
    published: str | None
    text: str


# --- Step 1: find and fetch the latest post --------------------------------------------

def fetch_latest_post(blog_url: str, http: httpx.Client) -> Post:
    """RSS/Atom if the site has one (reliable), otherwise the first article link on the blog page."""
    entry = _latest_from_feed(blog_url, http) or _latest_from_html(blog_url, http)
    if entry is None:
        raise DigestError(f"Could not find any blog post at {blog_url} (no feed, no article links).")
    title, url, published = entry
    page = _get(http, url).text
    article = _extract_article_text(page)
    if not article:
        raise DigestError(f"Fetched {url} but could not extract readable text from it.")
    # The post's title is what a reader sees above the article (its <h1>). The
    # feed title is equivalent when a feed exists; og:title / <title> are SEO
    # variants that can differ from the visible heading, so they come last.
    return Post(
        title=title or _h1(page) or _html_title(page) or url,
        url=url,
        published=published or _published_date(page),
        text=article[:MAX_ARTICLE_CHARS],
    )


def _latest_from_feed(blog_url: str, http: httpx.Client) -> tuple[str, str, str | None] | None:
    for path in FEED_PATHS:
        candidate = urljoin(blog_url.rstrip("/") + "/", path)
        try:
            response = http.get(candidate)
        except httpx.HTTPError:
            continue
        if response.status_code != 200 or "xml" not in response.headers.get("content-type", "") and "<rss" not in response.text[:500] and "<feed" not in response.text[:500]:
            continue
        parsed = _parse_feed(response.text)
        if parsed:
            return parsed
    return None


def _parse_feed(xml_text: str) -> tuple[str, str, str | None] | None:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return None
    # RSS 2.0
    item = root.find("./channel/item")
    if item is not None:
        return (item.findtext("title", "").strip(), item.findtext("link", "").strip(), item.findtext("pubDate"))
    # Atom
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", ns)
    if entry is not None:
        link = entry.find("a:link", ns)
        href = link.get("href", "") if link is not None else ""
        return (entry.findtext("a:title", "", ns).strip(), href.strip(), entry.findtext("a:published", None, ns) or entry.findtext("a:updated", None, ns))
    return None


def _latest_from_html(blog_url: str, http: httpx.Client) -> tuple[str, str, str | None] | None:
    page = _get(http, blog_url).text
    base = urlparse(blog_url)
    blog_path = base.path.rstrip("/") or "/blog"
    seen: list[str] = []
    for href in _links(page):
        absolute = urljoin(blog_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc != base.netloc:
            continue
        path = parsed.path.rstrip("/")
        # An article lives one level under the blog index: /blog/<slug>
        if path.startswith(blog_path + "/") and path.count("/") == blog_path.count("/") + 1 and not _looks_like_listing(path):
            clean = absolute.split("#")[0].split("?")[0]
            if clean not in seen:
                seen.append(clean)
    if not seen:
        return None
    return ("", seen[0], None)  # title and date are read from the article page itself


def _looks_like_listing(path: str) -> bool:
    last = path.rsplit("/", 1)[-1]
    return last in {"page", "category", "categories", "tag", "tags", "author", "authors"} or last.isdigit()


# --- HTML helpers (stdlib only, to keep the automation dependency-light) --------------

class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def _links(page: str) -> list[str]:
    collector = _LinkCollector()
    collector.feed(page)
    return collector.hrefs


class _TextExtractor(HTMLParser):
    """
    Collects the text of paragraph-like elements (<p>, headings, list items).

    Navigation menus, buttons and footers are made of short links inside
    <div>s, while an article body is made of paragraphs, so keeping only
    paragraph-like blocks is a simple and robust way to isolate the content,
    with or without an <article>/<main> wrapper around it.
    """

    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "svg", "form", "button"}
    BLOCKS = {"p", "h1", "h2", "h3", "h4", "li", "blockquote", "pre"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._block_depth = 0
        self._in_content = 0
        self._current: list[str] = []
        self.blocks: list[tuple[bool, str]] = []  # (inside <article>/<main>, text)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag in {"article", "main"}:
            self._in_content += 1
        elif tag in self.BLOCKS:
            self._flush()
            self._block_depth += 1
        elif tag == "br" and self._block_depth:
            self._current.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"article", "main"} and self._in_content:
            self._in_content -= 1
        elif tag in self.BLOCKS and self._block_depth:
            self._block_depth -= 1
            self._flush()

    def handle_data(self, data):
        if not self._skip_depth and self._block_depth:
            self._current.append(data)

    def close(self):
        self._flush()
        super().close()

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._current)).strip()
        self._current = []
        if text:
            self.blocks.append((self._in_content > 0, text))


MIN_WORDS_PER_BLOCK = 3   # "Request a Demo", "Published on", author names: not content


def _extract_article_text(page: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(page)
    extractor.close()
    blocks = extractor.blocks
    inside = [text for in_content, text in blocks if in_content]
    candidates = inside if len(" ".join(inside)) >= 200 else [text for _, text in blocks]
    lines: list[str] = []
    for text in candidates:
        if len(text.split()) < MIN_WORDS_PER_BLOCK:
            continue
        if text not in lines:  # Webflow pages repeat the title in a hidden duplicate block
            lines.append(text)
    return "\n".join(lines)


_DATE_PATTERNS = [
    r'"datePublished"\s*:\s*"([^"]+)"',                                  # JSON-LD
    r"Published on\s*(?:</[^>]+>\s*<[^>]+>\s*)*([A-Z][a-z]{2,8}\.? \d{1,2}, \d{4})",  # "Published on Jul 28, 2026", possibly across tags
    r"datetime=[\"']([^\"']+)[\"']",                                     # <time datetime="...">
]


def _published_date(page: str) -> str | None:
    """Best effort: Open Graph / article meta, JSON-LD, <time>, or the visible 'Published on' text."""
    for prop in ("article:published_time", "og:article:published_time", "date", "pubdate"):
        value = _meta(page, prop)
        if value:
            return value
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, page)
        if match:
            return match.group(1).strip()
    return None


def _h1(page: str) -> str | None:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
    if not match:
        return None
    text = re.sub(r"<[^>]+>", "", match.group(1))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _html_title(page: str) -> str | None:
    return _meta(page, "og:title") or (re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I) or [None, None])[1]


def _meta(page: str, prop: str) -> str | None:
    match = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']', page, re.I)
    return match.group(1).strip() if match else None


def _get(http: httpx.Client, url: str) -> httpx.Response:
    try:
        response = http.get(url)
    except httpx.HTTPError as exc:
        raise DigestError(f"Could not fetch {url}: {exc}") from exc
    if response.status_code != 200:
        raise DigestError(f"Fetching {url} returned HTTP {response.status_code}.")
    return response


# --- Step 2: summarize with Claude ---------------------------------------------------------

SYSTEM_PROMPT = """You summarize blog posts for people who have not read them.

Write plain text, no markdown headings. Structure:
1. One sentence saying what the post is about and who wrote it, if known.
2. Three to five bullet points (lines starting with "- ") with the main points, in the post's own order.
3. One closing sentence with the post's conclusion or call to action, if it has one.
Keep the whole summary under 180 words. Stay faithful to the post; do not add opinions or facts that are not in it."""


def summarize(post: Post, *, model: str) -> str:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise DigestError("The 'anthropic' package is not installed. Run: pip install -r requirements.txt") from exc

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise DigestError(
            "ANTHROPIC_API_KEY is not set. The digest needs it for the AI summary.\n"
            "Create a key at https://console.anthropic.com/ and export it, or add it to the root .env."
        )

    client = anthropic.Anthropic()
    user_content = f"Title: {post.title}\nURL: {post.url}\n\n{post.text}"
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            # If the primary model declines the request, the API retries it on a
            # fallback model inside the same call, so the digest still runs.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as exc:
        raise DigestError("Anthropic rejected the API key (ANTHROPIC_API_KEY). Check that it is valid.") from exc
    except anthropic.RateLimitError as exc:
        raise DigestError("Anthropic rate limit reached. Try again in a minute.") from exc
    except anthropic.APIStatusError as exc:
        raise DigestError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise DigestError("Could not reach the Anthropic API. Check your network.") from exc

    if response.stop_reason == "refusal":
        raise DigestError("The model declined to summarize this post.")
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise DigestError("The model returned an empty summary.")
    return text


# --- Step 3: create the ticket through IdentityHub's public API ------------------------------

def build_finding(post: Post, summary: str, project_key: str) -> dict:
    lines = [summary, "", f"Source: {post.url}"]
    if post.published:
        lines.append(f"Published: {post.published}")
    lines.append("Summary generated automatically by the NHI Blog Digest automation.")
    return {
        "project_key": project_key,
        "summary": post.title[:255],          # the ticket title is the post title
        "description": "\n".join(lines),     # the AI summary, then where it came from
        "issue_type": "Task",
    }


def create_ticket(finding: dict, *, api_url: str, api_key: str, http: httpx.Client) -> dict:
    try:
        response = http.post(f"{api_url.rstrip('/')}/api/v1/findings", json=finding, headers={"X-API-Key": api_key})
    except httpx.HTTPError as exc:
        raise DigestError(f"Could not reach IdentityHub at {api_url}: {exc}") from exc
    if response.status_code == 201:
        return response.json()
    try:
        error = response.json()["error"]
        raise DigestError(f"IdentityHub refused the ticket ({response.status_code} {error['code']}): {error['message']}")
    except (ValueError, KeyError):
        raise DigestError(f"IdentityHub returned HTTP {response.status_code}: {response.text[:300]}")


# --- State: do not report the same post twice -------------------------------------------------

def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2))


# --- Entry point ------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--print-post", action="store_true", help="fetch the latest post and print it; no AI, no ticket")
    parser.add_argument("--dry-run", action="store_true", help="fetch and summarize, print the ticket, do not create it")
    parser.add_argument("--force", action="store_true", help="run even if this post was already reported")
    args = parser.parse_args(argv)

    blog_url = os.environ.get("BLOG_URL", DEFAULT_BLOG_URL)
    api_url = os.environ.get("IDENTITYHUB_API_URL", "http://localhost:8000")
    project_key = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")
    model = os.environ.get("DIGEST_MODEL", DEFAULT_MODEL)
    state_file = Path(os.environ.get("DIGEST_STATE_FILE", Path(__file__).with_name("state.json")))

    try:
        with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as http:
            print(f"[digest] Looking for the latest post at {blog_url} ...")
            post = fetch_latest_post(blog_url, http)
            print(f"[digest] Latest post: {post.title}\n[digest] URL: {post.url}\n[digest] Published: {post.published or 'unknown'}")

            if args.print_post:
                print(f"[digest] Extracted {len(post.text)} characters of text. First lines:\n")
                print("\n".join(post.text.splitlines()[:12]))
                return 0

            state = load_state(state_file)
            if not args.force and not args.dry_run and state.get("last_post_url") == post.url:
                print(f"[digest] Already reported as {state.get('issue_key')} on {state.get('reported_at')}. Nothing to do (use --force to repeat).")
                return 0

            print(f"[digest] Summarizing with {model} ...")
            summary = summarize(post, model=model)
            finding = build_finding(post, summary, project_key)
            print("[digest] Ticket to create:\n" + json.dumps(finding, indent=2, ensure_ascii=False))

            if args.dry_run:
                print("[digest] Dry run: ticket not created.")
                return 0

            api_key = os.environ.get("IDENTITYHUB_API_KEY")
            if not api_key:
                raise DigestError("IDENTITYHUB_API_KEY is not set. Create a key in IdentityHub under 'API keys' and export it.")
            created = create_ticket(finding, api_url=api_url, api_key=api_key, http=http)
            print(f"[digest] Created {created['issue_key']}: {created['issue_url']}")
            save_state(state_file, {"last_post_url": post.url, "issue_key": created["issue_key"], "reported_at": created["created_at"]})
            return 0
    except DigestError as exc:
        print(f"[digest] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
