import os
from typing import List, Dict
from hermes.memory.sqlite_store import LearningLoop

class SkillManager:
    """
    Manages skills for the Hermes agent.
    Combines FTS5 SQLite storage with optional file-based markdown export.
    """
    def __init__(self, db_path: str = "hermes_learning.db"):
        self.loop = LearningLoop(db_path)
        self.skills_dir = "skills/"
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir, exist_ok=True)

    def get_relevant_skills(self, query: str) -> List[Dict]:
        return self.loop.get_relevant_skills(query)

    def export_skill_to_markdown(self, skill: Dict):
        """Export a skill to the skills/ directory as a Markdown file."""
        filename = f"{self.skills_dir}{skill['name']}.md"
        content = f"# Skill: {skill['name']}\n\n"
        content += f"## Description\n{skill['description']}\n\n"
        content += f"## Instructions\n{skill['instructions']}\n\n"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

# Global instance
skill_manager = SkillManager()
