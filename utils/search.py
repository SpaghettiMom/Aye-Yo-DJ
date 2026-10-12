"""
Music search utility module
Handles searching for music on YouTube and Spotify
"""
import asyncio
import re
import wavelink
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Matches: https://open.spotify.com/track/<ID>  (with or without query string)
_SPOTIFY_TRACK_RE = re.compile(
    r"open\.spotify\.com/track/([A-Za-z0-9]+)"
)

# Matches: https://open.spotify.com/playlist/<ID>
_SPOTIFY_PLAYLIST_RE = re.compile(
    r"open\.spotify\.com/playlist/([A-Za-z0-9]+)"
)


def _fetch_spotify_track_info(track_id: str) -> Optional[Tuple[str, str]]:
    """
    Blocking call – run inside an executor.
    Returns (title, primary_artist) or None if credentials are missing / call fails.
    """
    try:
        from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            return None
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
            )
        )
        track = sp.track(track_id)
        title = track["name"]
        artists = ", ".join(a["name"] for a in track["artists"])
        return title, artists
    except Exception as exc:
        logger.warning(f"Spotify API lookup failed: {exc}")
        return None


async def resolve_spotify_url(url: str) -> Optional[str]:
    """
    Given a Spotify track URL, return a YouTube search query string
    like ``"Song Title Artist Name"`` to use with Lavalink.
    Returns *None* if the URL isn't a recognised Spotify track URL or
    if credentials haven't been configured.
    """
    match = _SPOTIFY_TRACK_RE.search(url)
    if not match:
        return None
    track_id = match.group(1)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_fetch_spotify_track_info, track_id),
            timeout=8.0
        )
    except asyncio.TimeoutError:
        logger.warning(f"Spotify API lookup timed out for track {track_id}")
        return None
    if result is None:
        return None
    title, artists = result
    return f"{title} {artists}"


def _fetch_spotify_playlist_tracks(playlist_id: str) -> Optional[List[Tuple[str, str]]]:
    """
    Blocking call – run inside an executor.
    Tries three methods in order:
      1. User OAuth refresh token (full playlist, all tracks)
      2. Client credentials via spotipy (may 403 on newer Spotify policy)
      3. Public embed page (no auth, up to 100 tracks)
    Returns a list of (title, artists) tuples or None if all methods fail.
    """
    # --- Method 1: User OAuth refresh token (run spotify_auth.py once to set this up) ---
    try:
        from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN
        if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET and SPOTIFY_REFRESH_TOKEN:
            import requests as _req
            import base64 as _b64
            creds = _b64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
            token_resp = _req.post(
                "https://accounts.spotify.com/api/token",
                headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "refresh_token", "refresh_token": SPOTIFY_REFRESH_TOKEN},
                timeout=10,
            )
            if token_resp.status_code == 200:
                access_token = token_resp.json()["access_token"]
                tracks: List[Tuple[str, str]] = []
                offset = 0
                while True:
                    r = _req.get(
                        f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params={"limit": 100, "offset": offset},
                        timeout=15,
                    )
                    if r.status_code != 200:
                        logger.warning(f"Spotify OAuth tracks request failed: {r.status_code} {r.text[:200]}")
                        break
                    data = r.json()
                    for item in data.get("items", []):
                        track_data = item.get("item") or item.get("track")
                        if not track_data:
                            continue
                        title = track_data["name"]
                        artists = ", ".join(a["name"] for a in track_data.get("artists", []))
                        tracks.append((title, artists))
                    if data.get("next") is None:
                        break
                    offset += 100
                if tracks:
                    logger.info(f"Spotify OAuth returned {len(tracks)} tracks for playlist {playlist_id}")
                    return tracks
            else:
                logger.warning(f"Spotify refresh token exchange failed: {token_resp.status_code}")
    except Exception as oauth_exc:
        logger.warning(f"Spotify OAuth playlist lookup failed: {oauth_exc}")

    # --- Method 2: Client credentials via spotipy (may 403 post-2024 policy change) ---
    try:
        from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
        if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
            sp = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id=SPOTIFY_CLIENT_ID,
                    client_secret=SPOTIFY_CLIENT_SECRET,
                )
            )
            tracks: List[Tuple[str, str]] = []
            offset = 0
            while True:
                response = sp.playlist_items(
                    playlist_id,
                    offset=offset,
                    fields="items(track(name,artists(name))),next",
                    limit=100,
                )
                for item in response.get("items", []):
                    track_data = item.get("track")
                    if not track_data:
                        continue
                    title = track_data["name"]
                    artists = ", ".join(a["name"] for a in track_data.get("artists", []))
                    tracks.append((title, artists))
                if response.get("next") is None:
                    break
                offset += 100
            if tracks:
                logger.info(f"Spotify client creds returned {len(tracks)} tracks for playlist {playlist_id}")
                return tracks
    except Exception as spotipy_exc:
        logger.warning(f"Spotify client credentials playlist lookup failed (falling back to embed): {spotipy_exc}")

    # --- Method 3: Parse the public embed page (no API key required, up to 100 tracks) ---
    # To get all tracks run: python spotify_auth.py
    try:
        import requests
        import re
        import json as _json
        url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        m = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            resp.text,
            re.DOTALL,
        )
        if not m:
            logger.warning("Spotify embed page: __NEXT_DATA__ block not found")
            return None
        page_data = _json.loads(m.group(1))
        entity = (
            page_data.get("props", {})
            .get("pageProps", {})
            .get("state", {})
            .get("data", {})
            .get("entity", {})
        )
        track_list = entity.get("trackList", [])
        if not track_list:
            logger.warning("Spotify embed page: trackList is empty")
            return None
        result = [(t["title"], t.get("subtitle", "")) for t in track_list if t.get("title")]
        logger.info(f"Spotify embed page returned {len(result)} tracks for playlist {playlist_id}")
        return result
    except Exception as embed_exc:
        logger.warning(f"Spotify embed page playlist lookup failed: {embed_exc}")
        return None


