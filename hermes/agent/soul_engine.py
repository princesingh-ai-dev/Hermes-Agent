"""
SOUL.md Personality Engine
==========================
Trending implementation from the Hermes-Agent community.

Allows users to switch between different agent personalities/personas via SOUL profiles
without conversation restarts. Structured persona definitions are saved as YAML/JSON
under ~/.hermes/souls/
"""

import os
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger("hermes.agent.soul_engine")

@dataclass
class SoulProfile:
    """
    Structured representation of a Hermes agent's persona.
    """
    name: str
    role: str
    tone: str
    communication_style: str
    guardrails: List[str] = field(default_factory=list)
    expertise_areas: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "tone": self.tone,
            "communication_style": self.communication_style,
            "guardrails": self.guardrails,
            "expertise_areas": self.expertise_areas
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SoulProfile":
        return cls(
            name=data.get("name", "default"),
            role=data.get("role", "General Assistant"),
            tone=data.get("tone", "helpful, professional"),
            communication_style=data.get("communication_style", "clear, structured"),
            guardrails=data.get("guardrails", []),
            expertise_areas=data.get("expertise_areas", [])
        )


class SoulEngine:
    """
    Manages loading, registering, and switching active SOUL profiles.
    Generates structured prompt segments to insert into system messages.
    """
    def __init__(self, souls_dir: Optional[Path] = None):
        if souls_dir is None:
            self.souls_dir = Path.home() / ".hermes" / "souls"
        else:
            self.souls_dir = Path(souls_dir)
        self.souls_dir.mkdir(parents=True, exist_ok=True)
        self.active_profile_name = "default"
        self._load_builtins()

    def _load_builtins(self):
        """Seed default and built-in profiles if directory is empty."""
        builtins = {
            "default": SoulProfile(
                name="default",
                role="General Assistant",
                tone="Helpful, balanced, and direct",
                communication_style="Clear, concise, and structured",
                guardrails=[
                    "Never hallucinate facts or library APIs",
                    "Acknowledge knowledge limits honestly"
                ],
                expertise_areas=["general reasoning", "problem solving", "explanations"]
            ),
            "coding-mentor": SoulProfile(
                name="coding-mentor",
                role="Patient Software Engineering Educator",
                tone="Encouraging, educational, and thorough",
                communication_style="Explain reasoning step-by-step, use code blocks with inline comments",
                guardrails=[
                    "Avoid writing code without explaining the architectural context",
                    "Highlight potential pitfalls, edge cases, and safety trade-offs in solutions"
                ],
                expertise_areas=["software architecture", "refactoring", "debugging", "best practices"]
            ),
            "devops-operator": SoulProfile(
                name="devops-operator",
                role="DevOps & Infrastructure Operator",
                tone="Terse, action-oriented, and highly technical",
                communication_style="Provide direct scripts/commands, minimize conversational filler",
                guardrails=[
                    "Always warn the user before destructive commands",
                    "Do not suggest changes that violate secure credential storage principles"
                ],
                expertise_areas=["bash scripting", "docker", "ci/cd pipelines", "system diagnostics"]
            ),
            "research-analyst": SoulProfile(
                name="research-analyst",
                role="Thorough Research Analyst",
                tone="Analytical, academic, and citation-heavy",
                communication_style="Structure with clear headings, bullet points, and explicit citations/links",
                guardrails=[
                    "Distinguish clearly between factual references and speculative conclusions",
                    "Acknowledge the date/recency of cited information"
                ],
                expertise_areas=["literature search", "data synthesis", "comparative analysis"]
            ),
            "security-auditor": SoulProfile(
                name="security-auditor",
                role="Paranoid Application Security Auditor",
                tone="Objective, critical, and defense-in-depth oriented",
                communication_style="Present findings as structured threat assessments, checklists, and CVSS scores",
                guardrails=[
                    "Never assume code is safe; identify vulnerability vectors proactively",
                    "Provide secure alternatives for any unsafe patterns flagged"
                ],
                expertise_areas=["code auditing", "vulnerability analysis", "threat modeling"]
            )
        }

        for name, profile in builtins.items():
            profile_path = self.souls_dir / f"{name}.json"
            if not profile_path.exists():
                profile_path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")

    def list_profiles(self) -> List[str]:
        """List all available soul profile names."""
        profiles = []
        for p in self.souls_dir.iterdir():
            if p.suffix == ".json" and not p.name.startswith("."):
                profiles.append(p.stem)
        return sorted(profiles)

    def load_profile(self, name: str) -> SoulProfile:
        """Load a profile from json file."""
        profile_path = self.souls_dir / f"{name}.json"
        if not profile_path.exists():
            # Fallback to default
            profile_path = self.souls_dir / "default.json"
            name = "default"

        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            profile = SoulProfile.from_dict(data)
            self.active_profile_name = name
            return profile
        except Exception as e:
            logger.error(f"Error loading SOUL profile '{name}': {e}")
            # In-memory default fallback
            return SoulProfile(
                name="default",
                role="General Assistant",
                tone="Helpful",
                communication_style="Clear"
            )

    def save_custom_profile(self, profile: SoulProfile) -> None:
        """Save a new custom profile to the souls directory."""
        profile_path = self.souls_dir / f"{profile.name}.json"
        profile_path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")

    def render_soul_prompt(self, name: Optional[str] = None) -> str:
        """
        Generates system prompt segment corresponding to the loaded SOUL persona.
        """
        profile_name = name or self.active_profile_name
        profile = self.load_profile(profile_name)

        guardrails_str = "\n".join(f"- {g}" for g in profile.guardrails)
        expertise_str = ", ".join(profile.expertise_areas)

        prompt = (
            f"=== AGENT SOUL PERSONALITY ACTIVE: {profile.name.upper()} ===\n"
            f"Role: {profile.role}\n"
            f"Tone: {profile.tone}\n"
            f"Communication Style: {profile.communication_style}\n"
        )
        if profile.expertise_areas:
            prompt += f"Expertise Areas: {expertise_str}\n"
        if profile.guardrails:
            prompt += f"Core Behavioral Guardrails:\n{guardrails_str}\n"
            
        prompt += "=================================================="
        return prompt
