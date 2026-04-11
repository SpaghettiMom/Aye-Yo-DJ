"""
Pancake currency system
Handles persistent per-user balances stored in data/pancakes.json
"""
import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PANCAKES_FILE = DATA_DIR / "pancakes.json"
STARTING_BALANCE = 1000


def _load() -> dict:
    if not PANCAKES_FILE.exists():
        return {}
    with open(PANCAKES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(PANCAKES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_balance(guild_id: int, user_id: int) -> int:
    """Return the user's pancake balance for the given guild, defaulting to STARTING_BALANCE."""
    data = _load()
    key = f"{guild_id}:{user_id}"
    return data.get(key, STARTING_BALANCE)


def set_balance(guild_id: int, user_id: int, amount: int) -> None:
    """Set a user's balance for the given guild to a specific amount."""
    data = _load()
    key = f"{guild_id}:{user_id}"
    data[key] = max(0, amount)
    _save(data)


def add_balance(guild_id: int, user_id: int, amount: int) -> int:
    """Add amount to a user's balance in the given guild and return the new balance."""
    new_balance = get_balance(guild_id, user_id) + amount
    set_balance(guild_id, user_id, new_balance)
    return new_balance


def subtract_balance(guild_id: int, user_id: int, amount: int) -> int:
    """Subtract amount from a user's balance in the given guild and return the new balance."""
    new_balance = get_balance(guild_id, user_id) - amount
    set_balance(guild_id, user_id, new_balance)
    return new_balance


def get_all_guild_balances(guild_id: int) -> dict:
    """Return {user_id_str: balance} for every user with a stored balance in this guild."""
    data = _load()
    prefix = f"{guild_id}:"
    return {key[len(prefix):]: val for key, val in data.items() if key.startswith(prefix)}


def reset_guild_balances(guild_id: int) -> None:
    """Delete all stored balance entries for this guild (resets everyone to the default)."""
    data = _load()
    prefix = f"{guild_id}:"
    for key in [k for k in data if k.startswith(prefix)]:
        del data[key]
    _save(data)