async def resolve_spotify_playlist_url(url: str) -> Optional[List[str]]:
    """
    Given a Spotify playlist URL, return a list of YouTube search query strings
    (one per track).  Returns None if not a recognised playlist URL or
    credentials are missing.
    """
    match = _SPOTIFY_PLAYLIST_RE.search(url)
    if not match:
        return None
    playlist_id = match.group(1)
    try:
        track_infos = await asyncio.wait_for(
            asyncio.to_thread(_fetch_spotify_playlist_tracks, playlist_id),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Spotify playlist lookup timed out for {playlist_id}")
        return None
    if not track_infos:
        return None
    return [f"{title} {artists}" for title, artists in track_infos]


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
            explicit_prefixes = ("ytsearch:", "ytmsearch:", "scsearch:", "spsearch:")
            lower_query = query.lower()
            for prefix in explicit_prefixes:
                if lower_query.startswith(prefix):
                    results = await wavelink.Playable.search(query, source=None)
                    return results, prefix[:-1]

            # If the query is a URL or a native Spotify/SoundCloud URI, handle it
            if (query.startswith("http://") or query.startswith("https://")
                    or query.startswith("spotify:") or query.startswith("soundcloud:")):

                # Block Spotify playlist URLs from reaching Lavalink — they must go through search_playlist()
                if "open.spotify.com/playlist/" in query:
                    logger.warning("Spotify playlist URL passed to search() — use search_playlist() instead")
                    return [], "spotify"

                # Spotify track URL → resolve metadata → search YouTube
                if "open.spotify.com/track/" in query:
                    yt_query = await resolve_spotify_url(query)
                    if yt_query:
                        logger.info(f"Spotify track resolved to YouTube query: {yt_query!r}")
                        results = await wavelink.Playable.search(f"ytsearch:{yt_query}", source=None)
                        return results, "spotify"
                    # Credentials not configured – fall through to direct Lavalink search
                    # (strip tracking params first)
                    if "?" in query:
                        query = query.split("?")[0]

                results = await wavelink.Playable.search(query)
                return results, "url"

            normalized_search_type = search_type.lower()

            if normalized_search_type in ["spotify", "spsearch"]:
                search_source = "spsearch"
            elif normalized_search_type == "youtube":
                search_source = "ytsearch"
            elif normalized_search_type == "soundcloud":
                search_source = "scsearch"
            else:
                search_source = "ytsearch"

            # Prefer YouTube Music search for plain music queries because it often
            # surfaces less restricted matches than the top regular YouTube result.
            if normalized_search_type == "youtube":
                results = await wavelink.Playable.search(f"ytmsearch:{query}", source=None)
                if results:
                    return results, "ytmsearch"

            # Perform search
            results = await wavelink.Playable.search(f"{search_source}:{query}", source=None)

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

    @staticmethod
    async def search_playlist(url: str, max_tracks: int = 1000) -> Tuple[List[wavelink.Playable], str]:
        """
        Load all tracks from a playlist URL (Spotify or YouTube).
        Spotify playlists are resolved concurrently via YouTube search.

        Args:
            url: Playlist URL
            max_tracks: Maximum number of tracks to load (default 500, matches queue limit)

        Returns:
            Tuple of (list of Playable objects, source platform)
        """
        try:
            # Spotify playlist → resolve each track via YouTube search (concurrent)
            if "open.spotify.com/playlist/" in url:
                queries = await resolve_spotify_playlist_url(url)
                if not queries:
                    return [], "spotify"

                queries = queries[:max_tracks]
                logger.info(f"Resolving {len(queries)} Spotify tracks to YouTube...")

                # Use a semaphore so we don't flood Lavalink with 500 simultaneous requests
                sem = asyncio.Semaphore(8)

                async def _resolve_one(q: str) -> Optional[wavelink.Playable]:
                    async with sem:
                        try:
                            results = await wavelink.Playable.search(f"ytsearch:{q}", source=None)
                            return results[0] if results else None
                        except Exception as err:
                            logger.warning(f"Failed to resolve track '{q}': {err}")
                            return None

                resolved = await asyncio.gather(*[_resolve_one(q) for q in queries])
                tracks = [t for t in resolved if t is not None]
                logger.info(f"Resolved {len(tracks)}/{len(queries)} tracks from Spotify playlist")
                return tracks, "spotify"

            # YouTube playlist or generic URL – wavelink returns all tracks directly
            results = await wavelink.Playable.search(url)
            return results[:max_tracks] if results else [], "youtube"
        except Exception as e:
            logger.error(f"Playlist search error: {e}")
            return [], "unknown"
