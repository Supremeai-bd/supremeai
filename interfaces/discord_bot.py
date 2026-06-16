import os
import discord
from discord.ext import commands
from loguru import logger
from brain.langgraph_agent import SupremeOrchestrator

class SupremeDiscordBot(commands.Bot):
    def __init__(self, orchestrator: SupremeOrchestrator = None):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.orchestrator = orchestrator or SupremeOrchestrator()

    async def on_ready(self):
        logger.info(f"Discord bot logged in as {self.user.name} ({self.user.id})")

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith("!"):
            await self.process_commands(message)
            return

        # Default fallback: Execute task via SupremeOrchestrator
        logger.info(f"Discord Bot received message from {message.author}: '{message.content}'")
        task_type = "coding" if "code" in message.content.lower() else "general"
        
        async with message.channel.typing():
            try:
                result = self.orchestrator.execute_task(message.content, task_type)
                response = result.get("result", "Sorry, I encountered an error.")
                if len(response) > 2000:
                    for i in range(0, len(response), 2000):
                        await message.channel.send(response[i:i+2000])
                else:
                    await message.channel.send(response)
            except Exception as e:
                logger.error(f"Error handling Discord message: {e}")
                await message.channel.send("Error executing request.")

def run_discord_bot():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token or token == "mock_token":
        logger.warning("DISCORD_BOT_TOKEN not set, skipping Discord bot startup.")
        return
    
    bot = SupremeDiscordBot()
    bot.run(token)

if __name__ == "__main__":
    run_discord_bot()
