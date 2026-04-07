"""
Play command cog
Handles: /play <song/url>
"""
import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import logging
from utils.search import MusicSearch
from utils.embed_builder import EmbedBuilder
from utils.player import MusicPlayer
from config import RADIO_JINGLE_URL

logger = logging.getLogger(__name__)


class PlayCog(commands.Cog):
    """Music play command"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_or_create_player(self, guild_id: int) -> MusicPlayer:
        """Get or create a player for the guild"""
        if guild_id not in self.bot.players:
            self.bot.players[guild_id] = MusicPlayer(guild_id)
        return self.bot.players[guild_id]
    
    @app_commands.command(
        name="play",
        description="Play a song from YouTube or Spotify"
    )
    @app_commands.describe(
        query="Song name, artist, or URL",
        source="Music source (youtube, spotify)"
    )
    async def play(
        self,
        interaction: discord.Interaction,
        query: str,
        source: str = "youtube"
    ):
        """Play a song"""
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
                    # Check if we have a connected node first
                    if not wavelink.Pool.nodes:
                        embed = EmbedBuilder.create_error_embed(
                            "Lavalink server is not connected. Please try again in a moment."
                        )
                        await interaction.followup.send(embed=embed)
                        logger.error("No Lavalink nodes available")
                        return
                    
                    # Get the first available node from the pool
                    node = next(iter(wavelink.Pool.nodes.values()))
                    logger.info(f"Using Lavalink node: {node.identifier}")
                    
                    # Create a wavelink Player with increased timeout
                    voice_client: wavelink.Player = await voice_channel.connect(
                        cls=wavelink.Player,
                        timeout=30.0  # Increased to 30 seconds for Lavalink connection
                    )
                    logger.info(f"Successfully connected to voice channel {voice_channel.name}")
                except Exception as e:
                    # If we connected but something else failed, disconnect cleanly
                    if isinstance(voice_client, wavelink.Player):
                        try:
                            await voice_client.disconnect()
                        except Exception:
                            pass
                    embed = EmbedBuilder.create_error_embed(
                        f"Failed to connect to voice channel: {str(e)}"
                    )
                    await interaction.followup.send(embed=embed)
                    logger.error(f"Voice connection error: {e}", exc_info=True)
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
            
            # Show search suggestions
            suggestions = await MusicSearch.get_suggestions(query, limit=5, search_type=source)
            
            if not suggestions:
                embed = EmbedBuilder.create_error_embed(
                    f"No results found for: {query}"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Create search results embed
            embed = EmbedBuilder.create_search_result(
                "Search Results",
                suggestions,
                query
            )
            
            # Add select menu for track selection
            from discord.ui import View, Select
            
            class TrackSelect(Select):
                def __init__(self, suggestions, cog, voice_client, player, interaction):
                    self.suggestions = suggestions
                    self.cog = cog
                    self.voice_client = voice_client
                    self.player = player
                    self.interaction_obj = interaction
                    
                    options = [
                        discord.SelectOption(
                            label=suggestion['title'][:100],
                            value=str(i),
                            description=suggestion['artist'][:100]
                        )
                        for i, suggestion in enumerate(suggestions)
                    ]
                    super().__init__(
                        placeholder="Select a track...",
                        options=options
                    )
                
                async def callback(self, select_interaction: discord.Interaction):
                    await select_interaction.response.defer()
                    
                    try:
                        idx = int(self.values[0])
                        track_data = self.suggestions[idx]
                        logger.info(f"Track selected: {track_data['title']} - {track_data['artist']}")
                        
                        # Get the actual track
                        tracks, _ = await MusicSearch.search(
                            track_data['title'],
                            search_type=source
                        )
                        logger.info(f"Search returned {len(tracks) if tracks else 0} tracks")
                        
                        if not tracks:
                            embed = EmbedBuilder.create_error_embed(
                                "Failed to load track"
                            )
                            await select_interaction.followup.send(embed=embed)
                            return
                        
                        track = tracks[0]
                        logger.info(f"Track object: {track} | Type: {type(track)}")
                        logger.info(f"Track attributes: title={getattr(track, 'title', 'N/A')}, uri={getattr(track, 'uri', 'N/A')}")
                        
                        # Add to queue
                        self.player.add_track(track)
                        logger.info(f"Added track to queue. Queue size: {self.player.get_queue_size()}")
                        
                        # Show added embed
                        embed = EmbedBuilder.create_track_added_embed([track])
                        embed.add_field(
                            name="Position in Queue",
                            value=f"{self.player.get_queue_size()}",
                            inline=True
                        )
                        
                        await select_interaction.followup.send(embed=embed)
                        
                        # Play if no track is currently playing
                        if not self.voice_client.playing:
                            next_track = self.player.next_track()
                            if next_track:
                                # Play jingle once at the start of a new queue session
                                if not self.player.jingle_played and RADIO_JINGLE_URL:
                                    try:
                                        jingle_results, _ = await MusicSearch.search(RADIO_JINGLE_URL)
                                        if jingle_results:
                                            self.player.jingle_played = True
                                            # Re-insert the selected track back so it plays after the jingle
                                            self.player.queue.appendleft(next_track)
                                            next_track = jingle_results[0]
                                            logger.info(f"Playing jingle before queue start")
                                    except Exception as jingle_error:
                                        logger.warning(f"Could not load jingle: {jingle_error}")

                                try:
                                    await self.voice_client.play(next_track)
                                    logger.info(f"Track sent to Lavalink. Voice client playing: {self.voice_client.playing}")
                                except Exception as play_error:
                                    logger.error(f"Error playing track: {play_error}", exc_info=True)
                                    raise
                            else:
                                logger.warning("No next track available after adding to queue")
                        else:
                            logger.info(f"Voice client already playing, added to queue for later")
                        
                    except Exception as e:
                        embed = EmbedBuilder.create_error_embed(
                            f"Error: {str(e)}"
                        )
                        await select_interaction.followup.send(embed=embed)
            
            view = View()
            view.add_item(TrackSelect(suggestions, self, voice_client, player, interaction))
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Play command error: {e}")
            embed = EmbedBuilder.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(PlayCog(bot))
