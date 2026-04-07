# Bot Architecture & Extension Guide

## Overview

This bot is built with a modular, scalable architecture that makes it easy to add new features.

## File Structure Explanation

### Core Files
- **`bot.py`** - Main entry point. Initializes the bot, sets up Lavalink connection, and loads all cogs
- **`config.py`** - Centralized configuration for all settings (tokens, colors, limits, etc.)
- **`requirements.txt`** - All Python dependencies

### Command Structure (cogs/)

Each command is a separate file (cog) for easy management:

#### Music Commands
- **`play.py`** - `/play <query>` - Music search and playback
  - Handles searching across sources
  - Shows suggestions with interactive selection
  - Manages initial playback

- **`pause.py`** - `/pause` - Toggle play/pause
  - Simple pause/resume toggle

- **`stop.py`** - `/stop` - Stop playback
  - Stops current track
  - Clears the queue

- **`queue.py`** - `/queue [page]` - View queue
  - Paginated queue display
  - Shows track info and duration

- **`move.py`** - `/move <from> <to>` - Rearrange queue
  - Reorder tracks in queue
  - 1-based index position

- **`playlist.py`** - `/playlist <url>` - Load playlists
  - Support for YouTube and Spotify playlists
  - Batch add multiple tracks

#### System Commands
- **`events.py`** - Internal event handlers
  - Track end events
  - Track start events
  - Automatic next track playing
  - Loop mode handling

### Utility Modules (utils/)

- **`search.py`** - Music search engine
  - `MusicSearch.search()` - Search across sources
  - `MusicSearch.get_suggestions()` - Get search suggestions
  - `MusicSearch.get_track_by_url()` - Direct URL lookup

- **`player.py`** - Queue and player state management
  - `MusicPlayer` class handles all queue operations
  - Track management (add, remove, move)
  - Volume and loop mode control
  - Pause state tracking

- **`embed_builder.py`** - Discord embed creation
  - Pre-built embed templates
  - Consistent formatting
  - Color themes

- **`music_player_view.py`** - Interactive player controller
  - `PlayerController` class with buttons
  - Play/Pause, Skip, Stop buttons
  - Queue and Shuffle buttons

- **`blackjack.py`** - Blackjack game template (for future use)
  - Ready for implementation

## How Commands Work

### Command Flow Example: /play

1. User runs `/play taylor swift love story`
2. `cogs/play.py` receives the command
3. Checks if user is in voice channel
4. Connects bot to voice channel (if not connected)
5. Gets or creates `MusicPlayer` for the guild
6. Calls `MusicSearch.get_suggestions()` to find tracks
7. Shows embed with search results and select menu
8. User selects a track
9. Track is added to `MusicPlayer.queue`
10. Bot connects to Lavalink and starts playback
11. `cogs/events.py` listens for track events
12. When track ends, next track is automatically played

### Key Classes

#### MusicPlayer (utils/player.py)
```python
player = MusicPlayer(guild_id=123456)
player.add_track(track)              # Add single track
player.add_tracks(tracks)            # Add multiple tracks
player.next_track()                  # Get next from queue
player.remove_track(index)           # Remove by position
player.move_track(from_idx, to_idx)  # Reorder queue
player.set_loop_mode("one")          # "off", "one", "all"
player.set_volume(80)                # 0-100
```

#### MusicSearch (utils/search.py)
```python
results, source = await MusicSearch.search("song_name")
suggestions = await MusicSearch.get_suggestions("song_name", limit=5)
track = await MusicSearch.get_track_by_url("spotify_url")
```

#### EmbedBuilder (utils/embed_builder.py)
```python
embed = EmbedBuilder.create_now_playing(track)
embed = EmbedBuilder.create_queue_embed(queue_list)
embed = EmbedBuilder.create_search_result()
embed = EmbedBuilder.create_error_embed("message")
```

## Adding New Commands

### Example: Adding a /lyrics command

