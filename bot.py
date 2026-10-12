"""
Main Discord Music Bot Entry Point
"""
import asyncio
import discord
from discord.ext import commands
import wavelink
from wavelink.exceptions import LavalinkException
import os
import logging
import json
from config import (
    DISCORD_TOKEN,
    LAVALINK_HOST,
    LAVALINK_PORT,
    LAVALINK_PASSWORD,
    JINGLE_DIR,
    JINGLE_SERVER_PORT,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def _dispatch_voice_update_with_channel_id(self: wavelink.Player) -> None:
    """Send the Lavalink v4 voice payload required by Lavalink 4.2.2.

    Wavelink 3.4.1 omits ``channelId``, while the Lavalink server used by this
    project requires it for every voice update.
    """
    assert self.guild is not None

    voice = self._voice_state["voice"]
    session_id = voice.get("session_id")
    token = voice.get("token")
    endpoint = voice.get("endpoint")
    channel_id = getattr(self.channel, "id", None)

    if not session_id or not token or not endpoint or not channel_id:
        logger.debug(
            "Waiting for complete Discord voice state for guild %s "
            "(session=%s, token=%s, endpoint=%s, channel=%s)",
            self.guild.id,
            bool(session_id),
            bool(token),
            bool(endpoint),
            bool(channel_id),
        )
        return

    request = {
        "voice": {
            "sessionId": session_id,
            "token": token,
            "endpoint": endpoint,
            "channelId": str(channel_id),
        }
    }

    try:
        await self.node._update_player(self.guild.id, data=request)
    except LavalinkException as exc:
        logger.error(
            "Lavalink rejected the voice update for guild %s: %s",
            self.guild.id,
            exc,
        )
        await self.disconnect()
        return

    self._connection_event.set()
    logger.info("Sent Lavalink voice update with channelId for guild %s", self.guild.id)


# Lavalink 4.2.2 requires voice.channelId; Wavelink 3.4.1 does not send it.
wavelink.Player._dispatch_voice_update = _dispatch_voice_update_with_channel_id
logger.info("Applied Lavalink 4.2.2 voice channelId compatibility patch")

# Create bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents)

# Store active players
bot.players = {}

# Jingle toggle — admins can flip this at runtime via /jingle
bot.jingle_enabled = True


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


async def start_jingle_server():
    """Serve local jingle files over HTTP so Lavalink can fetch them."""
    import aiohttp.web as web
    if not os.path.exists(JINGLE_DIR):
        os.makedirs(JINGLE_DIR)
        logger.info(f"Created jingles directory: {JINGLE_DIR}")
    app = web.Application()
    app.router.add_static('/jingles', JINGLE_DIR, show_index=False)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', JINGLE_SERVER_PORT)
    await site.start()
    logger.info(f"Jingle file server started on port {JINGLE_SERVER_PORT} serving '{JINGLE_DIR}/'")


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
    
    # Sync slash commands with Discord so autocomplete is registered
    if not hasattr(bot, 'commands_synced'):
        synced = await bot.tree.sync()
        bot.commands_synced = True
        logger.info(f"Synced {len(synced)} slash command(s) with Discord")

    # Setup Lavalink after bot is ready
    if not hasattr(bot, 'lavalink_connected'):
        await setup_lavalink()
        bot.lavalink_connected = True

    # Start jingle file server (idempotent)
    if not hasattr(bot, 'jingle_server_started'):
        await start_jingle_server()
        bot.jingle_server_started = True


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

