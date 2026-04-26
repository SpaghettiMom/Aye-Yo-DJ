"""
Autoplay command cog
Handles: /autoplay — toggle continuous playback of similar music
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)


class AutoplayCog(commands.Cog):
    """Toggle autoplay mode (continuous similar music)"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="autoplay",
        description="Toggle autoplay — the bot will keep playing similar music when the queue runs out"
    )
    async def autoplay(self, interaction: discord.Interaction):
        """Toggle autoplay mode for this guild"""
        player = self.bot.players.get(interaction.guild_id)

        if not player:
            embed = EmbedBuilder.create_error_embed(
                "Nothing is playing right now. Use **/play** to start some music first!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        player.autoplay = not player.autoplay

        if player.autoplay:
            embed = EmbedBuilder.create_success_embed(
                "🔁 Autoplay Enabled",
                "I'll automatically queue similar tracks when the queue runs out."
            )
        else:
            embed = EmbedBuilder.create_info_embed(
                "⏹️ Autoplay Disabled",
                "Autoplay has been turned off. Playback will stop when the queue is empty."
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(AutoplayCog(bot))
