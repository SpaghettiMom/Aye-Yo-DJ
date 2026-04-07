"""
Music player controller view
Interactive buttons and menus for the player controller message
"""
import discord
from discord.ui import View, Button, button
from typing import Optional


class PlayerController(View):
    """Interactive music player controller with buttons"""
    
    def __init__(self, bot, player, guild_id: int, timeout: Optional[int] = None):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.player = player
        self.guild_id = guild_id
    
    @button(
        label="⏯️ Play/Pause",
        style=discord.ButtonStyle.primary,
        custom_id="music_player:pause_resume"
    )
    async def pause_resume_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ) -> None:
        """Pause/Resume button"""
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ You must be in a voice channel!",
                ephemeral=True
            )
            return
        
        try:
            player = self.bot.players.get(self.guild_id)
            
            if not player:
                await interaction.response.send_message(
                    "❌ No player found!",
                    ephemeral=True
                )
                return
            
            voice_client = interaction.guild.voice_client
            if not voice_client:
                await interaction.response.send_message(
                    "❌ Bot is not in a voice channel!",
                    ephemeral=True
                )
                return

            if voice_client.paused:
                await voice_client.pause(False)
                status = "▶️ Resumed"
            else:
                await voice_client.pause(True)
                status = "⏸️ Paused"
            
            await interaction.response.send_message(
                status,
                ephemeral=True,
                delete_after=2
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @button(
        label="⏭️ Skip",
        style=discord.ButtonStyle.primary,
        custom_id="music_player:skip"
    )
    async def skip_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ) -> None:
        """Skip to next track button"""
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ You must be in a voice channel!",
                ephemeral=True
            )
            return
        
        try:
            player = self.bot.players.get(self.guild_id)

            if not player:
                await interaction.response.send_message(
                    "❌ No player found!",
                    ephemeral=True
                )
                return

            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.playing:
                await voice_client.stop()
                await interaction.response.send_message(
                    "⏭️ Skipped!",
                    ephemeral=True,
                    delete_after=2
                )
            else:
                await interaction.response.send_message(
                    "❌ No track is currently playing!",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @button(
        label="⏹️ Stop",
        style=discord.ButtonStyle.danger,
        custom_id="music_player:stop"
    )
    async def stop_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ) -> None:
        """Stop playback button"""
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ You must be in a voice channel!",
                ephemeral=True
            )
            return
        
        try:
            player = self.bot.players.get(self.guild_id)

            if not player:
                await interaction.response.send_message(
                    "❌ No player found!",
                    ephemeral=True
                )
                return

            voice_client = interaction.guild.voice_client
            if voice_client:
                player.clear_queue()
                player.current_track = None
                if voice_client.playing:
                    await voice_client.stop()
                await voice_client.disconnect()
                del self.bot.players[self.guild_id]

            await interaction.response.send_message(
                "⏹️ Playback stopped",
                ephemeral=True,
                delete_after=2
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @button(
        label="🔀 Shuffle",
        style=discord.ButtonStyle.secondary,
        custom_id="music_player:shuffle"
    )
    async def shuffle_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ) -> None:
        """Shuffle queue button"""
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ You must be in a voice channel!",
                ephemeral=True
            )
            return
        
        try:
            import random

            player = self.bot.players.get(self.guild_id)

            if not player:
                await interaction.response.send_message(
                    "❌ No player found!",
                    ephemeral=True
                )
                return
            
            queue = player.get_queue()
            if not queue:
                await interaction.response.send_message(
                    "❌ Queue is empty!",
                    ephemeral=True
                )
                return
            
            random.shuffle(queue)
            player.queue = __import__('collections').deque(queue, maxlen=player.queue.maxlen)
            
            await interaction.response.send_message(
                "🔀 Queue shuffled",
                ephemeral=True,
                delete_after=2
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @button(
        label="📋 Queue",
        style=discord.ButtonStyle.secondary,
        custom_id="music_player:queue"
    )
    async def queue_button(
        self,
        interaction: discord.Interaction,
        button: Button
    ) -> None:
        """Show queue button"""
        try:
            from utils.embed_builder import EmbedBuilder

            player = self.bot.players.get(self.guild_id)

            if not player:
                await interaction.response.send_message(
                    "❌ No player found!",
                    ephemeral=True
                )
                return
            
            queue = player.get_queue()
            embed = EmbedBuilder.create_queue_embed(queue)
            
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
