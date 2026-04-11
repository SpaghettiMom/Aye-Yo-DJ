"""
Monthly leaderboard archive and announcement channel configuration.

Archive format (data/leaderboard_archive.json):
  { "guild_id": { "YYYY-MM": [ {"user_id": "123", "balance": 5000}, ... ] } }

Channel config (data/leaderboard_channels.json):
  { "guild_id": channel_id }

Last-reset tracker (data/leaderboard_last_reset.json):
  { "guild_id": "YYYY-MM" }
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
_ARCHIVE_FILE = DATA_DIR / "leaderboard_archive.json"
_CHANNELS_FILE = DATA_DIR / "leaderboard_channels.json"
_LAST_RESET_FILE = DATA_DIR / "leaderboard_last_reset.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path: Path, data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Announcement channel
# ---------------------------------------------------------------------------

def get_channel(guild_id: int) -> int | None:
    """Return the configured announcement channel ID for a guild, or None."""
    data = _load(_CHANNELS_FILE)
    val = data.get(str(guild_id))
    return int(val) if val is not None else None


def set_channel(guild_id: int, channel_id: int) -> None:
    data = _load(_CHANNELS_FILE)
    data[str(guild_id)] = channel_id
    _save(_CHANNELS_FILE, data)


# ---------------------------------------------------------------------------
# Monthly archive
# ---------------------------------------------------------------------------

def save_snapshot(guild_id: int, month_str: str, top_entries: list) -> None:
    """
    Save the end-of-month top entries for a guild.
    top_entries: list of {"user_id": str, "balance": int}
    """
    data = _load(_ARCHIVE_FILE)
    guild_key = str(guild_id)
    if guild_key not in data:
        data[guild_key] = {}
    data[guild_key][month_str] = top_entries
    _save(_ARCHIVE_FILE, data)


def get_snapshot(guild_id: int, month_str: str) -> list:
    """Return previously archived top entries for a guild/month, or []."""
    data = _load(_ARCHIVE_FILE)
    return data.get(str(guild_id), {}).get(month_str, [])


# ---------------------------------------------------------------------------
# Last-reset tracker
# ---------------------------------------------------------------------------

def get_last_reset(guild_id: int) -> str:
    """Return the month string ('YYYY-MM') of the last reset, or '' if never reset."""
    data = _load(_LAST_RESET_FILE)
    return data.get(str(guild_id), "")


def set_last_reset(guild_id: int, month_str: str) -> None:
    data = _load(_LAST_RESET_FILE)
    data[str(guild_id)] = month_str
    _save(_LAST_RESET_FILE, data)
