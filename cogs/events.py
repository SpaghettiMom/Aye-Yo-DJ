"""
Music events cog
Handles: Track end, track start, and player controller events
"""
import discord
from discord.ext import commands
import wavelink
import logging
import aiohttp
from utils.embed_builder import EmbedBuilder
from utils.music_player_view import PlayerController
from utils.search import MusicSearch
from config import LAVALINK_HOST, LAVALINK_PORT, LAVALINK_PASSWORD, JINGLE_SERVER_HOST, JINGLE_SERVER_PORT

logger = logging.getLogger(__name__)


class EventsCog(commands.Cog):
    """Handle music player events"""
    
    def __init__(self, bot):
        self.bot = bot
        self._voice_updates = {}  # Track pending voice updates

    def _get_notification_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Find the first writable text channel for status messages."""
        for text_channel in guild.text_channels:
            if text_channel.permissions_for(guild.me).send_messages:
                return text_channel
        return None
    
    @commands.Cog.listener()
    async def on_connect(self):
        """Initialize bot connection handler"""
        logger.info("Bot connected to Discord")
    
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload) -> None:
        """Called when a Lavalink node is ready"""
        logger.info(f"Wavelink node is ready")
    
    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload) -> None:
        """Handle track exception event — fired when Lavalink fails to load/stream a track."""
        try:
            exc = payload.exception
            track_title = getattr(payload.track, 'title', 'unknown')
            logger.error(
                f"Track exception for '{track_title}': "
                f"{exc.get('message', 'unknown')} (severity={exc.get('severity', '?')}, "
                f"cause={exc.get('cause', '?')})"
            )
            player: wavelink.Player = payload.player
            if not player or not player.guild:
                return
            bot_player = self.bot.players.get(player.guild.id)
            if not bot_player:
                return
            # Don't post an error for jingle tracks — their failure is handled silently
            from config import JINGLE_SERVER_HOST, JINGLE_SERVER_PORT
            jingle_uri = getattr(payload.track, 'uri', '')
            if JINGLE_SERVER_HOST and jingle_uri and f"{JINGLE_SERVER_HOST}:{JINGLE_SERVER_PORT}/jingles/" in jingle_uri:
                return
        except Exception as e:
            logger.error(f"Error in track exception event: {e}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload) -> None:
        """Handle track end event"""
        try:
            player: wavelink.Player = payload.player
            
            if not player:
                return

            reason: str = getattr(payload, "reason", "finished")
            logger.debug(f"Track ended: reason={reason}, track={getattr(payload.track, 'title', 'unknown')}")

            # Get the bot's player
            bot_player = self.bot.players.get(player.guild.id)

            if not bot_player:
                return

            # loadFailed means Lavalink couldn't stream the audio — skip to next track
            # (on_wavelink_track_exception already sent an error embed for non-jingle tracks)
            if reason == "loadFailed":
                logger.warning(
                    f"Track '{getattr(payload.track, 'title', 'unknown')}' failed to load/stream, skipping to next."
                )
                failed_uri = getattr(payload.track, 'uri', None)
                if failed_uri:
                    bot_player.failed_track_uris.add(failed_uri)

                next_track = bot_player.next_track()
                if next_track:
                    bot_player.current_track = next_track
                    bot_player.current_requester = getattr(next_track, 'requester', None)
                    await player.play(next_track)
                else:
                    bot_player.current_track = None

                channel = self._get_notification_channel(player.guild)
                if channel:
                    embed = EmbedBuilder.create_error_embed(
                        f"Failed to play **{getattr(payload.track, 'title', 'that track')}**. "
                        f"YouTube blocked the available stream variants for this result."
                    )
                    await channel.send(embed=embed)
                return

            # Handle loop modes
            if bot_player.loop_mode == "one":
                # Replay current track
                if bot_player.current_track:
                    await player.play(bot_player.current_track)
                    return

            # Get next track from queue
            next_track = bot_player.next_track()
            
            if next_track:
                bot_player.current_track = next_track
                bot_player.current_requester = getattr(next_track, 'requester', None)
                
                # Play the track (on_wavelink_track_start will post the now playing embed)
                await player.play(next_track)
                
                # Handle loop all
                if bot_player.loop_mode == "all":
                    bot_player.add_track(next_track)
            else:
                # Queue is empty
                if bot_player.autoplay and bot_player.current_track:
                    # Try to find and queue a related track
                    await self._queue_autoplay_track(player, bot_player)
                    return

                bot_player.current_track = None

                # Post queue ended message
                embed = EmbedBuilder.create_info_embed(
                    "📋 Queue Ended",
                    "All tracks have been played!"
                )

                message_id, channel_id = bot_player.get_controller_message()
                if message_id and channel_id:
                    try:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            await channel.send(embed=embed)
                    except Exception as e:
                        logger.error(f"Error posting queue ended message: {e}")
        
        except Exception as e:
            logger.error(f"Error in track end event: {e}")
    
    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload) -> None:
        """Handle track start event"""
        try:
            player: wavelink.Player = payload.player
            track: wavelink.Playable = payload.track
            
            if not player or not track:
                return
            
            # Get the bot's player
            bot_player = self.bot.players.get(player.guild.id)
            
            if not bot_player:
                return
            
            bot_player.current_track = track
            bot_player.played_tracks.add(track.uri)
            
            # Post now playing message
            await self.post_now_playing(player, track)
        
        except Exception as e:
            logger.error(f"Error in track start event: {e}")
    
    async def _queue_autoplay_track(self, player: wavelink.Player, bot_player) -> None:
        """Fetch a related track and play it for autoplay mode."""
        try:
            seed_track = bot_player.current_track
            artist = getattr(seed_track, "author", None) or ""
            title = getattr(seed_track, "title", None) or ""

            # Build a search query: "Artist mix" gives a good variety of related songs.
            # Fall back to title-based search if artist is unknown.
            if artist:
                query = f"ytsearch:{artist} mix"
            else:
                query = f"ytsearch:{title} mix"

            results, _ = await MusicSearch.search(query, search_type="youtube")

            # Pick a result that isn't the same track that just ended and hasn't been played before
            chosen = None
            for candidate in results:
                if candidate.uri != seed_track.uri and candidate.uri not in bot_player.played_tracks:
                    chosen = candidate
                    break

            if not chosen and results:
                chosen = results[0]

            if not chosen:
                bot_player.current_track = None
                logger.warning("Autoplay: no related track found")
                return

            bot_player.current_track = chosen
            await player.play(chosen)
            logger.info(f"Autoplay: queued related track '{chosen.title}' by '{chosen.author}'")
        except Exception as e:
            logger.error(f"Autoplay error: {e}")
            bot_player.current_track = None

    async def post_now_playing(
        self,
        player: wavelink.Player,
        track: wavelink.Playable
    ) -> None:
        """Post now playing embed with controller"""
        try:
            guild = player.guild
            bot_player = self.bot.players.get(guild.id)
            
            if not bot_player:
                return
            
            # Get controller channel (voice channel of the player)
            channel = None
            if player.channel:
                # Find a text channel to post the message
                for text_channel in guild.text_channels:
                    if text_channel.permissions_for(guild.me).send_messages:
                        channel = text_channel
                        break
            
            if not channel:
                return
            
            # Create now playing embed
            requester = bot_player.current_requester
            if requester:
                req_name = requester.display_name
                req_avatar = requester.display_avatar.url
            else:
                req_name = guild.me.display_name
                req_avatar = guild.me.avatar.url if guild.me.avatar else None
            embed = EmbedBuilder.create_now_playing(
                track,
                author_name=req_name,
                author_avatar=req_avatar
            )
            
            # Create controller view
            controller = PlayerController(
                self.bot,
                bot_player,
                guild.id
            )
            
            # Send message
            message = await channel.send(embed=embed, view=controller)
            bot_player.set_controller_message(message.id, channel.id)
        
        except Exception as e:
            logger.error(f"Error posting now playing: {e}")


    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player) -> None:
        """Disconnect and clean up the player when it becomes inactive"""
        try:
            guild_id = player.guild.id if player.guild else None
            await player.disconnect()
            if guild_id and guild_id in self.bot.players:
                del self.bot.players[guild_id]
            logger.info(f"Player for guild {guild_id} disconnected due to inactivity")
        except Exception as e:
            logger.error(f"Error disconnecting inactive player: {e}")


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(EventsCog(bot))
