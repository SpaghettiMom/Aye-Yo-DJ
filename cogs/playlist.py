"""
Playlist command cog
Handles: /playlist <url> or /playlist search <query>
"""
import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import logging
from utils.search import MusicSearch
from utils.embed_builder import EmbedBuilder
from utils.player import MusicPlayer

logger = logging.getLogger(__name__)


class PlaylistCog(commands.Cog):
    """Music playlist command"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_or_create_player(self, guild_id: int) -> MusicPlayer:
        """Get or create a player for the guild"""
        if guild_id not in self.bot.players:
            self.bot.players[guild_id] = MusicPlayer(guild_id)
        return self.bot.players[guild_id]
    
    @app_commands.command(
        name="playlist",
        description="Load a playlist from YouTube or Spotify"
    )
    @app_commands.describe(
        url="Playlist URL or search query",
        source="Music source (youtube, spotify)"
    )
    async def playlist(
        self,
        interaction: discord.Interaction,
        url: str,
        source: str = "youtube"
    ):
        """Load a playlist"""
        await interaction.response.defer()
        
        # Check if user is in voice channel
        if not interaction.user.voice:
            embed = EmbedBuilder.create_error_embed(
                "You must be in a voice channel to play music!"
            )
            await interaction.followup.send(embed=embed)
            return
        
        try:
            # Get or create voice client
            voice_channel = interaction.user.voice.channel
            voice_client: discord.VoiceClient = interaction.guild.voice_client
            
            if not voice_client:
                try:
                    voice_client = await voice_channel.connect(cls=wavelink.Player)
                    voice_client.guild = interaction.guild
                except Exception as e:
                    embed = EmbedBuilder.create_error_embed(
                        f"Failed to connect to voice channel: {str(e)}"
                    )
                    await interaction.followup.send(embed=embed)
                    return
            elif voice_client.channel != voice_channel:
                try:
                    await voice_client.move_to(voice_channel)
                except Exception as e:
                    embed = EmbedBuilder.create_error_embed(
                        f"Failed to move to voice channel: {str(e)}"
                    )
                    await interaction.followup.send(embed=embed)
                    return
            
            # Get or create player
            player = await self.get_or_create_player(interaction.guild_id)
            
            # Try to load playlist
            try:
                if url.startswith("http"):
                    # It's a direct URL
                    playlist = await wavelink.Playable.search(url)
                else:
                    # It's a search query
                    search_source = "spsearch" if source.lower() == "spotify" else "ytplaylist"
                    playlist = await wavelink.Playable.search(
                        f"{search_source}:{url}"
                    )
            except Exception as e:
                embed = EmbedBuilder.create_error_embed(
                    f"Failed to load playlist: {str(e)}"
                )
                await interaction.followup.send(embed=embed)
                return
            
            if not playlist:
                embed = EmbedBuilder.create_error_embed(
                    f"No playlist found for: {url}"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Add tracks to queue
            added = player.add_tracks(playlist)
            
            if added == 0:
                embed = EmbedBuilder.create_error_embed(
                    "Could not add any tracks from the playlist!"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Create success embed
            embed = EmbedBuilder.create_track_added_embed(playlist[:added], playlist=True)
            embed.add_field(
                name="Total Tracks",
                value=f"{len(playlist)}",
                inline=True
            )
            embed.add_field(
                name="Successfully Added",
                value=f"{added}",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
            # Play if no track is currently playing
            if not voice_client.playing:
                next_track = player.next_track()
                if next_track:
                    try:
                        await voice_client.play(next_track)
                    except Exception as e:
                        logger.error(f"Error playing track: {e}")
        
        except Exception as e:
            logger.error(f"Playlist command error: {e}")
            embed = EmbedBuilder.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(PlaylistCog(bot))
