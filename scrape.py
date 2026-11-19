"""Step 1: fetch a page and turn it into clean text.

Plain HTTP requests (cheap); no headless browser. Menus, footers, scripts and cookie banners are
stripped before anything reaches the model. A failed fetch is reported as a failure with a reason,
never as an empty page, so "couldn't read the site" is never mistaken for "poor fit".
"""
import re
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config

# Which links to follow for which question (the "where it lives" column of the evidence map).
PAGE_HINTS = {
    "about": ["about", "company", "our-story", "who-we-are", "team", "leadership"],
    "security": ["security", "trust", "compliance", "privacy", "soc"],
    "customers": ["customers", "case-studies", "case-study", "testimonials", "stories", "enterprise"],
    "careers": ["careers", "jobs", "join", "hiring", "work-with-us"],
    "pricing": ["pricing", "plans"],
    "press": ["press", "news", "blog/funding", "newsroom", "media"],
}

_robots = {}


def _allowed(url):
    root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if root not in _robots:
        rp = robotparser.RobotFileParser()
        try:
            r = requests.get(root + "/robots.txt", headers={"User-Agent": config.USER_AGENT}, timeout=config.TIMEOUT_S)
            rp.parse(r.text.splitlines() if r.ok else [])
        except requests.RequestException:
            rp.parse([])
        _robots[root] = rp
    return _robots[root].can_fetch(config.USER_AGENT, url)


def _clean(soup):
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"]):
        tag.decompose()
    for el in soup.select('[class*="cookie"], [id*="cookie"], [class*="banner"], [aria-hidden="true"]'):
        el.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)[: config.MAX_PAGE_CHARS]


def fetch(url):
    """Returns {"url", "ok", "reason", "title", "text", "links"}. Never raises for network problems."""
    if not url.startswith("http"):
        url = "https://" + url
    page = {"url": url, "ok": False, "reason": "", "title": "", "text": "", "links": []}
    if not _allowed(url):
        page["reason"] = "blocked by robots.txt"
        return page
    try:
        r = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=config.TIMEOUT_S)
    except requests.exceptions.SSLError:
        page["reason"] = "the site's secure connection (HTTPS certificate) failed"
        return page
    except requests.exceptions.Timeout:
        page["reason"] = f"the site didn't respond within {config.TIMEOUT_S} s"
        return page
    except requests.exceptions.ConnectionError as e:
        dns = any(s in str(e) for s in ("NameResolution", "getaddrinfo", "Name or service not known", "nodename nor servname"))
        page["reason"] = "this domain doesn't exist or has no website (check the spelling)" if dns \
            else "couldn't connect to the site"
        return page
    except requests.RequestException as e:
        page["reason"] = f"network error: {type(e).__name__}"
        return page
    if r.status_code >= 400:
        page["reason"] = f"HTTP {r.status_code}"
        return page
    soup = BeautifulSoup(r.text, "html.parser")
    page["title"] = (soup.title.string or "").strip() if soup.title else ""
    base = urlparse(r.url).netloc
    for a in soup.find_all("a", href=True):  # collect links before cleaning removes the nav
        href = urljoin(r.url, a["href"]).split("#")[0]
        if urlparse(href).netloc.endswith(base.replace("www.", "")):
            page["links"].append((a.get_text(" ", strip=True)[:60], href))
    page["text"] = _clean(soup)
    page["url"] = r.url
    if len(page["text"]) < 200:
        page["reason"] = ("page has almost no readable text: a placeholder or parked page, "
                          "or a site built entirely with JavaScript")
        return page
    page["ok"] = True
    return page


def find_link(home, kind, exclude=()):
    """Best on-site link for a kind of page ("about", "security", ...), or a guessed path."""
    hints = PAGE_HINTS[kind]
    done = {e.rstrip("/") for e in exclude}
    # Hints are in priority order ("security" before "privacy"). A link matches on its first path
    # segment, or on its text when the text is a short label like "About us" (not a sentence).
    for h in hints:
        for text, href in home.get("links", []):
            first = urlparse(href).path.lower().strip("/").split("/")[0]
            words = re.findall(r"[a-z]+", text.lower())
            if (first == h or first.startswith(h + "-") or (len(words) <= 3 and h in words)) \
                    and href.rstrip("/") not in done:
                return href
    root = f"{urlparse(home['url']).scheme}://{urlparse(home['url']).netloc}"
    for h in hints[:2]:
        guess = f"{root}/{h}"
        if guess not in exclude:
            return guess
    return None
