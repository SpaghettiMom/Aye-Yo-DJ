"""
Main Discord Music Bot Entry Point
"""
import asyncio
import discord
from discord.ext import commands, tasks
import wavelink
import os
import logging
import json
import aiohttp
from config import (
    DISCORD_TOKEN,
    LAVALINK_HOST,
    LAVALINK_PORT,
    LAVALINK_PASSWORD,
    JINGLE_DIR,
    JINGLE_SERVER_PORT,
    POTOKEN_GENERATOR_URL,
    POTOKEN_REFRESH_INTERVAL_MINUTES,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Patch wavelink.Player._dispatch_voice_update to inject channelId required by Lavalink v4
async def _reconnect_lavalink_node(node) -> None:
    """Re-establish the websocket connection to Lavalink after a session-expiry 404."""
    try:
        logger.info("[Lavalink v4 Fix] Reconnecting node after session expiry (404)…")
        if node._websocket is not None:
            try:
                await node._websocket.cleanup()
            except Exception:
                pass
        node._has_closed = False
        node._session_id = None
        await node._connect(client=None)
        logger.info("[Lavalink v4 Fix] Node reconnect initiated successfully")
    except Exception as exc:
        logger.error(f"[Lavalink v4 Fix] Node reconnect failed: {exc}")


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
        except LavalinkException as exc:
            if exc.status == 404:
                # Session is stale (Lavalink restarted) — reconnect the node
                logger.warning(
                    f"[Lavalink v4 Fix] Lavalink session expired (404) for guild {self.guild.id}, reconnecting node"
                )
                asyncio.create_task(_reconnect_lavalink_node(self.node))
            else:
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


@tasks.loop(minutes=POTOKEN_REFRESH_INTERVAL_MINUTES)
async def refresh_potoken_task():
    """Fetch a fresh poToken/visitorData from the bgutil-ytdlp-pot-provider service
    and push it to Lavalink's youtube-source plugin over its REST API, so tokens
    never go stale without needing to restart Lavalink."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{POTOKEN_GENERATOR_URL}/get_pot",
                json={},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(f"[PoToken] Generator not ready yet (status {resp.status}): {body}")
                    return
                data = await resp.json(content_type=None)

            po_token = data.get("poToken")
            visitor_data = data.get("contentBinding")
            if not po_token or not visitor_data:
                logger.warning("[PoToken] Generator response missing poToken/contentBinding")
                return

            headers = {"Authorization": LAVALINK_PASSWORD, "Content-Type": "application/json"}
            payload = {"poToken": po_token, "visitorData": visitor_data}
            url = f"http://{LAVALINK_HOST}:{LAVALINK_PORT}/youtube"
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 204:
                    logger.info("[PoToken] Refreshed poToken/visitorData on Lavalink")
                else:
                    body = await resp.text()
                    logger.warning(f"[PoToken] Lavalink rejected update (status {resp.status}): {body}")
    except Exception as e:
        logger.error(f"[PoToken] Failed to refresh poToken: {e}")


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

    # Start automatic poToken refresh loop (idempotent)
    if not refresh_potoken_task.is_running():
        refresh_potoken_task.start()


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

