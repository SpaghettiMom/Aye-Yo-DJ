"""
Pause/Resume command cog
Handles: /pause
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)


class PauseCog(commands.Cog):
    """Music pause/resume command"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(
        name="pause",
        description="Pause or resume the current track"
    )
    async def pause(self, interaction: discord.Interaction):
        """Pause/Resume playback"""
        await interaction.response.defer()
        
        # Check if user is in voice channel
        if not interaction.user.voice:
            embed = EmbedBuilder.create_error_embed(
                "You must be in a voice channel!"
            )
            await interaction.followup.send(embed=embed)
            return
        
        try:
            voice_client: discord.VoiceClient = interaction.guild.voice_client
            
            if not voice_client or not voice_client.playing:
                embed = EmbedBuilder.create_error_embed(
                    "No track is currently playing!"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Get player
            player = self.bot.players.get(interaction.guild_id)
            if not player:
                embed = EmbedBuilder.create_error_embed(
                    "No player found!"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Toggle pause
            is_paused = player.toggle_pause()
            if is_paused:
                await voice_client.pause(True)
            else:
                await voice_client.pause(False)
            
            status = "⏸️ Paused" if is_paused else "▶️ Resumed"
            embed = EmbedBuilder.create_info_embed(
                status,
                "Playback state changed"
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Pause command error: {e}")
            embed = EmbedBuilder.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(PauseCog(bot))
