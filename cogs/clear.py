"""
Clear command cog
Handles: /clear
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)


class ClearCog(commands.Cog):
    """Music queue clear command"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="clear",
        description="Clear the music queue without stopping the current song"
    )
    async def clear(self, interaction: discord.Interaction):
        """Clear the queue"""
        await interaction.response.defer()

        if not interaction.user.voice:
            embed = EmbedBuilder.create_error_embed(
                "You must be in a voice channel!"
            )
            await interaction.followup.send(embed=embed)
            return

        try:
            player = self.bot.players.get(interaction.guild_id)

            if not player:
                embed = EmbedBuilder.create_error_embed(
                    "No player found! Use /play to start playing music."
                )
                await interaction.followup.send(embed=embed)
                return

            queue_size = player.get_queue_size()

            if queue_size == 0:
                embed = EmbedBuilder.create_info_embed(
                    "📋 Queue",
                    "The queue is already empty!"
                )
                await interaction.followup.send(embed=embed)
                return

            player.clear_queue()

            embed = EmbedBuilder.create_success_embed(
                "🗑️ Queue Cleared",
                f"Removed {queue_size} track{'s' if queue_size != 1 else ''} from the queue."
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in clear command: {e}")
            embed = EmbedBuilder.create_error_embed(
                "An error occurred while clearing the queue."
            )
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ClearCog(bot))
