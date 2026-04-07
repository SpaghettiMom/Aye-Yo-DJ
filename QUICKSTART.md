# Quick Start Guide

## 1. Initial Setup

### Step 1: Create Discord Bot
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token
5. Under "OAuth2" > "URL Generator", select:
   - Scopes: `bot`
   - Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Manage Messages`, `Connect`, `Speak`
6. Copy the generated URL and invite the bot to your server

### Step 2: Get Lavalink Running
1. Download [Lavalink](https://github.com/lavalink-devs/Lavalink/releases)
2. Extract the files
3. Create/edit `application.yml`:
   ```yaml
   server:
     port: 2333
     address: localhost
   lavalink:
     server:
       password: "youshallnotpass"
   ```
4. Run: `java -jar Lavalink.jar`
5. Keep this running in a terminal while using the bot

### Step 3: Setup Bot
1. Navigate to the bot directory:
   ```bash
   cd "c:\Users\isaac\Desktop\PYTHON MUSIC BOT"
   ```

2. Create Python virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create `.env` file:
   ```
   DISCORD_TOKEN=your_bot_token_here
   LAVALINK_HOST=localhost
   LAVALINK_PORT=2333
   LAVALINK_PASSWORD=youshallnotpass
   SPOTIFY_CLIENT_ID=
   SPOTIFY_CLIENT_SECRET=
   ```

5. Run the bot:
   ```bash
   python bot.py
   ```

## 2. Using the Bot

### Basic Commands
```
/play song_name              - Search and play a song
/pause                       - Pause/resume playback
/stop                        - Stop and clear queue
/queue [page]               - View the queue
/move <from> <to>           - Move track in queue
/playlist <url>             - Load entire playlist
```

### Search Tips
- Song name: `/play let it be`
- Artist + Song: `/play the beatles let it be`
- YouTube URL: `/play https://www.youtube.com/watch?v=...`
- Spotify: Use `/play song_name source:spotify`

## 3. Optional: Spotify Support

If you want to support Spotify searches:

1. Go to [Spotify Developer](https://developer.spotify.com/dashboard)
2. Create an app
3. Get your Client ID and Client Secret
4. Add them to `.env`:
   ```
   SPOTIFY_CLIENT_ID=your_id
   SPOTIFY_CLIENT_SECRET=your_secret
   ```

## 4. Customization

### Change Radio Jingle
Edit `config.py` and set:
```python
RADIO_JINGLE_URL = "your_youtube_or_spotify_url"
```

### Change Theme Colors
Edit the `COLORS` dict in `config.py`:
```python
COLORS = {
    "primary": 0x1DB954,  # Spotify green
    "success": 0x00FF00,
    "error": 0xFF0000,
    "info": 0x0099FF,
}
```

### Add More Commands
Create a new file in `cogs/` folder and follow the pattern in existing cogs.

## 5. Troubleshooting

### "No module named 'discord'"
- Make sure virtual environment is activated
- Run: `pip install -r requirements.txt`

### "Failed to connect to Lavalink"
- Check if Lavalink server is running
- Verify host/port in `.env` matches Lavalink config
- Check Lavalink password

### Bot doesn't respond
- Check if bot has permissions in the channel
- Make sure Lavalink is running
- Check console for error messages

### Music doesn't play
- User must be in a voice channel
- Bot must have permission to join voice
- Check if tracks are being added to queue

## 6. Next Steps

- Customize the bot prefix and commands
- Add more features (lyrics, recommendations, etc.)
- Implement the Blackjack feature
- Add database support for user preferences
- Create a web dashboard

## 7. Useful Resources

- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [Lavalink Documentation](https://lavalink.dev/)
- [Wavelink Documentation](https://wavelink.dev/)
- [Discord.py GitHub](https://github.com/Rapptz/discord.py)

---

Good luck with your music bot! 🎵
