"""
Move command cog
Handles: /move <from_position> <to_position>
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)


class MoveCog(commands.Cog):
    """Music queue move command"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(
        name="move",
        description="Move a track in the queue"
    )
    @app_commands.describe(
        from_position="Current position of the track (1-based)",
        to_position="New position for the track (1-based)"
    )
    async def move(
        self,
        interaction: discord.Interaction,
        from_position: int,
        to_position: int
    ):
        """Move a track in the queue"""
        await interaction.response.defer()
        
        try:
            player = self.bot.players.get(interaction.guild_id)
            
            if not player:
                embed = EmbedBuilder.create_error_embed(
                    "No player found! Use /play to start playing music."
                )
                await interaction.followup.send(embed=embed)
                return
            
            queue = player.get_queue()
            queue_size = len(queue)
            
            if queue_size == 0:
                embed = EmbedBuilder.create_error_embed(
                    "The queue is empty!"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Convert from 1-based to 0-based indexing
            from_idx = from_position - 1
            to_idx = to_position - 1
            
            # Validate positions
            if from_idx < 0 or from_idx >= queue_size:
                embed = EmbedBuilder.create_error_embed(
                    f"Invalid 'from' position! Must be between 1 and {queue_size}"
                )
                await interaction.followup.send(embed=embed)
                return
            
            if to_idx < 0 or to_idx >= queue_size:
                embed = EmbedBuilder.create_error_embed(
                    f"Invalid 'to' position! Must be between 1 and {queue_size}"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Move the track
            if player.move_track(from_idx, to_idx):
                track = queue[from_idx]
                
                embed = EmbedBuilder.create_success_embed(
                    "✅ Track Moved",
                    f"**{track.title}** moved from position {from_position} to {to_position}"
                )
                await interaction.followup.send(embed=embed)
            else:
                embed = EmbedBuilder.create_error_embed(
                    "Failed to move track!"
                )
                await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Move command error: {e}")
            embed = EmbedBuilder.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(MoveCog(bot))
