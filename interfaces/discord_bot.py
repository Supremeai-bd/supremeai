"""
SupremeAI 2.0 — Discord Bot Handler (Production-Ready)

Features:
- Slash commands: /ask, /status, /help
- Message intent routing → SupremeOrchestrator
- Long response chunking (2000-char limit)
- All privileged intents supported

Setup:
  1. discord.com/developers → New Application → Bot → Add Bot
  2. Enable: SERVER MEMBERS INTENT, MESSAGE CONTENT INTENT, PRESENCE INTENT
  3. Copy token → .env: DISCORD_BOT_TOKEN=your_token_here
  4. Invite bot: OAuth2 → URL Generator → bot + applications.commands
     Permissions: Send Messages, Read Message History, Use Slash Commands
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger


class SupremeDiscordBot(commands.Bot):
    """
    Production Discord Bot with slash commands and AI message routing.
    """

    def __init__(self, orchestrator=None) -> None:
        intents = discord.Intents.all()  # All intents enabled (set in Dev Portal)
        super().__init__(command_prefix="!", intents=intents)
        self.orchestrator = orchestrator
        self._synced = False

    # ── Lifecycle ────────────────────────────────────────────────

    async def setup_hook(self) -> None:
        """Register slash commands on startup."""
        self.tree.add_command(_ask_cmd)
        self.tree.add_command(_status_cmd)
        self.tree.add_command(_help_cmd)
        await self.tree.sync()
        logger.info("✅ Discord slash commands synced.")

    async def on_ready(self) -> None:
        logger.info(f"🤖 Discord bot logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the SupremeAI mesh | /help",
            )
        )

    # ── Message handler ──────────────────────────────────────────

    async def on_message(self, message: discord.Message) -> None:
        # Ignore own messages
        if message.author == self.user:
            return

        # Process prefix commands (!, etc.)
        await self.process_commands(message)

        # Ignore prefix commands (already handled)
        if message.content.startswith(self.command_prefix):
            return

        # Only respond to DMs or when mentioned
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.user in message.mentions

        if not (is_dm or is_mentioned):
            return

        # Strip mention from text
        text = message.content.replace(f"<@{self.user.id}>", "").strip()
        if not text:
            await message.reply("Hi! Send me a message or use `/help`.")
            return

        logger.info(f"Discord message from {message.author}: '{text}'")

        async with message.channel.typing():
            response = await self._ai_response(text, str(message.author.id))

        await self._send_chunked(message.channel, response, reply_to=message)

    # ── Helpers ──────────────────────────────────────────────────

    async def _ai_response(self, text: str, user_id: str) -> str:
        if self.orchestrator:
            try:
                task_type = (
                    "coding"
                    if any(k in text.lower() for k in ["code", "function", "script", "debug"])
                    else "general"
                )
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: self.orchestrator.execute_task(text, task_type)
                )
                return result.get("result", "Sorry, I couldn't process that.")
            except Exception as exc:
                logger.error(f"Orchestrator error: {exc}")
                return "⚠️ Error processing request. Please try again."
        return "🤖 SupremeAI 2.0 is ready! (Orchestrator not connected)"

    async def _send_chunked(
        self,
        channel: discord.abc.Messageable,
        text: str,
        reply_to: Optional[discord.Message] = None,
    ) -> None:
        chunks = [text[i : i + 1990] for i in range(0, len(text), 1990)]
        for i, chunk in enumerate(chunks):
            if i == 0 and reply_to:
                await reply_to.reply(chunk)
            else:
                await channel.send(chunk)

    async def system_status(self) -> str:
        """Check all backend nodes."""
        import httpx

        lines = ["🔍 **SupremeAI System Status**\n"]
        nodes = [
            ("GCP Cloud Run", os.getenv("GCP_CLOUD_RUN_URL", "")),
            ("Railway", os.getenv("RAILWAY_URL", "")),
            ("Render", os.getenv("RENDER_URL", "")),
        ]
        for name, url in nodes:
            if not url:
                lines.append(f"⚪ **{name}**: not configured")
                continue
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(url + "/health")
                    icon = "✅" if r.status_code == 200 else "⚠️"
                    lines.append(f"{icon} **{name}**: `HTTP {r.status_code}`")
            except Exception:
                lines.append(f"❌ **{name}**: unreachable")
        return "\n".join(lines)


# ── Slash Commands ────────────────────────────────────────────────

@app_commands.command(name="ask", description="Ask SupremeAI anything")
@app_commands.describe(question="Your question or task")
async def _ask_cmd(interaction: discord.Interaction, question: str) -> None:
    await interaction.response.defer(thinking=True)
    bot: SupremeDiscordBot = interaction.client
    response = await bot._ai_response(question, str(interaction.user.id))
    # Discord followup has 2000 char limit
    if len(response) > 1990:
        await interaction.followup.send(response[:1990])
        for chunk in [response[i : i + 1990] for i in range(1990, len(response), 1990)]:
            await interaction.channel.send(chunk)
    else:
        await interaction.followup.send(response)


@app_commands.command(name="status", description="Check SupremeAI system health")
async def _status_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    bot: SupremeDiscordBot = interaction.client
    status = await bot.system_status()
    await interaction.followup.send(status)


@app_commands.command(name="help", description="Show SupremeAI help")
async def _help_cmd(interaction: discord.Interaction) -> None:
    embed = discord.Embed(
        title="🔱 SupremeAI 2.0",
        description="Multi-cloud AI agent system",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="/ask [question]", value="Ask AI anything", inline=False)
    embed.add_field(name="/status", value="Check system health", inline=False)
    embed.add_field(name="/help", value="Show this help", inline=False)
    embed.add_field(
        name="💬 Direct Message",
        value="DM me or @mention me in any channel",
        inline=False,
    )
    embed.set_footer(text="SupremeAI 2.0 | Powered by multi-cloud AI mesh")
    await interaction.response.send_message(embed=embed)


# ── Entrypoint ────────────────────────────────────────────────────

def run_discord_bot(orchestrator=None) -> None:
    token = os.getenv("DISCORD_BOT_TOKEN", "")
    if not token:
        logger.warning("DISCORD_BOT_TOKEN not set — Discord bot disabled.")
        return

    bot = SupremeDiscordBot(orchestrator=orchestrator)
    logger.info("🚀 Starting Discord bot...")
    bot.run(token, log_handler=None)  # loguru handles logging


if __name__ == "__main__":
    run_discord_bot()
