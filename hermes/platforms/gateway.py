import asyncio
from typing import Callable, Any, Coroutine

class PlatformGateway:
    """
    Unified platform gateway.
    A single gateway process serving ALL platforms simultaneously.
    """
    def __init__(self, agent_runner: Callable[[str, str, str], Coroutine[Any, Any, str]]):
        # agent_runner takes (message, platform, user_id) and returns a response string
        self.agent_runner = agent_runner
        self.platforms = []

    def register_platform(self, platform: Any):
        """Register a platform adapter (e.g. TelegramBot, DiscordBot)"""
        self.platforms.append(platform)

    async def handle_message(self, platform_id: str, user_id: str, message: str) -> str:
        """
        Central message handler.
        All platforms route their incoming messages through this single function.
        """
        print(f"[{platform_id}] Message from {user_id}: {message}")
        try:
            # Delegate to the LangGraph core
            response = await self.agent_runner(message, platform_id, user_id)
            return response
        except Exception as e:
            return f"Error processing message: {str(e)}"

    async def broadcast(self, message: str):
        """
        Send a message to all active platforms.
        Used by the Scheduled Automations (cron jobs) to deliver async results.
        """
        print(f"[BROADCAST] {message}")
        for platform in self.platforms:
            if hasattr(platform, 'broadcast'):
                await platform.broadcast(message)

    async def start_all(self):
        """Start polling/listening on all registered platforms asynchronously"""
        tasks = []
        for platform in self.platforms:
            if hasattr(platform, 'start'):
                tasks.append(asyncio.create_task(platform.start()))
        
        if tasks:
            await asyncio.gather(*tasks)
