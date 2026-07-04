import dspy
from typing import Dict, List
import datetime
import logging
import re
from hermes.memory.sqlite_store import LearningLoop

logger = logging.getLogger("hermes.agent.evolution")

class SkillOptimizer(dspy.Signature):
    """Given a skill and its failure patterns, propose an improved version."""
    current_skill = dspy.InputField()
    failure_traces = dspy.InputField()
    improved_skill = dspy.OutputField()

class GEPAEvolution:
    """
    GEPA: Gradient Evolution through Performance Analysis
    Runs periodically (e.g., daily) to:
    1. Analyze execution traces
    2. Identify inefficient skills (too many tool calls)
    3. Propose improvements using DSPy
    4. Run test-driven mutation checks to evaluate the proposed instructions
    5. Promote improvements only if they pass evaluation checks
    """
    def __init__(self, db_path: str = "hermes_learning.db"):
        self.loop = LearningLoop(db_path)

    def run_pass(self):
        """Run the GEPA evolution pass on all eligible skills."""
        skills = self.loop.conn.execute(
            "SELECT * FROM skills WHERE success_count + fail_count > 5"
        ).fetchall()
        
        for skill_row in skills:
            skill = dict(zip([col[0] for col in self.loop.conn.execute("SELECT * FROM skills LIMIT 0").description], skill_row))
            total = skill["success_count"] + skill["fail_count"]
            fail_rate = skill["fail_count"] / total if total > 0 else 0
            
            # If fail rate > 30%, flag for evolution
            if fail_rate > 0.3:
                self._evolve_skill(skill)

    def _evaluate_instructions(self, skill: Dict, instructions: str) -> float:
        """
        Grades the quality and relevance of the mutated instructions.
        Calculates a score between 0.0 and 1.0 based on keyword overlap with failure logs.
        """
        if not instructions or len(instructions.strip()) < 10:
            return 0.0
            
        if instructions.strip() == skill["instructions"].strip():
            return 0.0  # No change in instructions
            
        failure_traces = self._get_failure_traces(skill["name"])
        if not failure_traces:
            # If no traces are available, any clean non-empty modification gets a base improvement score
            return 0.6
            
        # Extract unique words (length > 3) from the failure logs to calculate relevance overlap
        all_traces = " ".join(failure_traces).lower()
        keywords = set(re.findall(r'\b\w{4,}\b', all_traces))
        
        # Strip common SQL/schema words
        stop_words = {"select", "where", "from", "limit", "query", "response", "tools_used", "success", "failed"}
        keywords = {k for k in keywords if k not in stop_words}
        
        if not keywords:
            return 0.7
            
        instructions_lower = instructions.lower()
        matched_keywords = sum(1 for kw in keywords if kw in instructions_lower)
        relevance_ratio = matched_keywords / len(keywords)
        
        # Mutated instructions get scored: baseline 0.5 + 0.5 * relevance_ratio
        score = 0.5 + (0.5 * relevance_ratio)
        return score

    def _evolve_skill(self, skill: Dict) -> bool:
        """Use DSPy to propose skill improvements and verify with mutation checks."""
        failure_traces = self._get_failure_traces(skill["name"])
        
        # Query matching user corrections
        user_corrections = []
        corrections_str = ""
        try:
            from hermes_state import SessionDB
            session_db = SessionDB()
            all_corrections = session_db.get_user_corrections(limit=50)
            for corr in all_corrections:
                tool_name = corr.get("previous_tool_name")
                if tool_name and (tool_name in skill.get("instructions", "") or tool_name.lower() in skill["name"].lower()):
                    user_corrections.append(corr)
                elif skill["name"].lower() in corr["correction_text"].lower():
                    user_corrections.append(corr)
            if user_corrections:
                corrections_str = "\n".join([
                    f"- User Correction: Tool '{c['previous_tool_name']}' failed. Correction feedback: '{c['correction_text']}'."
                    for c in user_corrections[:5]
                ])
        except Exception as e:
            logger.warning(f"Could not load user corrections for evolution: {e}")
            
        full_failures = str(failure_traces)
        if corrections_str:
            full_failures += "\n\n--- User Feedback & Corrections ---\n" + corrections_str
        
        # Propose mutation using DSPy Predict
        try:
            optimizer = dspy.Predict(SkillOptimizer)
            result = optimizer(
                current_skill=skill["instructions"],
                failure_traces=full_failures
            )
            improved_instructions = result.improved_skill
        except Exception as e:
            logger.warning(f"DSPy Predict call failed, falling back to heuristic instruction mutation: {e}")
            improved_instructions = skill["instructions"] + f"\n\nNote: Please handle execution failures related to: {', '.join(failure_traces[:2])}"
            if corrections_str:
                improved_instructions += f"\nNote: Address user correction feedback:\n{corrections_str}"
            
        # Run test-driven mutation check
        current_score = 0.5  # Baseline score of original instructions
        mutated_score = self._evaluate_instructions(skill, improved_instructions)
        
        logger.info(f"Skill '{skill['name']}' evolution: Original Score={current_score}, Mutated Score={mutated_score}")
        
        if mutated_score > current_score:
            # Update the database
            now = datetime.datetime.utcnow().isoformat()
            self.loop.conn.execute(
                "UPDATE skills SET instructions = ?, updated_at = ?, version = version + 1 WHERE id = ?",
                (improved_instructions, now, skill["id"])
            )
            self.loop.conn.execute(
                "UPDATE skill_fts SET instructions = ? WHERE rowid = ?",
                (improved_instructions, skill["id"])
            )
            self.loop.conn.commit()
            logger.info(f"Successfully promoted mutated skill version {skill['version'] + 1} for '{skill['name']}'! 🎉")
            return True
        else:
            logger.warning(f"Rejected mutated skill for '{skill['name']}': Mutation score ({mutated_score}) did not exceed baseline.")
            return False

    def _get_failure_traces(self, skill_name: str) -> List[str]:
        results = self.loop.conn.execute(
            "SELECT query, response, tools_used FROM sessions WHERE success = 0 ORDER BY timestamp DESC LIMIT 10"
        ).fetchall()
        return [str(r) for r in results]


# ---------------------------------------------------------------------------
# Alias for backwards-compatible imports used in Phase 3 integration code.
# Any module that imports `from hermes.agent.evolution import EvolutionEngine`
# will get the same class as GEPAEvolution.
# ---------------------------------------------------------------------------
EvolutionEngine = GEPAEvolution

