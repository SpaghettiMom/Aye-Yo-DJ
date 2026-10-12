"""
Music player management module
Handles queue, playback, and player state
"""
import wavelink
from typing import Optional, List
from collections import deque
import logging

logger = logging.getLogger(__name__)


class MusicPlayer:
    """Manages music playback, queue, and player state"""
    
    def __init__(self, guild_id: int, max_queue_size: int = 1000):
        self.guild_id = guild_id
        self.queue = deque(maxlen=max_queue_size)
        self.current_track: Optional[wavelink.Playable] = None
        self.is_paused = False
        self.current_message_id: Optional[int] = None
        self.current_channel_id: Optional[int] = None
        self.loop_mode = "off"  # "off", "one", "all"
        self.volume = 100
        self.jingle_played = False
        self.autoplay = False
        self.played_tracks = set()  # Track URIs of played tracks to avoid repeats
        self.failed_track_uris = set()  # Track URIs that failed to stream for this session
        self.current_requester = None  # discord.Member who requested the current track
    
    def add_track(self, track: wavelink.Playable) -> bool:
        """
        Add a track to the queue
        
        Returns:
            True if added successfully, False if queue is full
        """
        try:
            self.queue.append(track)
            return True
        except Exception as e:
            logger.error(f"Error adding track to queue: {e}")
            return False
    
    def add_tracks(self, tracks: List[wavelink.Playable]) -> int:
        """
        Add multiple tracks to the queue
        
        Returns:
            Number of tracks successfully added
        """
        added = 0
        for track in tracks:
            if self.add_track(track):
                added += 1
            else:
                break
        return added
    
    def remove_track(self, index: int) -> Optional[wavelink.Playable]:
        """
        Remove a track from the queue by index
        
        Returns:
            The removed track or None if index is invalid
        """
        try:
            queue_list = list(self.queue)
            if 0 <= index < len(queue_list):
                removed = queue_list.pop(index)
                self.queue = deque(queue_list, maxlen=self.queue.maxlen)
                return removed
            return None
        except Exception as e:
            logger.error(f"Error removing track: {e}")
            return None
    
    def move_track(self, from_index: int, to_index: int) -> bool:
        """
        Move a track in the queue
        
        Returns:
            True if successful
        """
        try:
            queue_list = list(self.queue)
            if 0 <= from_index < len(queue_list) and 0 <= to_index < len(queue_list):
                track = queue_list.pop(from_index)
                queue_list.insert(to_index, track)
                self.queue = deque(queue_list, maxlen=self.queue.maxlen)
                return True
            return False
        except Exception as e:
            logger.error(f"Error moving track: {e}")
            return False
    
    def get_queue(self) -> List[wavelink.Playable]:
        """Get current queue as a list"""
        return list(self.queue)
    
    def get_queue_size(self) -> int:
        """Get the size of the queue"""
        return len(self.queue)
    
    def clear_queue(self) -> None:
        """Clear the entire queue"""
        self.queue.clear()
    
    def next_track(self) -> Optional[wavelink.Playable]:
        """Get the next track from the queue"""
        try:
            if self.queue:
                return self.queue.popleft()
            return None
        except Exception as e:
            logger.error(f"Error getting next track: {e}")
            return None
    
    def set_loop_mode(self, mode: str) -> bool:
        """
        Set loop mode
        
        Args:
            mode: "off", "one", or "all"
        """
        if mode in ["off", "one", "all"]:
            self.loop_mode = mode
            return True
        return False
    
    def get_loop_mode(self) -> str:
        """Get current loop mode"""
        return self.loop_mode
    
    def set_volume(self, volume: int) -> bool:
        """
        Set player volume (0-100)
        """
        if 0 <= volume <= 100:
            self.volume = volume
            return True
        return False
    
    def get_volume(self) -> int:
        """Get current volume"""
        return self.volume
    
    def toggle_pause(self) -> bool:
        """Toggle pause state"""
        self.is_paused = not self.is_paused
        return self.is_paused
    
    def set_pause(self, paused: bool) -> None:
        """Set pause state"""
        self.is_paused = paused
    
    def is_player_paused(self) -> bool:
        """Check if player is paused"""
        return self.is_paused
    
    def set_controller_message(self, message_id: int, channel_id: int) -> None:
        """Store the controller message ID and channel ID"""
        self.current_message_id = message_id
        self.current_channel_id = channel_id
    
    def get_controller_message(self) -> tuple:
        """Get controller message ID and channel ID"""
        return self.current_message_id, self.current_channel_id
    
    def reset(self) -> None:
        """Reset player to initial state"""
        self.queue.clear()
        self.current_track = None
        self.is_paused = False
        self.loop_mode = "off"
        self.volume = 100
        self.autoplay = False
        self.current_message_id = None
        self.current_channel_id = None
        self.played_tracks.clear()
        self.failed_track_uris.clear()
        self.current_requester = None
