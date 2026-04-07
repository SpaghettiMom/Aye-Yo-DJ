"""
Skip command cog
Handles: /skip
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)


class SkipCog(commands.Cog):
    """Music skip command"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="skip",
        description="Skip the current track"
    )
    async def skip(self, interaction: discord.Interaction):
        """Skip the current track"""
        await interaction.response.defer()

        if not interaction.user.voice:
            embed = EmbedBuilder.create_error_embed(
                "You must be in a voice channel!"
            )
            await interaction.followup.send(embed=embed)
            return

        try:
            voice_client = interaction.guild.voice_client

            if not voice_client or not voice_client.playing:
                embed = EmbedBuilder.create_error_embed(
                    "No track is currently playing!"
                )
                await interaction.followup.send(embed=embed)
                return

            await voice_client.stop()

            embed = EmbedBuilder.create_success_embed(
                "⏭️ Skipped",
                "Skipped to the next track"
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Skip command error: {e}")
            embed = EmbedBuilder.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(SkipCog(bot))
