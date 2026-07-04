"""
Multi-Source Research Scrapers
===============================
Scrapers for the Autonomous Research Blueprint system.

Each scraper implements a common interface:
    scraper.scrape(keywords: list, max_items: int) -> list[ResearchItem]

Sources: arXiv, GitHub Trending, Reddit, General Web Search.
All scrapers are designed for graceful degradation — if a source is
unreachable, they return an empty list rather than raising.
"""

import re
import json
import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

from hermes.scheduler.research_blueprint import ResearchItem

logger = logging.getLogger("hermes.scheduler.source_scrapers")


# ---------------------------------------------------------------------------
# Base scraper
# ---------------------------------------------------------------------------

class BaseScraper:
    """Base class for all research scrapers."""

    source_name: str = "unknown"

    def scrape(self, keywords: list, max_items: int = 10) -> list:
        """
        Scrape the source for items matching keywords.
        Returns a list of ResearchItem objects.
        """
        raise NotImplementedError

    def _safe_request(self, url: str, timeout: int = 30,
                      headers: Optional[dict] = None) -> Optional[str]:
        """Make an HTTP GET request with error handling."""
        try:
            req = urllib.request.Request(url)
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            req.add_header("User-Agent", "HermesAgent/1.0 Research Blueprint")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"[{self.source_name}] Request failed for {url}: {e}")
            return None


# ---------------------------------------------------------------------------
# arXiv Scraper
# ---------------------------------------------------------------------------

class ArxivScraper(BaseScraper):
    """
    Fetches recent papers from arXiv's Atom API.

    Supports:
        - Keyword search across title, abstract, authors
        - Category filtering (e.g. cs.AI, cs.CL, cs.LG)
        - Sorted by submission date (newest first)
    """

    source_name = "arxiv"
    BASE_URL = "http://export.arxiv.org/api/query"

    def scrape(self, keywords: list, max_items: int = 10) -> list:
        # Separate category keywords from regular keywords
        categories = [kw for kw in keywords if re.match(r'^[a-z]+\.[A-Z]{2,}$', kw)]
        search_terms = [kw for kw in keywords if kw not in categories]

        # Build query
        parts = []
        if search_terms:
            terms_query = "+OR+".join(
                f'all:"{urllib.parse.quote(t)}"' for t in search_terms
            )
            parts.append(f"({terms_query})")
        if categories:
            cat_query = "+OR+".join(f"cat:{c}" for c in categories)
            parts.append(f"({cat_query})")

        query = "+AND+".join(parts) if parts else "all:artificial+intelligence"

        url = (
            f"{self.BASE_URL}?search_query={query}"
            f"&start=0&max_results={max_items}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )

        xml_text = self._safe_request(url)
        if not xml_text:
            return []

        return self._parse_atom(xml_text, max_items)

    def _parse_atom(self, xml_text: str, max_items: int) -> list:
        items = []
        try:
            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns)[:max_items]:
                title_el = entry.find("atom:title", ns)
                summary_el = entry.find("atom:summary", ns)
                link_el = entry.find("atom:id", ns)
                published_el = entry.find("atom:published", ns)

                authors = []
                for author_el in entry.findall("atom:author", ns):
                    name_el = author_el.find("atom:name", ns)
                    if name_el is not None and name_el.text:
                        authors.append(name_el.text.strip())

                title = title_el.text.strip() if title_el is not None and title_el.text else "Untitled"
                summary = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
                url = link_el.text.strip() if link_el is not None and link_el.text else ""
                published = published_el.text.strip() if published_el is not None and published_el.text else None

                # Clean up whitespace in title/summary
                title = re.sub(r'\s+', ' ', title)
                summary = re.sub(r'\s+', ' ', summary)
                if len(summary) > 500:
                    summary = summary[:497] + "..."

                items.append(ResearchItem(
                    title=title,
                    url=url,
                    summary=summary,
                    relevance_score=0.7,  # Base score for arXiv
                    source="arxiv",
                    published=published,
                    authors=", ".join(authors[:5]),
                    metadata={"categories": [
                        cat.attrib.get("term", "")
                        for cat in entry.findall("{http://arxiv.org/schemas/atom}category")
                    ]},
                ))
        except ET.ParseError as e:
            logger.error(f"[arxiv] XML parse error: {e}")

        return items


# ---------------------------------------------------------------------------
# GitHub Trending Scraper
# ---------------------------------------------------------------------------

