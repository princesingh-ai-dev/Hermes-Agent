# hermes/tools/obsidian.py
import pathlib
import re
from datetime import datetime
from langchain_core.tools import tool
from hermes.tools.registry import register_tool
import hermes.core.config as config

VAULT_PATH = pathlib.Path(config.OBSIDIAN_VAULT_PATH)

@register_tool
@tool
def obsidian_read(note_name: str) -> str:
    """Read a note from the Obsidian vault."""
    matches = list(VAULT_PATH.rglob(f"{note_name}.md"))
    if not matches:
        return f"Note '{note_name}' not found."
    return matches[0].read_text(encoding="utf-8")

@register_tool
@tool
def obsidian_write(note_name: str, content: str, folder: str = "Hermes") -> str:
    """Write or update a note in the Obsidian vault."""
    target = VAULT_PATH / folder / f"{note_name}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Note saved: {target}"

@register_tool
@tool
def obsidian_append(note_name: str, text: str) -> str:
    """Append text to an existing Obsidian note."""
    # We unwrap the string response from the tool function for this helper
    try:
        matches = list(VAULT_PATH.rglob(f"{note_name}.md"))
        if not matches:
            note = ""
        else:
            note = matches[0].read_text(encoding="utf-8")
    except Exception:
        note = ""
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    updated = note + f"\n\n---\nAdded by Hermes at {timestamp}\n{text}"
    return obsidian_write(note_name, updated)

@register_tool
@tool
def obsidian_search(query: str) -> list[dict]:
    """Full-text search across the entire vault."""
    results = []
    for md_file in VAULT_PATH.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        if query.lower() in content.lower():
            results.append({"file": md_file.name, "path": str(md_file)})
    return results
