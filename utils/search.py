"""
Music search utility module
Handles searching for music on YouTube and Spotify
"""
import wavelink
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class MusicSearch:
    """Handle music search across different platforms"""
    
    @staticmethod
    async def search(
        query: str,
        search_type: str = "youtube"
    ) -> Tuple[List[wavelink.Playable], str]:
        """
        Search for music
        
        Args:
            query: Search query
            search_type: Type of search ("youtube", "spotify", "soundcloud", "ytsearch")
            
        Returns:
            Tuple of (list of Playable objects, source platform)
        """
        try:
            # If the query is a URL, pass it directly — no search prefix needed
            if query.startswith("http://") or query.startswith("https://"):
                results = await wavelink.Playable.search(query)
                return results, "url"

            if search_type.lower() in ["spotify", "spsearch"]:
                search_source = "spsearch"
            elif search_type.lower() == "youtube":
                search_source = "ytsearch"
            elif search_type.lower() == "soundcloud":
                search_source = "scsearch"
            else:
                search_source = "ytsearch"

            # Perform search
            results = await wavelink.Playable.search(
                f"{search_source}:{query}"
            )

            return results, search_source
        except Exception as e:
            logger.error(f"Search error: {e}")
            return [], "unknown"
    
    @staticmethod
    async def get_suggestions(
        query: str,
        limit: int = 5,
        search_type: str = "youtube"
    ) -> List[dict]:
        """
        Get search suggestions with metadata
        
        Args:
            query: Search query
            limit: Maximum number of suggestions
            search_type: Type of search
            
        Returns:
            List of suggestion dictionaries
        """
        results, source = await MusicSearch.search(query, search_type)
        
        suggestions = []
        for i, track in enumerate(results[:limit]):
            suggestion = {
                "index": i,
                "title": track.title,
                "artist": track.author,
                "duration": track.length,
                "source": source,
                "url": track.uri,
                "thumbnail": getattr(track, "artwork", None),
            }
            suggestions.append(suggestion)
        
        return suggestions
    
    @staticmethod
    async def get_track_by_url(url: str) -> wavelink.Playable:
        """Get a single track by URL"""
        try:
            results = await wavelink.Playable.search(url)
            if results:
                return results[0]
            return None
        except Exception as e:
            logger.error(f"Error getting track from URL: {e}")
            return None
