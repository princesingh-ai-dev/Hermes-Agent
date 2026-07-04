"""
Skill Curator Lifecycle Manager
===============================
Prevents "skill bloat" in Hermes by checking usage metrics, identifying duplicates,
generating consolidation/pruning suggestions, and managing auto-archival to
~/.hermes/skills/.archive/
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
import json

from hermes.skills.curator_metrics import SkillMetricsStore

logger = logging.getLogger("hermes.skills.curator")

class SkillCurator:
    """
    Evaluates skill catalog files periodically. Identifies stale or near-duplicate
    skills, archives them safely, and writes a REPORT.md mapping the curator's decisions.
    """
    def __init__(self, skills_dir: Optional[Path] = None, metrics_store: Optional[SkillMetricsStore] = None):
        if skills_dir is None:
            self.skills_dir = Path.home() / ".hermes" / "skills"
        else:
            self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        self.archive_dir = self.skills_dir / ".archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        self.metrics_store = metrics_store or SkillMetricsStore()

    def get_all_skills(self) -> List[Path]:
        """Find all custom skill folders (any subdirectory under skills_dir that is not .archive)."""
        skills = []
        for p in self.skills_dir.iterdir():
            if p.is_dir() and p.name != ".archive" and not p.name.startswith("."):
                # Must contain a SKILL.md file
                if (p / "SKILL.md").exists():
                    skills.append(p)
        return skills

    def evaluate_skill(self, skill_path: Path) -> Dict:
        """Evaluate a skill based on metadata and metrics store."""
        skill_name = skill_path.name
        metrics = self.metrics_store.get_metrics(skill_name)
        
        # Check file timestamps
        skill_md = skill_path / "SKILL.md"
        mtime = datetime.fromtimestamp(skill_md.stat().st_mtime, tz=timezone.utc)
        
        # Determine status
        last_activity = mtime
        if metrics["last_used_at"]:
            last_activity = max(last_activity, datetime.fromisoformat(metrics["last_used_at"]))
            
        now = datetime.now(timezone.utc)
        days_inactive = (now - last_activity).days

        status = "Active"
        if not metrics["pinned"]:
            if days_inactive >= 90:
                status = "Archive"
            elif days_inactive >= 30:
                status = "Stale"

        return {
            "name": skill_name,
            "path": str(skill_path),
            "status": status,
            "days_inactive": days_inactive,
            "pinned": metrics["pinned"],
            "use_count": metrics["use_count"],
            "view_count": metrics["view_count"],
            "patch_count": metrics["patch_count"],
            "last_activity": last_activity.isoformat()
        }

    def archive_skill(self, skill_name: str) -> bool:
        """Safely move a skill directory into the .archive folder."""
        src = self.skills_dir / skill_name
        dest = self.archive_dir / skill_name
        if not src.exists() or not src.is_dir():
            logger.warning(f"Cannot archive non-existent skill: {skill_name}")
            return False
        
        try:
            # Overwrite if exists in archive
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(src), str(dest))
            logger.info(f"Archived skill: {skill_name}")
            return True
        except Exception as e:
            logger.error(f"Error archiving skill {skill_name}: {e}")
            return False

    def restore_skill(self, skill_name: str) -> bool:
        """Move a skill from the archive directory back to active skills."""
        src = self.archive_dir / skill_name
        dest = self.skills_dir / skill_name
        if not src.exists() or not src.is_dir():
            logger.warning(f"Cannot restore non-existent archived skill: {skill_name}")
            return False

        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(src), str(dest))
            logger.info(f"Restored skill: {skill_name}")
            return True
        except Exception as e:
            logger.error(f"Error restoring skill {skill_name}: {e}")
            return False

    def list_archived_skills(self) -> List[str]:
        """List names of currently archived skills."""
        archived = []
        if self.archive_dir.exists():
            for p in self.archive_dir.iterdir():
                if p.is_dir() and (p / "SKILL.md").exists():
                    archived.append(p.name)
        return archived

    def find_duplicate_skills(self) -> List[Tuple[str, str, float]]:
        """
        Simplistic word-frequency/lexical overlap similarity between skill files
        to detect near-duplicates. Returns list of (skill1, skill2, similarity_score).
        """
        skills = self.get_all_skills()
        skill_texts = {}
        for s in skills:
            skill_md = s / "SKILL.md"
            try:
                content = skill_md.read_text(encoding="utf-8").lower()
                # Clean punctuation
                content_clean = "".join(c if c.isalnum() or c.isspace() else " " for c in content)
                # Extract words
                words = set(w for w in content_clean.split() if len(w) > 3)
                skill_texts[s.name] = words
            except Exception:
                continue

        duplicates = []
        checked = set()
        for name1, words1 in skill_texts.items():
            for name2, words2 in skill_texts.items():
                if name1 == name2 or (name2, name1) in checked:
                    continue
                checked.add((name1, name2))
                
                if not words1 or not words2:
                    continue
                
                intersection = words1.intersection(words2)
                union = words1.union(words2)
                similarity = len(intersection) / len(union)
                
                if similarity >= 0.65:  # High overlap threshold
                    duplicates.append((name1, name2, similarity))
        
        return duplicates

    def run_curator_pass(self, dry_run: bool = False) -> Dict:
        """
        Evaluates active skills, auto-archives those marked for archival,
        detects near-duplicates, and outputs a REPORT.md.
        """
        skills = self.get_all_skills()
        evaluations = []
        archived_count = 0

        for s in skills:
            eval_data = self.evaluate_skill(s)
            evaluations.append(eval_data)
            
            if eval_data["status"] == "Archive":
                if not dry_run:
                    if self.archive_skill(eval_data["name"]):
                        archived_count += 1
                        eval_data["status"] = "Archived"

        duplicates = self.find_duplicate_skills()

        # Write curator pass report to REPORT.md
        report_path = self.skills_dir / "REPORT.md"
        if not dry_run:
            self._write_report(report_path, evaluations, duplicates)

        return {
            "evaluations": evaluations,
            "archived_count": archived_count,
            "duplicates": duplicates,
            "report_path": str(report_path) if not dry_run else None
        }

    def _write_report(self, report_path: Path, evaluations: List[Dict], duplicates: List[Tuple[str, str, float]]):
        now = datetime.now(timezone.utc).isoformat()
        lines = [
            "# 🧹 Skill Curator Passes Report",
            f"**Last pass executed:** {now}",
            "",
            "## 📊 Skill Lifecycle Status",
            "",
            "| Skill Name | Status | Use Count | Days Inactive | Pinned? |",
            "|---|---|---|---|---|",
        ]
        
        for ev in evaluations:
            pinned_str = "📌 Yes" if ev["pinned"] else "No"
            lines.append(f"| `{ev['name']}` | {ev['status']} | {ev['use_count']} | {ev['days_inactive']} | {pinned_str} |")

        lines.append("")
        lines.append("## 🔍 Near-Duplicate / Consolidation Suggestions")
        lines.append("")

        if duplicates:
            lines.append("| Skill A | Skill B | Word Overlap % | Recommendation |")
            lines.append("|---|---|---|---|")
            for sa, sb, sim in duplicates:
                lines.append(f"| `{sa}` | `{sb}` | {sim:.1%} | ⚠️ Merge files into single modular skill |")
        else:
            lines.append("*No near-duplicate skills detected.*")

        lines.append("\n---")
        lines.append("*Report generated autonomously by Hermes Skill Curator*")

        report_path.write_text("\n".join(lines), encoding="utf-8")
