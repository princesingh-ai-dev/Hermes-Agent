import os
import discord
import asyncio
from hermes.platforms.gateway import PlatformGateway

class DiscordBot(discord.Client):
    """Discord adapter for Hermes Gateway."""
    
    def __init__(self, gateway: PlatformGateway):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.gateway = gateway
        self.token = os.getenv("DISCORD_BOT_TOKEN")
        self.active_channels = set()

    async def start(self, *args, **kwargs):
        """Override start to safely handle missing token."""
        if not self.token or self.token.startswith("xxxxxxxxxx"):
            print("[Discord] DISCORD_BOT_TOKEN not set, skipping.")
            return
        # Start Discord in the background loop
        await super().start(self.token)

    async def on_ready(self):
        print(f"[Discord] Logged in as {self.user}")

    async def on_message(self, message):
        # Ignore messages from ourselves
        if message.author == self.user:
            return
            
        self.active_channels.add(message.channel.id)
        
        # Show typing indicator while agent thinks
        async with message.channel.typing():
            response = await self.gateway.handle_message("discord", str(message.author.id), message.content)
            
        await message.channel.send(response)

    async def broadcast(self, message: str):
        """Broadcast a message to all active channels."""
        if not self.is_ready():
            return
            
        for channel_id in self.active_channels:
            try:
                channel = self.get_channel(channel_id)
                if channel:
                    await channel.send(message)
            except Exception as e:
                print(f"[Discord] Failed to broadcast to {channel_id}: {e}")
