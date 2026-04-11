"""
Configuration module for the Discord Music Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Settings
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_PREFIX = "/"

# Lavalink Server Settings
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "localhost")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

# Spotify Settings
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")

# Music Bot Settings
DEFAULT_VOLUME = 100
MAX_QUEUE_SIZE = 1000
SEARCH_RESULTS_COUNT = 5
RADIO_JINGLE_URL = "https://www.youtube.com/watch?v=yx28m-M--4Q"

# Colors for embeds
COLORS = {
    "primary": 0x1DB954,  # Spotify green
    "success": 0x00FF00,
    "error": 0xFF0000,
    "info": 0x0099FF,
}