1. **Create `cogs/lyrics.py`:**
```python
import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class LyricsCog(commands.Cog):
    """Get song lyrics command"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(
        name="lyrics",
        description="Get lyrics for current or specified song"
    )
    @app_commands.describe(song="Song name (optional, uses current if not specified)")
    async def lyrics(self, interaction: discord.Interaction, song: str = None):
        """Get song lyrics"""
        await interaction.response.defer()
        
        # Your implementation here
        pass

async def setup(bot):
    """Load the cog"""
    await bot.add_cog(LyricsCog(bot))
```

2. The cog is automatically loaded! No other changes needed.

### Example: Adding a utility function

1. **Create or edit a file in `utils/`:**
```python
class MyUtility:
    @staticmethod
    async def do_something():
        # Logic here
        pass
```

2. **Import and use in your cog:**
```python
from utils.my_utility import MyUtility

result = await MyUtility.do_something()
```

## Accessing Bot Resources

### From within a cog:
```python
# Get player for guild
player = self.bot.players.get(interaction.guild_id)

# Get voice client
voice_client = interaction.guild.voice_client

# All bot commands
all_cogs = self.bot.cogs

# Guild/user info
guild = interaction.guild
user = interaction.user
```

## Adding New Features to Existing Commands

### Example: Add volume control to /play

Edit `cogs/play.py`:
```python
@app_commands.describe(volume="Volume level 0-100")
async def play(self, interaction, query, source="youtube", volume: int = 100):
    # ... existing code ...
    player.set_volume(volume)
```

### Example: Add favorite tracks

1. Create `utils/favorites.py`:
```python
class FavoritesManager:
    def __init__(self):
        self.favorites = {}  # user_id: [tracks]
    
    def add_favorite(self, user_id, track):
        if user_id not in self.favorites:
            self.favorites[user_id] = []
        self.favorites[user_id].append(track)
```

2. Create `cogs/favorites.py`:
```python
@app_commands.command(name="favorite", description="Save current track")
async def favorite(self, interaction):
    # Get current track and save
    pass
```

## Configuration Management

All settings are in `config.py`. To add a new setting:

```python
# In config.py
MY_NEW_SETTING = os.getenv("MY_NEW_SETTING", "default_value")

# In .env
MY_NEW_SETTING=my_value
```

## Event System

The bot responds to Lavalink events in `cogs/events.py`:

- `on_wavelink_track_end` - When track finishes
- `on_wavelink_track_start` - When track starts
- `on_wavelink_node_ready` - When Lavalink connects
- `on_ready` - When bot starts up

Add more listeners by creating methods in EventsCog:
```python
@commands.Cog.listener()
async def on_your_event(self, payload):
    # Your logic
    pass
```

## Data Persistence

Currently, all data is stored in memory (resets on bot restart).

To add persistence:
1. Use SQLite with `sqlite3` or `aiosqlite`
2. Or use a database like PostgreSQL
3. Store in JSON files for simple data
4. Use Discord's reaction system for user preferences

Example with JSON:
```python
import json

class DataManager:
    def save_data(self, key, data):
        with open("data.json", "w") as f:
            json.dump({key: data}, f)
```

## Performance Considerations

### Current Optimizations:
- Queue uses `deque` for O(1) operations
- Pagination for large queues
- Lazy loading of search results
- Efficient Wavelink pooling

### Future Optimizations:
- Cache search results
- Pre-fetch next track while current plays
- Implement rate limiting
- Use slash command options for better UX

## Common Tasks

### Get current playing track:
```python
player = bot.players.get(guild_id)
current = player.current_track
```

### Clear queue:
```python
player.clear_queue()
```

### Check if paused:
```python
is_paused = player.is_player_paused()
```

### Send an embed:
```python
from utils.embed_builder import EmbedBuilder
embed = EmbedBuilder.create_success_embed("Title", "Description")
await interaction.response.send_message(embed=embed)
```

## Debugging

1. Enable logging in `bot.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```

2. Check console output for errors
3. Use Discord's developer mode to inspect messages
4. Test commands directly in a private server

## Deployment

### Local Testing:
```bash
python bot.py
```

### Production:
- Use a cloud host (AWS, Heroku, DigitalOcean, etc.)
- Set environment variables on the hosting platform
- Use process manager (PM2, systemd, etc.)
- Keep Lavalink running on a separate server or process

---

You now have a solid foundation to build upon! Happy coding! 🚀
