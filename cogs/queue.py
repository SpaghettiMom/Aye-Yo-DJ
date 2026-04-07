"""
Queue command cog
Handles: /queue
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.embed_builder import EmbedBuilder
from discord.ui import View, Button, button

logger = logging.getLogger(__name__)


class QueuePagination(View):
    """View for queue pagination"""
    
    def __init__(self, queue, bot, guild_id, timeout=180):
        super().__init__(timeout=timeout)
        self.queue = queue
        self.bot = bot
        self.guild_id = guild_id
        self.current_page = 1
        self.per_page = 10
        self.total_pages = (len(queue) + self.per_page - 1) // self.per_page if queue else 1
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page"""
        self.previous_button.disabled = self.current_page <= 1
        self.next_button.disabled = self.current_page >= self.total_pages
    
    @button(label="◀️ Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        """Previous page button"""
        if self.current_page > 1:
            self.current_page -= 1
            self.update_buttons()
            
            embed = EmbedBuilder.create_queue_embed(self.queue, self.current_page, self.per_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @button(label="Next ▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        """Next page button"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_buttons()
            
            embed = EmbedBuilder.create_queue_embed(self.queue, self.current_page, self.per_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()


class QueueCog(commands.Cog):
    """Music queue command"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(
        name="queue",
        description="Show the current music queue"
    )
    @app_commands.describe(page="Page number (optional)")
    async def queue(self, interaction: discord.Interaction, page: int = 1):
        """Show the queue"""
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
            
            if not queue:
                embed = EmbedBuilder.create_info_embed(
                    "📋 Queue",
                    "The queue is empty. Use /play to add tracks!"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Validate page number
            per_page = 10
            total_pages = (len(queue) + per_page - 1) // per_page
            
            if page < 1 or page > total_pages:
                page = 1
            
            # Create queue embed
            embed = EmbedBuilder.create_queue_embed(queue, page, per_page)
            
            # Create pagination view if multiple pages
            view = QueuePagination(queue, self.bot, interaction.guild_id)
            view.current_page = page
            view.update_buttons()
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Queue command error: {e}")
            embed = EmbedBuilder.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(QueueCog(bot))
