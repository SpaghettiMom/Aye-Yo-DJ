"""
Play command cog
Handles: /play <song/url>
"""
import discord
from discord.ext import commands
from discord import app_commands
import wavelink
from wavelink.exceptions import LavalinkException
import logging
import os
import random
from urllib.parse import quote
from typing import List, Optional
from utils.search import MusicSearch
from utils.embed_builder import EmbedBuilder
from utils.player import MusicPlayer
from config import JINGLE_DIR, JINGLE_SERVER_HOST, JINGLE_SERVER_PORT

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

    def _random_jingle_url(self) -> Optional[str]:
        """Pick a random jingle file from the jingles directory and return its HTTP URL."""
        if not JINGLE_SERVER_HOST or not JINGLE_DIR:
            return None
        try:
            files = [
                f for f in os.listdir(JINGLE_DIR)
                if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac'))
            ]
            if not files:
                return None
            return f"http://{JINGLE_SERVER_HOST}:{JINGLE_SERVER_PORT}/jingles/{quote(random.choice(files))}"
        except Exception:
            return None

    async def query_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        if not current or len(current) < 2:
            return []
        try:
            import aiohttp
            url = "https://suggestqueries.google.com/complete/search"
            params = {"client": "firefox", "ds": "yt", "q": current}
            timeout = aiohttp.ClientTimeout(total=2.5)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as resp:
                    data = await resp.json(content_type=None)
            suggestions = data[1][:6]
            return [
                app_commands.Choice(name=s[:100], value=s[:100])
                for s in suggestions
            ]
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
                            jingle_url = self._random_jingle_url()
                            if not player.jingle_played and jingle_url and self.bot.jingle_enabled:
                                try:
                                    jingle_results, _ = await MusicSearch.search(jingle_url)
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
                        jingle_url = self._random_jingle_url()
                        if not player.jingle_played and jingle_url and self.bot.jingle_enabled:
                            try:
                                jingle_results, _ = await MusicSearch.search(jingle_url)
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
                    jingle_url = self._random_jingle_url()
                    if not player.jingle_played and jingle_url and self.bot.jingle_enabled:
                        try:
                            jingle_results, _ = await MusicSearch.search(jingle_url)
                            if jingle_results:
                                player.jingle_played = True
                                player.queue.appendleft(next_track)
                                next_track = jingle_results[0]
                                logger.info("Playing jingle before queue start")
                        except Exception as jingle_error:
                            logger.warning(f"Could not load jingle: {jingle_error}")
                    player.current_requester = getattr(next_track, 'requester', None)
                    await voice_client.play(next_track)
            
        except LavalinkException as exc:
            if exc.status == 404:
                logger.warning(f"Play command: Lavalink session expired (404), node is reconnecting")
                embed = EmbedBuilder.create_error_embed(
                    "The Lavalink connection was lost and is reconnecting. Please try again in a moment."
                )
            else:
                logger.error(f"Play command Lavalink error: {exc}")
                embed = EmbedBuilder.create_error_embed(f"Lavalink error ({exc.status}): {exc.error}")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Play command error: {e}")
            embed = EmbedBuilder.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(PlayCog(bot))
