"""
Main Discord Music Bot Entry Point
"""
import discord
from discord.ext import commands
import wavelink
import os
import logging
import json
from config import DISCORD_TOKEN, LAVALINK_HOST, LAVALINK_PORT, LAVALINK_PASSWORD

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Patch wavelink.Player._dispatch_voice_update to inject channelId required by Lavalink v4
try:
    from wavelink.player import Player as _WavelinkPlayer
    from wavelink.exceptions import LavalinkException
    _original_dispatch = _WavelinkPlayer._dispatch_voice_update

    async def _patched_dispatch_voice_update(self):
        """Inject channelId into the voice state payload before sending to Lavalink v4"""
        assert self.guild is not None
        data = self._voice_state["voice"]

        session_id = data.get("session_id")
        token = data.get("token")
        endpoint = data.get("endpoint")

        if not session_id or not token or not endpoint:
            return

        channel_id = str(self.channel.id) if self.channel else None
        if not channel_id:
            logger.warning("[Lavalink v4 Fix] channelId unavailable, cannot dispatch voice update")
            return

        request = {
            "voice": {
                "sessionId": session_id,
                "token": token,
                "endpoint": endpoint,
                "channelId": channel_id,
            }
        }
        logger.debug(f"[Lavalink v4 Fix] Injecting channelId {channel_id} for guild {self.guild.id}")

        try:
            await self.node._update_player(self.guild.id, data=request)
        except LavalinkException:
            await self.disconnect()
        else:
            self._connection_event.set()

    _WavelinkPlayer._dispatch_voice_update = _patched_dispatch_voice_update
    logger.info("Applied Lavalink v4 compatibility patch: channelId injection into voice update")
except Exception as e:
    logger.warning(f"Could not apply Lavalink compatibility patch: {e}")

# Create bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents)

# Store active players
bot.players = {}


async def load_cogs():
    """Load all cogs from the cogs directory"""
    cogs_dir = "cogs"
    if not os.path.exists(cogs_dir):
        os.makedirs(cogs_dir)
    
    for filename in os.listdir(cogs_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                logger.info(f"Loaded cog: {filename[:-3]}")
            except Exception as e:
                logger.error(f"Failed to load cog {filename[:-3]}: {e}")


async def setup_lavalink():
    """Setup Wavelink connection to Lavalink server"""
    try:
        logger.info(f"Attempting to connect to Lavalink at ws://{LAVALINK_HOST}:{LAVALINK_PORT}")
        node: wavelink.Node = wavelink.Node(
            uri=f"ws://{LAVALINK_HOST}:{LAVALINK_PORT}",
            password=LAVALINK_PASSWORD,
        )
        await wavelink.Pool.connect(nodes=[node], client=bot)
        logger.info("Connected to Lavalink server")
    except Exception as e:
        logger.error(f"Failed to connect to Lavalink: {e}", exc_info=True)


@bot.event
async def on_ready():
    """Bot ready event"""
    logger.info(f"Bot logged in as {bot.user}")
    logger.info(f"Bot ID: {bot.user.id}")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.listening, name="/play")
    )
    
    # Setup Lavalink after bot is ready
    if not hasattr(bot, 'lavalink_connected'):
        await setup_lavalink()
        bot.lavalink_connected = True


@bot.event
async def on_wavelink_node_ready(node: wavelink.Node) -> None:
    """Lavalink node ready event"""
    logger.info(f"Lavalink node is ready!")


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """Ensure voice state updates propagate to Lavalink properly"""
    # If it's not the bot, ignore
    if member != member.guild.me:
        return
    
    guild = member.guild
    
    # If bot joined a channel
    if before.channel is None and after.channel is not None:
        logger.info(f"Voice state update: Bot joined {after.channel.name} (ID: {after.channel.id})")
        # Get the player and ensure it knows about the channel
        player = guild.voice_client
        if isinstance(player, wavelink.Player):
            player.channel = after.channel
            logger.info(f"Set Wavelink player channel to {after.channel.name} (ID: {after.channel.id})")
    
    # If bot left a channel
    elif before.channel is not None and after.channel is None:
        logger.info(f"Voice state update: Bot left voice channel")


@bot.event
async def on_raw_socket_receive(payload):
    """
    This event fires when a raw socket payload is received from Discord.
    We use this to monitor but not interfere with normal operations.
    """
    pass


async def main():
    """Main function"""
    async with bot:
        # Load all cogs first (before starting bot)
        await load_cogs()
        
        # Start the bot (Lavalink setup will happen in on_ready)
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    import asyncio
    
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        exit(1)
    
    asyncio.run(main())

