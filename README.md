# Discord Music Bot

A feature-rich Discord music bot built with discord.py and Lavalink v4. Supports YouTube, Spotify, and more!

## Features

- 🎵 **Music Playback**: Play songs from YouTube, Spotify, and SoundCloud
- 🔍 **Smart Search**: Search with suggestions and track selection
- 📋 **Queue Management**: Add, remove, reorder tracks in the queue
- 🎮 **Player Controller**: Interactive buttons to control playback
- 📺 **Now Playing**: Beautiful embeds showing current track info
- 🔁 **Loop Modes**: Loop all tracks, loop one track, or no loop
- 🎧 **Volume Control**: Adjust player volume
- 📊 **Playlist Support**: Load entire playlists from YouTube and Spotify
- ⏯️ **Playback Control**: Play, pause, skip, stop functions
- 🎲 **Blackjack** (Coming soon!)
- 📻 **Radio Jingle** (Configurable)

## Commands

### Music Commands
- `/play <song/URL>` - Search and play a song
- `/pause` - Pause or resume playback
- `/stop` - Stop playback and clear queue
- `/queue [page]` - View the current queue
- `/move <from> <to>` - Move a track in the queue
- `/playlist <URL/query>` - Load a playlist

## Project Structure

```
PYTHON MUSIC BOT/
├── bot.py                 # Main bot entry point
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
│
├── cogs/                  # Command modules (organized by feature)
│   ├── __init__.py
│   ├── play.py           # /play command
│   ├── pause.py          # /pause command
│   ├── stop.py           # /stop command
│   ├── queue.py          # /queue command
│   ├── move.py           # /move command
│   ├── playlist.py       # /playlist command
│   └── events.py         # Music player events
│
└── utils/                 # Utility modules
    ├── __init__.py
    ├── search.py         # Music search functionality
    ├── player.py         # Queue and player management
    ├── embed_builder.py  # Discord embed creation
    └── music_player_view.py  # Interactive player controller
```

## Setup Instructions

### Prerequisites

- Python 3.8+
- A Discord bot token
- Lavalink v4 server running
- Spotify API credentials (optional, for Spotify support)

### Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment:**
   - Copy `.env.example` to `.env`
   - Fill in your Discord token, Lavalink credentials, and Spotify API keys
   - Set your radio jingle URL (optional)

3. **Setup Lavalink Server:**
   - Download Lavalink from [here](https://github.com/lavalink-devs/Lavalink)
   - Configure `application.yml` with your settings (default: localhost:2333)
   - Run the Lavalink server: `java -jar Lavalink.jar`

4. **Run the bot:**
```bash
python bot.py
```

## Configuration

Edit `config.py` to customize:
- Default volume (0-100)
- Max queue size
- Search results count
- Embed colors
- Radio jingle URL

### Environment Variables (.env)

```
DISCORD_TOKEN=your_discord_bot_token
LAVALINK_HOST=localhost
LAVALINK_PORT=2333
LAVALINK_PASSWORD=youshallnotpass
SPOTIFY_CLIENT_ID=your_spotify_id
SPOTIFY_CLIENT_SECRET=your_spotify_secret
```

## Adding New Features

The modular structure makes it easy to add new commands:

1. **Create a new cog file** in `cogs/` folder:
```python
# cogs/your_feature.py
import discord
from discord.ext import commands
from discord import app_commands

class YourFeatureCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="yourcommand")
    async def your_command(self, interaction: discord.Interaction):
        # Your command logic here
        pass

async def setup(bot):
    await bot.add_cog(YourFeatureCog(bot))
```

2. The cog will be automatically loaded by the bot!

## Upcoming Features

- 🎲 **Blackjack**: Full blackjack game integrated into Discord
- 🎙️ **Radio**: Stream radio stations
- 📀 **Lyrics**: Display song lyrics
- ⭐ **Favorites**: Save favorite tracks
- 👥 **Multi-language**: Support multiple languages

## Troubleshooting

### Bot not connecting to Lavalink
- Ensure Lavalink server is running
- Check host and port in `.env` file
- Verify Lavalink password

### No music playing
- Ensure bot is in voice channel
- Check if Lavalink is running
- Verify the track URL is valid

### Search not working
- Check internet connection
- Ensure YouTube/Spotify access is available
- Verify API credentials for Spotify

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is open source and available under the MIT License.

## Support

For issues and questions, please create an issue on the project repository.

---

Made with ❤️ for Discord music lovers
