from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from typing import Optional

class AutomationEngine:
    """
    Built-in cron scheduler with natural language task definitions.
    Users can say: "Every morning at 8 AM, check my email and summarize important ones"
    --> Hermes creates a scheduled automation automatically.
    """
    def __init__(self, agent_runner=None):
        self.scheduler = AsyncIOScheduler()
        self.agent_runner = agent_runner

    def start(self):
        """Start the scheduler (must be called inside an event loop)."""
        self.scheduler.start()

    async def create_automation(self, natural_language: str, task: str,
                                cron_expression: Optional[str] = None):
        """
        Parse natural language schedule and create a cron job.
        Examples:
        - "every day at 8am" -> "0 8 * * *"
        - "every Monday at 9am" -> "0 9 * * 1"
        - "every hour" -> "0 * * * *"
        """
        if not cron_expression:
            cron_expression = self._nl_to_cron(natural_language)

        self.scheduler.add_job(
            self._execute_task,
            trigger=CronTrigger.from_crontab(cron_expression),
            args=[task],
            id=f"auto_{datetime.utcnow().timestamp()}",
            replace_existing=True,
        )

    def _nl_to_cron(self, text: str) -> str:
        """Convert natural language to cron expression."""
        # Simple heuristic pattern matching.
        # In a full deployment, this is handled by an LLM call.
        text = text.lower()
        if "every morning" in text or "8am" in text:
            return "0 8 * * *"
        if "every hour" in text:
            return "0 * * * *"
        if "every monday" in text:
            return "0 9 * * 1"
            
        # Default fallback: midnight every day
        return "0 0 * * *"

    async def _execute_task(self, task: str):
        """Execute the scheduled task and deliver to configured platforms."""
        if self.agent_runner:
            result = await self.agent_runner(task)
            # In a full gateway implementation, this would broadcast the result 
            # to active Telegram/Discord channels.
            print(f"[Scheduled Task Result] {result}")
