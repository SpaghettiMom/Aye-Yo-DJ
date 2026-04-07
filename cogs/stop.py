"""
Stop command cog
Handles: /stop
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)


class StopCog(commands.Cog):
    """Music stop command"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(
        name="stop",
        description="Stop music playback and clear the queue"
    )
    async def stop(self, interaction: discord.Interaction):
        """Stop playback"""
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
            
            if not voice_client:
                embed = EmbedBuilder.create_error_embed(
                    "Bot is not connected to a voice channel!"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Get player and clear it
            player = self.bot.players.get(interaction.guild_id)
            if player:
                player.clear_queue()
                player.current_track = None
                player.set_pause(False)
            
            # Stop playback
            if voice_client.playing:
                voice_client.stop()
            
            embed = EmbedBuilder.create_success_embed(
                "⏹️ Stopped",
                "Playback stopped and queue cleared"
            )
            
            await interaction.followup.send(embed=embed)
            
            # Disconnect from voice channel and clean up player
            await voice_client.disconnect()
            if interaction.guild_id in self.bot.players:
                del self.bot.players[interaction.guild_id]
            
        except Exception as e:
            logger.error(f"Stop command error: {e}")
            embed = EmbedBuilder.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(StopCog(bot))
