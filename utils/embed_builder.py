"""
Discord embed builder utility module
Creates formatted embeds for music bot responses
"""
import discord
from datetime import datetime
from config import COLORS
from typing import List, Optional


class EmbedBuilder:
    """Helper class for building Discord embeds"""
    
    @staticmethod
    def format_duration(milliseconds: int) -> str:
        """Convert milliseconds to MM:SS format"""
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    @staticmethod
    def create_search_result(
        title: str,
        suggestions: List[dict],
        query: str
    ) -> discord.Embed:
        """Create an embed for search results"""
        embed = discord.Embed(
            title=f"🔍 Search Results for: {query}",
            color=COLORS["primary"],
            timestamp=datetime.now()
        )
        
        for suggestion in suggestions:
            duration = EmbedBuilder.format_duration(suggestion["duration"])
            field_value = (
                f"**Artist:** {suggestion['artist']}\n"
                f"**Duration:** {duration}\n"
                f"**URL:** [Click here]({suggestion['url']})"
            )
            embed.add_field(
                name=f"{suggestion['index'] + 1}. {suggestion['title'][:50]}",
                value=field_value,
                inline=False
            )
        
        embed.set_footer(text=f"Source: {suggestions[0]['source'] if suggestions else 'N/A'}")
        return embed
    
    @staticmethod
    def create_now_playing(
        track,
        author_name: str = None,
        author_avatar: str = None
    ) -> discord.Embed:
        """Create an embed for the now playing track"""
        duration = EmbedBuilder.format_duration(track.length)
        
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{track.title}**",
            color=COLORS["primary"],
            timestamp=datetime.now()
        )
        
        embed.add_field(name="Artist", value=track.author, inline=True)
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(
            name="Source",
            value=track.source or "Unknown",
            inline=True
        )
        
        if hasattr(track, "artwork") and track.artwork:
            embed.set_thumbnail(url=track.artwork)
        
        if author_name and author_avatar:
            embed.set_footer(text=f"Requested by {author_name}", icon_url=author_avatar)
        
        return embed
    
    @staticmethod
    def create_queue_embed(
        tracks: List,
        page: int = 1,
        per_page: int = 10
    ) -> discord.Embed:
        """Create an embed for the queue"""
        total_pages = (len(tracks) + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, len(tracks))
        
        embed = discord.Embed(
            title="📋 Music Queue",
            color=COLORS["primary"],
            timestamp=datetime.now()
        )
        
        if not tracks:
            embed.description = "Queue is empty"
            return embed
        
        queue_text = ""
        for i in range(start_idx, end_idx):
            track = tracks[i]
            duration = EmbedBuilder.format_duration(track.length)
            queue_text += f"{i + 1}. **{track.title}** - {duration}\n"
        
        embed.description = queue_text or "Queue is empty"
        embed.set_footer(text=f"Page {page}/{total_pages} | Total tracks: {len(tracks)}")
        
        return embed
    
    @staticmethod
    def create_track_added_embed(
        tracks: List,
        playlist: bool = False
    ) -> discord.Embed:
        """Create an embed for when track(s) are added"""
        embed = discord.Embed(
            color=COLORS["success"],
            timestamp=datetime.now()
        )
        
        if playlist:
            embed.title = "✅ Playlist Added to Queue"
            embed.description = f"Added {len(tracks)} tracks to the queue"
        else:
            if len(tracks) == 1:
                track = tracks[0]
                embed.title = "✅ Track Added to Queue"
                embed.description = f"**{track.title}** by {track.author}"
            else:
                embed.title = "✅ Tracks Added to Queue"
                embed.description = f"Added {len(tracks)} tracks to the queue"
        
        return embed
    
    @staticmethod
    def create_error_embed(
        error_message: str,
        title: str = "❌ Error"
    ) -> discord.Embed:
        """Create an error embed"""
        embed = discord.Embed(
            title=title,
            description=error_message,
            color=COLORS["error"],
            timestamp=datetime.now()
        )
        return embed
    
    @staticmethod
    def create_info_embed(
        title: str,
        description: str
    ) -> discord.Embed:
        """Create an info embed"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=COLORS["info"],
            timestamp=datetime.now()
        )
        return embed
    
    @staticmethod
    def create_success_embed(
        title: str,
        description: str
    ) -> discord.Embed:
        """Create a success embed"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=COLORS["success"],
            timestamp=datetime.now()
        )
        return embed
