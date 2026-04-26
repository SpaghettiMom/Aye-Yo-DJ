"""
Play command cog
Handles: /play <song/url>
"""
import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import logging
from typing import List
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

    async def query_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        if not current or len(current) < 2:
            return []
        try:
            suggestions = await MusicSearch.get_suggestions(current, limit=6)
            choices = []
            for s in suggestions:
                label = f"{s['title']} - {s['artist']}"
                choices.append(
                    app_commands.Choice(name=label[:100], value=s['url'])
                )
            return choices
        except Exception:
            return []

    @app_commands.command(
        name="play",
        description="Play a song from YouTube or Spotify"
    )
    @app_commands.describe(
        query="Song name, artist, or URL",
        source="Music source (youtube, spotify)"
    )
    @app_commands.autocomplete(query=query_autocomplete)
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

            # If the query is a URL (e.g. selected from autocomplete), play it directly
            is_url = query.startswith("http://") or query.startswith("https://")
            if is_url:
                # Detect playlist URLs
                is_playlist = (
                    "open.spotify.com/playlist/" in query
                    or "youtube.com/playlist" in query
                    or ("list=" in query and ("youtube.com" in query or "youtu.be" in query))
                )
                if is_playlist:
                    tracks, source = await MusicSearch.search_playlist(query)
                    if not tracks:
                        embed = EmbedBuilder.create_error_embed(
                            "Could not load any tracks from that playlist.\n\n"
                            "**If this is a Spotify playlist**, your Spotify developer app may need "
                            "Web API access enabled:\n"
                            "1. Go to https://developer.spotify.com/dashboard\n"
                            "2. Open your app → Settings\n"
                            "3. Enable **Web API** and save"
                        )
                        await interaction.followup.send(embed=embed)
                        return
                    for t in tracks:
                        t.requester = interaction.user
                    added = player.add_tracks(tracks)
                    embed = EmbedBuilder.create_track_added_embed(tracks[:added], playlist=True)
                    embed.add_field(name="Total Tracks", value=str(len(tracks)), inline=True)
                    embed.add_field(name="Added to Queue", value=str(added), inline=True)
                    await interaction.followup.send(embed=embed)
                    if not voice_client.playing:
                        next_track = player.next_track()
                        if next_track:
                            if not player.jingle_played and RADIO_JINGLE_URL:
                                try:
                                    jingle_results, _ = await MusicSearch.search(RADIO_JINGLE_URL)
                                    if jingle_results:
                                        player.jingle_played = True
                                        player.queue.appendleft(next_track)
                                        next_track = jingle_results[0]
                                except Exception as jingle_error:
                                    logger.warning(f"Could not load jingle: {jingle_error}")
                            player.current_requester = getattr(next_track, 'requester', None)
                            await voice_client.play(next_track)
                    return

                tracks, _ = await MusicSearch.search(query)
                if not tracks:
                    embed = EmbedBuilder.create_error_embed(f"Could not load track: {query}")
                    await interaction.followup.send(embed=embed)
                    return
                track = tracks[0]
                track.requester = interaction.user
                player.add_track(track)
                embed = EmbedBuilder.create_track_added_embed([track])
                embed.add_field(name="Position in Queue", value=f"{player.get_queue_size()}", inline=True)
                await interaction.followup.send(embed=embed)
                if not voice_client.playing:
                    next_track = player.next_track()
                    if next_track:
                        if not player.jingle_played and RADIO_JINGLE_URL:
                            try:
                                jingle_results, _ = await MusicSearch.search(RADIO_JINGLE_URL)
                                if jingle_results:
                                    player.jingle_played = True
                                    player.queue.appendleft(next_track)
                                    next_track = jingle_results[0]
                            except Exception as jingle_error:
                                logger.warning(f"Could not load jingle: {jingle_error}")
                        player.current_requester = getattr(next_track, 'requester', None)
                        await voice_client.play(next_track)
                return

            # Plain text query – search and play the top result directly
            tracks, _ = await MusicSearch.search(query, search_type=source)
            if not tracks:
                embed = EmbedBuilder.create_error_embed(f"No results found for: {query}")
                await interaction.followup.send(embed=embed)
                return

            track = tracks[0]
            track.requester = interaction.user
            player.add_track(track)
            embed = EmbedBuilder.create_track_added_embed([track])
            embed.add_field(name="Position in Queue", value=f"{player.get_queue_size()}", inline=True)
            await interaction.followup.send(embed=embed)

            if not voice_client.playing:
                next_track = player.next_track()
                if next_track:
                    if not player.jingle_played and RADIO_JINGLE_URL:
                        try:
                            jingle_results, _ = await MusicSearch.search(RADIO_JINGLE_URL)
                            if jingle_results:
                                player.jingle_played = True
                                player.queue.appendleft(next_track)
                                next_track = jingle_results[0]
                                logger.info("Playing jingle before queue start")
                        except Exception as jingle_error:
                            logger.warning(f"Could not load jingle: {jingle_error}")
                    player.current_requester = getattr(next_track, 'requester', None)
                    await voice_client.play(next_track)
            
        except Exception as e:
            logger.error(f"Play command error: {e}")
            embed = EmbedBuilder.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(PlayCog(bot))
