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
from config import RADIO_JINGLE_URL, LAVALINK_HOST, LAVALINK_PORT, LAVALINK_PASSWORD

logger = logging.getLogger(__name__)


class EventsCog(commands.Cog):
    """Handle music player events"""
    
    def __init__(self, bot):
        self.bot = bot
        self._voice_updates = {}  # Track pending voice updates
    
    @commands.Cog.listener()
    async def on_connect(self):
        """Initialize bot connection handler"""
        logger.info("Bot connected to Discord")
    
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload) -> None:
        """Called when a Lavalink node is ready"""
        logger.info(f"Wavelink node is ready")
    
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload) -> None:
        """Handle track end event"""
        try:
            player: wavelink.Player = payload.player
            
            if not player:
                return
            
            # Get the bot's player
            bot_player = self.bot.players.get(player.guild.id)
            
            if not bot_player:
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
                
                # Post now playing message
                await self.post_now_playing(player, next_track)
                
                # Play the track
                await player.play(next_track)
                
                # Handle loop all
                if bot_player.loop_mode == "all":
                    bot_player.add_track(next_track)
            else:
                # Queue is empty
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
            
            # Post now playing message
            await self.post_now_playing(player, track)
        
        except Exception as e:
            logger.error(f"Error in track start event: {e}")
    
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
            embed = EmbedBuilder.create_now_playing(
                track,
                author_name=guild.me.name,
                author_avatar=guild.me.avatar.url if guild.me.avatar else None
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
