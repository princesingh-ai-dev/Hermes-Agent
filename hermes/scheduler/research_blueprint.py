"""
Autonomous Research Cron Blueprint System
==========================================
Trending implementation from the Hermes-Agent community (X.com, YouTube, Reddit).

Provides parameterized "research blueprints" — templates for autonomous, scheduled
research tasks. The agent wakes on a cron schedule, executes multi-source research,
synthesizes findings, and delivers structured reports.

Architecture:
    BlueprintRegistry  →  stores/loads blueprint definitions (SQLite)
    BlueprintRunner    →  orchestrates execution via sub-agent DAG
    ResearchBlueprint  →  dataclass defining a single blueprint
"""

import json
import sqlite3
import asyncio
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

logger = logging.getLogger("hermes.scheduler.research_blueprint")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ResearchItem:
    """A single research finding from any source."""
    title: str
    url: str
    summary: str
    relevance_score: float  # 0.0–1.0
    source: str  # e.g. "arxiv", "github", "reddit", "web"
    published: Optional[str] = None
    authors: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Content-based dedup fingerprint."""
        raw = f"{self.title.lower().strip()}|{self.url.lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class ResearchBlueprint:
    """
    A parameterized template for autonomous scheduled research.

    Attributes:
        name:               Human-readable blueprint identifier
        description:        What this blueprint does
        sources:            List of source types to scrape (arxiv, github, reddit, web)
        keywords:           Search keywords / topics
        schedule:           Cron expression (e.g. "0 2 * * *" for nightly at 2 AM)
        delivery_channel:   Where to send results (file, telegram, discord, slack, email)
        output_format:      markdown | json | html
        max_items_per_source: Cap per source to prevent runaway scraping
        enabled:            Whether this blueprint is active
        created_at:         ISO timestamp of creation
        last_run:           ISO timestamp of last execution
        run_count:          Total number of executions
    """
    name: str
    description: str
    sources: list = field(default_factory=lambda: ["web"])
    keywords: list = field(default_factory=list)
    schedule: str = "0 9 * * *"  # daily at 9 AM
    delivery_channel: str = "file"
    output_format: str = "markdown"
    max_items_per_source: int = 10
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_run: Optional[str] = None
    run_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ResearchBlueprint":
        # Filter to only known fields
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Built-in blueprint catalog
# ---------------------------------------------------------------------------

BUILTIN_BLUEPRINTS = {
    "ai-news-digest": ResearchBlueprint(
        name="ai-news-digest",
        description="Daily digest of trending AI/ML research papers and industry news",
        sources=["arxiv", "web", "reddit"],
        keywords=["artificial intelligence", "machine learning", "LLM", "transformer", "agent framework"],
        schedule="0 8 * * *",
        delivery_channel="file",
        output_format="markdown",
        max_items_per_source=10,
    ),
    "github-trending": ResearchBlueprint(
        name="github-trending",
        description="Daily report of trending GitHub repositories in AI/Python/TypeScript",
        sources=["github"],
        keywords=["python", "typescript", "ai", "agent", "llm"],
        schedule="0 9 * * *",
        delivery_channel="file",
        output_format="markdown",
        max_items_per_source=15,
    ),
    "arxiv-daily": ResearchBlueprint(
        name="arxiv-daily",
        description="Daily arXiv paper digest filtered by your research interests",
        sources=["arxiv"],
        keywords=["cs.AI", "cs.CL", "cs.LG"],
        schedule="0 7 * * *",
        delivery_channel="file",
        output_format="markdown",
        max_items_per_source=20,
    ),
    "competitor-watch": ResearchBlueprint(
        name="competitor-watch",
        description="Weekly competitive intelligence scan across web and social media",
        sources=["web", "reddit"],
        keywords=["hermes agent", "autonomous agent", "AI agent framework"],
        schedule="0 10 * * 1",  # Monday at 10 AM
        delivery_channel="file",
        output_format="markdown",
        max_items_per_source=15,
    ),
}


# ---------------------------------------------------------------------------
# Blueprint Registry (SQLite persistence)
# ---------------------------------------------------------------------------

class BlueprintRegistry:
    """
    CRUD operations for research blueprints, persisted in SQLite.

    The registry merges user-created blueprints with the built-in catalog.
    User blueprints override built-ins of the same name.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            hermes_home = Path.home() / ".hermes"
            hermes_home.mkdir(parents=True, exist_ok=True)
            db_path = str(hermes_home / "research_blueprints.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blueprints (
                    name TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    is_builtin INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blueprint_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    blueprint_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    items_found INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    report_path TEXT,
                    error_message TEXT,
                    FOREIGN KEY (blueprint_name) REFERENCES blueprints(name)
                )
            """)
            conn.commit()

    def register_builtins(self):
        """Seed the database with built-in blueprints (won't overwrite user edits)."""
        with sqlite3.connect(self.db_path) as conn:
            for name, bp in BUILTIN_BLUEPRINTS.items():
                existing = conn.execute(
                    "SELECT is_builtin FROM blueprints WHERE name = ?", (name,)
                ).fetchone()
                if existing is None:
                    conn.execute(
                        "INSERT INTO blueprints (name, data, is_builtin) VALUES (?, ?, 1)",
                        (name, json.dumps(bp.to_dict())),
                    )
            conn.commit()

    def save(self, blueprint: ResearchBlueprint) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO blueprints (name, data, is_builtin, updated_at)
                   VALUES (?, ?, 0, ?)""",
                (blueprint.name, json.dumps(blueprint.to_dict()),
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def get(self, name: str) -> Optional[ResearchBlueprint]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data FROM blueprints WHERE name = ?", (name,)
            ).fetchone()
        if row:
            return ResearchBlueprint.from_dict(json.loads(row[0]))
        return None

    def list_all(self, enabled_only: bool = False) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT data FROM blueprints").fetchall()
        blueprints = [ResearchBlueprint.from_dict(json.loads(r[0])) for r in rows]
        if enabled_only:
            blueprints = [bp for bp in blueprints if bp.enabled]
        return blueprints

    def delete(self, name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM blueprints WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0

    def record_run(self, blueprint_name: str, items_found: int,
                   status: str = "completed", report_path: str = None,
                   error_message: str = None) -> int:
        """Record a blueprint execution in the run history."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO blueprint_runs
                   (blueprint_name, started_at, completed_at, items_found, status, report_path, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (blueprint_name, now, now, items_found, status, report_path, error_message),
            )
            lastrowid = cursor.lastrowid
            conn.commit()

        # Update the blueprint's last_run and run_count outside of the lock
        bp = self.get(blueprint_name)
        if bp:
            bp.last_run = now
            bp.run_count += 1
            self.save(bp)
            
        return lastrowid

    def get_run_history(self, blueprint_name: str, limit: int = 10) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, blueprint_name, started_at, completed_at,
                          items_found, status, report_path, error_message
                   FROM blueprint_runs
                   WHERE blueprint_name = ?
                   ORDER BY id DESC LIMIT ?""",
                (blueprint_name, limit),
            ).fetchall()
        return [
            {
                "id": r[0], "blueprint_name": r[1], "started_at": r[2],
                "completed_at": r[3], "items_found": r[4], "status": r[5],
                "report_path": r[6], "error_message": r[7],
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Blueprint Runner (orchestrates execution)
# ---------------------------------------------------------------------------

class BlueprintRunner:
    """
    Executes a research blueprint by:
    1. Dispatching scrapers per source (parallel via asyncio)
    2. Deduplicating results
    3. Scoring relevance against keywords
    4. Rendering the digest in the requested format
    5. Recording the run in the registry
    """

    def __init__(self, registry: BlueprintRegistry):
        self.registry = registry
        # Lazy import to avoid circular deps
        self._scrapers = {}

    def _get_scraper(self, source: str):
        """Get the scraper for a given source type."""
        from hermes.scheduler.source_scrapers import (
            ArxivScraper, GitHubTrendingScraper, RedditScraper, WebSearchScraper,
        )
        scraper_map = {
            "arxiv": ArxivScraper,
            "github": GitHubTrendingScraper,
            "reddit": RedditScraper,
            "web": WebSearchScraper,
        }
        if source not in self._scrapers:
            cls = scraper_map.get(source)
            if cls:
                self._scrapers[source] = cls()
        return self._scrapers.get(source)

    async def _scrape_source(self, source: str, keywords: list,
                              max_items: int) -> list:
        """Scrape a single source (async-safe)."""
        scraper = self._get_scraper(source)
        if scraper is None:
            logger.warning(f"No scraper for source: {source}")
            return []
        try:
            items = await asyncio.wait_for(
                asyncio.to_thread(scraper.scrape, keywords, max_items),
                timeout=60,
            )
            return items
        except asyncio.TimeoutError:
            logger.error(f"Timeout scraping {source}")
            return []
        except Exception as e:
            logger.error(f"Error scraping {source}: {e}")
            return []

    def _deduplicate(self, items: list) -> list:
        """Remove duplicate items based on content fingerprint."""
        seen = set()
        unique = []
        for item in items:
            fp = item.fingerprint
            if fp not in seen:
                seen.add(fp)
                unique.append(item)
        return unique

    def _score_relevance(self, items: list, keywords: list) -> list:
        """Boost relevance scores based on keyword matches."""
        kw_lower = [k.lower() for k in keywords]
        for item in items:
            text = f"{item.title} {item.summary}".lower()
            matches = sum(1 for kw in kw_lower if kw in text)
            keyword_boost = min(matches / max(len(kw_lower), 1), 1.0)
            item.relevance_score = round(
                0.5 * item.relevance_score + 0.5 * keyword_boost, 3
            )
        items.sort(key=lambda x: x.relevance_score, reverse=True)
        return items

    async def execute(self, blueprint: ResearchBlueprint) -> dict:
        """
        Execute a research blueprint end-to-end.

        Returns:
            dict with keys: items, report_text, report_path, status
        """
        logger.info(f"Executing blueprint: {blueprint.name}")
        start_time = datetime.now(timezone.utc)

        # 1. Scrape all sources in parallel
        tasks = [
            self._scrape_source(source, blueprint.keywords,
                                 blueprint.max_items_per_source)
            for source in blueprint.sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 2. Flatten + handle errors
        all_items = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Scraper error: {result}")
            elif isinstance(result, list):
                all_items.extend(result)

        # 3. Deduplicate
        unique_items = self._deduplicate(all_items)

        # 4. Score relevance
        scored_items = self._score_relevance(unique_items, blueprint.keywords)

        # 5. Render digest
        from hermes.scheduler.digest_renderer import DigestRenderer
        renderer = DigestRenderer()
        report_text = renderer.render(
            blueprint=blueprint,
            items=scored_items,
            output_format=blueprint.output_format,
            execution_time=start_time.isoformat(),
        )

        # 6. Save report to file
        report_dir = Path.home() / ".hermes" / "research_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        ext = {"markdown": "md", "json": "json", "html": "html"}.get(
            blueprint.output_format, "md"
        )
        report_filename = f"{blueprint.name}_{start_time.strftime('%Y%m%d_%H%M%S')}.{ext}"
        report_path = report_dir / report_filename
        report_path.write_text(report_text, encoding="utf-8")

        # 7. Record run in registry
        self.registry.record_run(
            blueprint_name=blueprint.name,
            items_found=len(scored_items),
            status="completed",
            report_path=str(report_path),
        )

        logger.info(
            f"Blueprint '{blueprint.name}' completed: "
            f"{len(scored_items)} items, report at {report_path}"
        )

        return {
            "items": scored_items,
            "report_text": report_text,
            "report_path": str(report_path),
            "status": "completed",
            "items_found": len(scored_items),
        }

    def execute_sync(self, blueprint: ResearchBlueprint) -> dict:
        """Synchronous wrapper for execute()."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.execute(blueprint))
                return future.result(timeout=300)
        else:
            return asyncio.run(self.execute(blueprint))
