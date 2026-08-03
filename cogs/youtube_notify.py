"""
YouTube channel notification cog
Handles: /youtube subscribe, /youtube unsubscribe, /youtube list

Polls YouTube RSS feeds every 5 minutes and announces new videos in the
configured Discord channel. No YouTube API key required.
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import xml.etree.ElementTree as ET
import json
import os
import re
import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

SUBSCRIPTIONS_FILE = "data/youtube_subscriptions.json"
YOUTUBE_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
POLL_INTERVAL = 300  # seconds (5 minutes)

# XML namespaces used in YouTube RSS feeds
ATOM_NS = "http://www.w3.org/2005/Atom"
YT_NS = "http://www.youtube.com/xml/schemas/2015"
MEDIA_NS = "http://search.yahoo.com/mrss/"


class YouTubeNotifyCog(commands.Cog):
    """YouTube new-video announcement system"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.subscriptions: dict = self._load_subscriptions()
        self.check_new_videos.start()

    def cog_unload(self):
        self.check_new_videos.cancel()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_subscriptions(self) -> dict:
        if os.path.exists(SUBSCRIPTIONS_FILE):
            try:
                with open(SUBSCRIPTIONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load YouTube subscriptions: {e}")
        return {}

    def _save_subscriptions(self):
        try:
            with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.subscriptions, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save YouTube subscriptions: {e}")

    # ------------------------------------------------------------------
    # YouTube helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _resolve_channel(
        session: aiohttp.ClientSession, url_or_id: str
    ) -> tuple[str, str]:
        """
        Given a YouTube channel URL, @handle, or raw UCxxxxxx channel ID,
        return (channel_id, channel_name).

        Raises ValueError if the channel cannot be resolved.
        """
        stripped = url_or_id.strip()

        # Bare channel ID already provided
        if re.match(r"^UC[a-zA-Z0-9_\-]{22}$", stripped):
            return await YouTubeNotifyCog._fetch_channel_name(session, stripped)

        # Build a full URL if only a path/handle was given
        if not stripped.startswith("http"):
            stripped = "https://www.youtube.com/" + stripped.lstrip("/")

        # Direct /channel/UCxxxxxx URL — extract ID without a page fetch
        m = re.search(r"youtube\.com/channel/(UC[a-zA-Z0-9_\-]{22})", stripped)
        if m:
            return await YouTubeNotifyCog._fetch_channel_name(session, m.group(1))

        # @handle or /c/name — scrape the page for the channel ID
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        async with session.get(
            stripped, headers=headers, allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status != 200:
                raise ValueError(
                    f"Could not reach the YouTube page (HTTP {resp.status}). "
                    "Try using the full channel URL, e.g. https://www.youtube.com/channel/UCxxxxxx"
                )
            html = await resp.text()

        # The RSS <link> tag in the page <head> always belongs to the channel being viewed.
        # This is far more reliable than generic "channelId" keys which appear for
        # recommended/related channels throughout the page JSON.
        for pattern in (
            r'feeds/videos\.xml\?channel_id=(UC[a-zA-Z0-9_\-]{22})',  # RSS link tag (most reliable)
            r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_\-]{22})"',           # page metadata externalId
            r'"channelId"\s*:\s*"(UC[a-zA-Z0-9_\-]{22})"',            # fallback — may pick wrong channel
        ):
            m = re.search(pattern, html)
            if m:
                return await YouTubeNotifyCog._fetch_channel_name(session, m.group(1))

        raise ValueError(
            "Could not extract a YouTube channel ID from the provided input. "
            "Try using the full channel URL (e.g. https://www.youtube.com/channel/UCxxxxxx)."
        )

    @staticmethod
    async def _fetch_channel_name(
        session: aiohttp.ClientSession, channel_id: str
    ) -> tuple[str, str]:
        """Return (channel_id, channel_name) by reading the channel's RSS feed title."""
        url = YOUTUBE_RSS_URL.format(channel_id=channel_id)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                raise ValueError(
                    f"No YouTube RSS feed found for channel ID `{channel_id}`. "
                    "Make sure the channel ID is correct."
                )
            xml_text = await resp.text()

        root = ET.fromstring(xml_text)
        title_el = root.find(f"{{{ATOM_NS}}}title")
        name = title_el.text if title_el is not None else channel_id
        return channel_id, name

    @staticmethod
    async def _get_latest_video(
        session: aiohttp.ClientSession, channel_id: str
    ) -> Optional[dict]:
        """
        Fetch the most recent video from the channel's RSS feed.
        Returns a dict or None if the feed is empty / unreachable.
        """
        url = YOUTUBE_RSS_URL.format(channel_id=channel_id)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                xml_text = await resp.text()
        except Exception as e:
            logger.warning(f"Failed to fetch RSS for {channel_id}: {e}")
            return None

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse RSS XML for {channel_id}: {e}")
            return None

        entry = root.find(f"{{{ATOM_NS}}}entry")
        if entry is None:
            return None

        video_id_el = entry.find(f"{{{YT_NS}}}videoId")
        title_el = entry.find(f"{{{ATOM_NS}}}title")
        link_el = entry.find(f"{{{ATOM_NS}}}link[@rel='alternate']")
        published_el = entry.find(f"{{{ATOM_NS}}}published")
        thumbnail_el = entry.find(
            f"{{{MEDIA_NS}}}group/{{{MEDIA_NS}}}thumbnail"
        )
        channel_title_el = root.find(f"{{{ATOM_NS}}}title")

        video_id = video_id_el.text if video_id_el is not None else None
        if not video_id:
            return None

        return {
            "video_id": video_id,
            "title": title_el.text if title_el is not None else "Unknown Title",
            "url": (
                link_el.get("href")
                if link_el is not None
                else f"https://youtu.be/{video_id}"
            ),
            "thumbnail": thumbnail_el.get("url") if thumbnail_el is not None else None,
            "published": published_el.text if published_el is not None else None,
            "channel_name": (
                channel_title_el.text if channel_title_el is not None else channel_id
            ),
        }

    # ------------------------------------------------------------------
    # Background poll loop
    # ------------------------------------------------------------------

    @tasks.loop(seconds=POLL_INTERVAL)
    async def check_new_videos(self):
        """Poll every YouTube subscription and announce any new uploads."""
        if not self.subscriptions:
            return

        async with aiohttp.ClientSession() as session:
            for guild_id, subs in list(self.subscriptions.items()):
                guild = self.bot.get_guild(int(guild_id))
                if guild is None:
                    continue

                changed = False
                for sub in subs:
                    latest = await self._get_latest_video(session, sub["yt_channel_id"])
                    if latest is None:
                        continue

                    new_id = latest["video_id"]
                    if sub.get("last_video_id") == new_id:
                        continue  # No new video

                    sub["last_video_id"] = new_id
                    changed = True

                    discord_channel = guild.get_channel(int(sub["discord_channel_id"]))
                    if not isinstance(discord_channel, discord.TextChannel):
                        continue

                    embed = self._build_announce_embed(latest)
                    try:
                        await discord_channel.send(
                            content=f"🎥 **{latest['channel_name']}** just posted a new video!",
                            embed=embed,
                        )
                        logger.info(
                            f"Announced new video '{latest['title']}' "
                            f"from {latest['channel_name']} in guild {guild_id}"
                        )
                    except discord.Forbidden:
                        logger.warning(
                            f"Missing permissions to post in channel {discord_channel.id} "
                            f"(guild {guild_id})"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send YouTube notification: {e}")

                if changed:
                    self._save_subscriptions()

    @check_new_videos.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @check_new_videos.error
    async def check_new_videos_error(self, error: Exception):
        logger.error(f"Error in check_new_videos loop: {error}", exc_info=error)

    # ------------------------------------------------------------------
    # Embed builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_announce_embed(video: dict) -> discord.Embed:
        embed = discord.Embed(
            title=video["title"],
            url=video["url"],
            color=0xFF0000,  # YouTube red
            timestamp=datetime.now(),
        )
        embed.set_author(
            name=video["channel_name"],
            url=f"https://www.youtube.com/channel/{video.get('channel_id', '')}",
        )
        if video.get("thumbnail"):
            embed.set_image(url=video["thumbnail"])
        if video.get("published"):
            try:
                pub = datetime.fromisoformat(video["published"].replace("Z", "+00:00"))
                embed.set_footer(
                    text=f"Published {pub.strftime('%B %d, %Y at %I:%M %p UTC')}"
                )
            except ValueError:
                pass
        return embed

    # ------------------------------------------------------------------
    # Slash commands  (/youtube subscribe | unsubscribe | list)
    # ------------------------------------------------------------------

    youtube = app_commands.Group(
        name="youtube",
        description="Manage YouTube channel upload notifications",
    )

    @youtube.command(
        name="subscribe",
        description="Subscribe a Discord channel to get alerts when a YouTube channel posts",
    )
    @app_commands.describe(
        youtube_channel=(
            "YouTube channel URL or @handle "
            "(e.g. https://youtube.com/@MrBeast or @MrBeast)"
        ),
        discord_channel="Discord channel where new video alerts will be posted",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def subscribe(
        self,
        interaction: discord.Interaction,
        youtube_channel: str,
        discord_channel: discord.TextChannel,
    ):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)

        async with aiohttp.ClientSession() as session:
            try:
                yt_id, yt_name = await self._resolve_channel(session, youtube_channel)
            except ValueError as e:
                await interaction.followup.send(f"❌ {e}", ephemeral=True)
                return

            subs: list = self.subscriptions.setdefault(guild_id, [])

            # Prevent duplicate subscriptions
            for existing in subs:
                if existing["yt_channel_id"] == yt_id:
                    await interaction.followup.send(
                        f"❌ Already subscribed to **{yt_name}**. "
                        f"Use `/youtube unsubscribe` first if you want to change the channel.",
                        ephemeral=True,
                    )
                    return

            # Seed last_video_id with the current latest video so we don't
            # immediately announce every recent upload.
            latest = await self._get_latest_video(session, yt_id)

        subs.append(
            {
                "yt_channel_id": yt_id,
                "yt_channel_name": yt_name,
                "discord_channel_id": str(discord_channel.id),
                "last_video_id": latest["video_id"] if latest else None,
            }
        )
        self._save_subscriptions()

        embed = discord.Embed(
            title="✅ YouTube Subscription Added",
            color=0xFF0000,
            timestamp=datetime.now(),
        )
        embed.add_field(name="YouTube Channel", value=f"**{yt_name}**", inline=True)
        embed.add_field(name="Posting alerts to", value=discord_channel.mention, inline=True)
        embed.set_footer(text="Checks for new videos every 5 minutes.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @youtube.command(
        name="unsubscribe",
        description="Stop receiving alerts for a YouTube channel",
    )
    @app_commands.describe(youtube_channel="Name of the YouTube channel to remove")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def unsubscribe(
        self,
        interaction: discord.Interaction,
        youtube_channel: str,
    ):
        guild_id = str(interaction.guild_id)
        subs: list = self.subscriptions.get(guild_id, [])

        new_subs = [
            s
            for s in subs
            if s["yt_channel_name"].lower() != youtube_channel.lower()
            and s["yt_channel_id"] != youtube_channel
        ]

        if len(new_subs) == len(subs):
            await interaction.response.send_message(
                f"❌ No subscription found for **{youtube_channel}**. "
                "Use `/youtube list` to see active subscriptions.",
                ephemeral=True,
            )
            return

        self.subscriptions[guild_id] = new_subs
        self._save_subscriptions()
        await interaction.response.send_message(
            f"✅ Unsubscribed from **{youtube_channel}**.", ephemeral=True
        )

    @unsubscribe.autocomplete("youtube_channel")
    async def unsubscribe_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        guild_id = str(interaction.guild_id)
        subs = self.subscriptions.get(guild_id, [])
        return [
            app_commands.Choice(name=s["yt_channel_name"], value=s["yt_channel_name"])
            for s in subs
            if current.lower() in s["yt_channel_name"].lower()
        ][:25]

    @youtube.command(
        name="list",
        description="List all active YouTube channel subscriptions in this server",
    )
    async def list_subs(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        subs = self.subscriptions.get(guild_id, [])

        if not subs:
            await interaction.response.send_message(
                "No YouTube subscriptions set up yet. "
                "Use `/youtube subscribe` to add one.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="YouTube Subscriptions",
            color=0xFF0000,
            timestamp=datetime.now(),
        )
        for sub in subs:
            ch = interaction.guild.get_channel(int(sub["discord_channel_id"]))
            ch_mention = ch.mention if ch else f"<#{sub['discord_channel_id']}>"
            embed.add_field(
                name=sub["yt_channel_name"],
                value=f"Alerts posted to: {ch_mention}",
                inline=False,
            )
        embed.set_footer(text=f"{len(subs)} active subscription(s) • Checks every 5 min")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # Cog-level error handler
    # ------------------------------------------------------------------

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ You need the **Manage Server** permission to manage YouTube subscriptions."
        else:
            logger.error(f"YouTube cog command error: {error}", exc_info=error)
            msg = "❌ An unexpected error occurred."

        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeNotifyCog(bot))
