"""
Jingle admin command cog
Handles: /jingle enable|disable
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from utils.embed_builder import EmbedBuilder
from config import JINGLE_DIR, JINGLE_SERVER_HOST, JINGLE_SERVER_PORT

logger = logging.getLogger(__name__)


class JingleCog(commands.Cog):
    """Admin command to toggle the radio jingle"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="jingle",
        description="Enable or disable the radio jingle (Admin only)"
    )
    @app_commands.describe(state="Turn the jingle on or off")
    @app_commands.choices(state=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def jingle(self, interaction: discord.Interaction, state: str):
        """Toggle the radio jingle on or off"""
        if not JINGLE_SERVER_HOST:
            embed = EmbedBuilder.create_error_embed(
                "Jingle server host is not configured (`JINGLE_SERVER_HOST` is empty in .env)."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        files = []
        if JINGLE_DIR and os.path.exists(JINGLE_DIR):
            files = [f for f in os.listdir(JINGLE_DIR) if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac'))]

        if not files:
            embed = EmbedBuilder.create_error_embed(
                f"No jingle files found in `{JINGLE_DIR}/`. Add `.mp3`, `.wav`, `.ogg`, or `.flac` files there first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if state == "enable":
            self.bot.jingle_enabled = True
            embed = EmbedBuilder.create_success_embed(
                "Radio Jingle Enabled",
                "The radio jingle will play at the start of each new queue session."
            )
            logger.info(f"Jingle enabled by {interaction.user} in guild {interaction.guild_id}")
        else:
            self.bot.jingle_enabled = False
            # Reset jingle_played on all active players so it doesn't play when re-enabled
            for player in self.bot.players.values():
                player.jingle_played = True
            embed = EmbedBuilder.create_success_embed(
                "Radio Jingle Disabled",
                "The radio jingle will no longer play."
            )
            logger.info(f"Jingle disabled by {interaction.user} in guild {interaction.guild_id}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="jinglestatus",
        description="Check whether the radio jingle is currently enabled (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def jinglestatus(self, interaction: discord.Interaction):
        """Show current jingle status and available files"""
        enabled = getattr(self.bot, "jingle_enabled", True)
        status = "Enabled ✅" if enabled else "Disabled ❌"

        files = []
        if JINGLE_DIR and os.path.exists(JINGLE_DIR):
            files = [f for f in os.listdir(JINGLE_DIR) if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac'))]

        file_list = "\n".join(f"• {f}" for f in sorted(files)) if files else "*(no jingle files found — drop MP3/WAV/OGG/FLAC into the `jingles/` folder)*"
        host_info = f"`{JINGLE_SERVER_HOST}:{JINGLE_SERVER_PORT}`" if JINGLE_SERVER_HOST else "*(JINGLE_SERVER_HOST not set in .env)*"
        embed = EmbedBuilder.create_info_embed(
            "Radio Jingle Status",
            f"**Status:** {status}\n**Server:** {host_info}\n**Files ({len(files)}):**\n{file_list}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(JingleCog(bot))