class GitHubTrendingScraper(BaseScraper):
    """
    Fetches trending repositories from GitHub's search API.

    Uses the GitHub Search API (unauthenticated, rate-limited to 10 req/min)
    to find recently created/updated repos sorted by stars.
    """

    source_name = "github"
    SEARCH_URL = "https://api.github.com/search/repositories"

    def scrape(self, keywords: list, max_items: int = 10) -> list:
        query_parts = keywords if keywords else ["artificial intelligence"]
        query_str = " ".join(query_parts)

        # Search for repos created in the last 7 days, sorted by stars
        params = urllib.parse.urlencode({
            "q": f"{query_str} created:>2026-01-01",
            "sort": "stars",
            "order": "desc",
            "per_page": min(max_items, 30),
        })
        url = f"{self.SEARCH_URL}?{params}"

        response = self._safe_request(url, headers={
            "Accept": "application/vnd.github+json",
        })
        if not response:
            return []

        return self._parse_response(response, max_items)

    def _parse_response(self, response: str, max_items: int) -> list:
        items = []
        try:
            data = json.loads(response)
            for repo in data.get("items", [])[:max_items]:
                name = repo.get("full_name", "unknown/unknown")
                description = repo.get("description", "") or ""
                stars = repo.get("stargazers_count", 0)
                language = repo.get("language", "")
                url = repo.get("html_url", "")
                created = repo.get("created_at", "")
                topics = repo.get("topics", [])

                summary = f"{description}\n⭐ {stars:,} stars | 📝 {language}"
                if topics:
                    summary += f" | Tags: {', '.join(topics[:5])}"

                # Score based on stars
                star_score = min(stars / 1000, 1.0) if stars else 0.0

                items.append(ResearchItem(
                    title=name,
                    url=url,
                    summary=summary,
                    relevance_score=round(0.5 + 0.5 * star_score, 3),
                    source="github",
                    published=created,
                    metadata={"stars": stars, "language": language, "topics": topics},
                ))
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[github] Parse error: {e}")

        return items


# ---------------------------------------------------------------------------
# Reddit Scraper
# ---------------------------------------------------------------------------

class RedditScraper(BaseScraper):
    """
    Fetches top posts from Reddit using the public JSON API.

    Scrapes specified subreddits (or r/all) filtered by keywords,
    sorted by "hot" or "top" (past week).
    """

    source_name = "reddit"
    DEFAULT_SUBREDDITS = ["MachineLearning", "artificial", "LocalLLaMA", "hermesagent"]

    def scrape(self, keywords: list, max_items: int = 10) -> list:
        items = []
        per_sub = max(max_items // len(self.DEFAULT_SUBREDDITS), 3)

        for subreddit in self.DEFAULT_SUBREDDITS:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={per_sub}"
            response = self._safe_request(url, headers={
                "Accept": "application/json",
            })
            if not response:
                continue

            try:
                data = json.loads(response)
                for post in data.get("data", {}).get("children", []):
                    pdata = post.get("data", {})
                    title = pdata.get("title", "")
                    selftext = pdata.get("selftext", "")[:300]
                    permalink = pdata.get("permalink", "")
                    score = pdata.get("score", 0)
                    created_utc = pdata.get("created_utc", 0)
                    num_comments = pdata.get("num_comments", 0)

                    # Keyword filter
                    text = f"{title} {selftext}".lower()
                    kw_lower = [k.lower() for k in keywords]
                    if keywords and not any(kw in text for kw in kw_lower):
                        continue

                    post_url = f"https://www.reddit.com{permalink}"
                    summary = selftext if selftext else f"Score: {score} | {num_comments} comments"

                    score_normalized = min(score / 500, 1.0) if score > 0 else 0.0

                    items.append(ResearchItem(
                        title=f"[r/{subreddit}] {title}",
                        url=post_url,
                        summary=summary[:400],
                        relevance_score=round(0.4 + 0.6 * score_normalized, 3),
                        source="reddit",
                        published=datetime.fromtimestamp(
                            created_utc, tz=timezone.utc
                        ).isoformat() if created_utc else None,
                        metadata={"subreddit": subreddit, "score": score,
                                  "num_comments": num_comments},
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"[reddit] Parse error for r/{subreddit}: {e}")

        return items[:max_items]


# ---------------------------------------------------------------------------
# Web Search Scraper
# ---------------------------------------------------------------------------

class WebSearchScraper(BaseScraper):
    """
    General web search aggregator.

    Uses a simple approach — builds search queries from keywords and
    attempts to fetch results. Designed as a fallback when specialized
    scrapers are unavailable.
    """

    source_name = "web"

    def scrape(self, keywords: list, max_items: int = 10) -> list:
        """
        Performs web search aggregation.

        In production, this would integrate with the agent's web_search tool.
        For standalone operation, it generates structured placeholders that
        can be enriched by the agent's existing search infrastructure.
        """
        items = []
        query = " ".join(keywords) if keywords else "AI agent news"

        # Create structured search tasks for the agent to execute
        search_variations = [
            f"{query} latest news {datetime.now().strftime('%B %Y')}",
            f"{query} trending developments",
            f"{query} new releases announcements",
        ]

        for i, search_query in enumerate(search_variations[:max_items]):
            items.append(ResearchItem(
                title=f"Web Search: {search_query}",
                url=f"https://www.google.com/search?q={urllib.parse.quote(search_query)}",
                summary=f"Pending web search for: {search_query}. "
                        f"Execute via agent's web_search tool for live results.",
                relevance_score=0.5,
                source="web",
                metadata={"query": search_query, "requires_agent": True},
            ))

        return items[:max_items]
