import os
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from hermes.platforms.gateway import PlatformGateway

class TelegramBot:
    """Telegram adapter for Hermes Gateway."""
    
    def __init__(self, gateway: PlatformGateway):
        self.gateway = gateway
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.app = None
        self.active_chats = set()

    async def start(self):
        """Start the Telegram bot in the background."""
        if not self.token or self.token.startswith("xxxxxxxxxx"):
            print("[Telegram] TELEGRAM_BOT_TOKEN not set, skipping.")
            return
            
        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_msg))
        
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        print("[Telegram] Started polling.")

    async def _handle_msg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message.text
        user_id = str(update.message.from_user.id)
        chat_id = update.effective_chat.id
        self.active_chats.add(chat_id)
        
        # Typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        
        # Route message to the central agent brain
        response = await self.gateway.handle_message("telegram", user_id, message)
        
        # Send back to Telegram
        await update.message.reply_text(response)
        
    async def broadcast(self, message: str):
        """Broadcast a message to all chats that have interacted with the bot."""
        if not self.app:
            return
        for chat_id in self.active_chats:
            try:
                await self.app.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                print(f"[Telegram] Failed to broadcast to {chat_id}: {e}")
