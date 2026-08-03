"""
Blackjack command cog
Handles: /blackjack <bet> and /pancakes
"""
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import tasks
import logging
from datetime import datetime, timezone

from utils.blackjack import (
    BlackjackGame,
    hand_str,
    hand_value,
    STATE_PLAYING,
    STATE_BLACKJACK,
    STATE_PLAYER_BUST,
    STATE_DEALER_BUST,
    STATE_WIN,
    STATE_LOSE,
    STATE_PUSH,
)
from utils import currency
from utils import leaderboard as lb_store
from utils import stocks

logger = logging.getLogger(__name__)

MEDALS = ["🥇", "🥈", "🥉"]

PANCAKE = "🥞"


# ---------------------------------------------------------------------------
# Embed builder
# ---------------------------------------------------------------------------

def _build_embed(
    game: BlackjackGame,
    user: discord.User | discord.Member,
    guild_id: int,
    *,
    game_over: bool,
) -> discord.Embed:
    player_val = hand_value(game.player_hand)
    dealer_val = hand_value(game.dealer_hand)

    state_meta = {
        STATE_PLAYING:     (0x0099FF, f"🃏 Blackjack — {PANCAKE} {game.total_bet} bet", "Hit, Stand, or Double Down!"),
        STATE_BLACKJACK:   (0xFFD700, "🃏 Blackjack! 🎉", f"Natural Blackjack! You win **{int(game.total_bet * 1.5)}** {PANCAKE} bonus!"),
        STATE_WIN:         (0x00CC44, "🃏 You Win! 🎉", f"You win **{game.total_bet}** {PANCAKE}!"),
        STATE_DEALER_BUST: (0x00CC44, "🃏 Dealer Bust! 🎉", f"Dealer busted — you win **{game.total_bet}** {PANCAKE}!"),
        STATE_PUSH:        (0xFFFF00, "🃏 Push — It's a Tie!", "Your bet has been returned."),
        STATE_LOSE:        (0xFF3333, "🃏 You Lose!", f"You lost **{game.total_bet}** {PANCAKE}."),
        STATE_PLAYER_BUST: (0xFF3333, "🃏 Bust! 💥", f"You busted — you lost **{game.total_bet}** {PANCAKE}."),
    }

    color, title, description = state_meta[game.state]
    embed = discord.Embed(title=title, description=description, color=color)

    embed.add_field(
        name=f"Your Hand ({player_val})",
        value=hand_str(game.player_hand),
        inline=False,
    )

    if game_over:
        embed.add_field(
            name=f"Dealer's Hand ({dealer_val})",
            value=hand_str(game.dealer_hand),
            inline=False,
        )
        new_bal = currency.get_balance(guild_id, user.id)
        embed.add_field(
            name="Balance",
            value=f"{PANCAKE} **{new_bal:,}** pancakes",
            inline=False,
        )
    else:
        embed.add_field(
            name="Dealer's Hand",
            value=hand_str(game.dealer_hand, hide_second=True),
            inline=False,
        )

    embed.set_footer(text=f"Player: {user.display_name}")
    return embed


# ---------------------------------------------------------------------------
# Interactive View
# ---------------------------------------------------------------------------

class BlackjackView(discord.ui.View):
    """Buttons: Hit / Stand / Double Down."""

    def __init__(
        self,
        game: BlackjackGame,
        user: discord.User | discord.Member,
        balance_after_bet: int,
        guild_id: int,
    ):
        super().__init__(timeout=120)
        self.game = game
        self.user = user
        self.guild_id = guild_id
        # Disable Double Down if user can't afford the extra bet
        if balance_after_bet < game.initial_bet:
            self.double_btn.disabled = True

    # Only the game's owner can press buttons
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This isn't your game!", ephemeral=True
            )
            return False
        return True

    def _finalize(self) -> None:
        """Credit winnings and disable all buttons."""
        currency.add_balance(self.guild_id, self.user.id, self.game.winnings())
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]
        self.stop()

    # --- Hit ---
    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="👊")
    async def hit_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.game.hit()
        if self.game.state != STATE_PLAYING:
            self._finalize()
            await interaction.response.edit_message(
                embed=_build_embed(self.game, self.user, self.guild_id, game_over=True), view=self
            )
        else:
            # After a hit, Double Down is no longer available
            self.double_btn.disabled = True
            await interaction.response.edit_message(
                embed=_build_embed(self.game, self.user, self.guild_id, game_over=False), view=self
            )

    # --- Stand ---
    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.game.stand()
        self._finalize()
        await interaction.response.edit_message(
            embed=_build_embed(self.game, self.user, self.guild_id, game_over=True), view=self
        )

    # --- Double Down ---
    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success, emoji="⬆️")
    async def double_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Deduct the additional bet before doubling
        currency.subtract_balance(self.guild_id, self.user.id, self.game.initial_bet)
        self.game.double_down()
        self._finalize()
        await interaction.response.edit_message(
            embed=_build_embed(self.game, self.user, self.guild_id, game_over=True), view=self
        )

    # Timeout: return the bet so the user isn't penalised for going AFK
    async def on_timeout(self) -> None:
        currency.add_balance(self.guild_id, self.user.id, self.game.total_bet)
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class BlackjackCog(commands.Cog):
    """Blackjack & pancake currency commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active: set[int] = set()   # user IDs with an in-progress game
        self._monthly_reset_task.start()

    def cog_unload(self):
        self._monthly_reset_task.cancel()

    async def _resolve_username(self, guild: discord.Guild, user_id: int) -> str:
        """Return a display name for user_id, fetching from Discord API if not in guild cache."""
        member = guild.get_member(user_id)
        if member:
            return member.display_name
        try:
            user = await self.bot.fetch_user(user_id)
            return user.display_name
        except discord.NotFound:
            return f"Deleted User"
        except discord.HTTPException:
            return f"Unknown User"

    # -----------------------------------------------------------------------
    # Monthly reset task
    # -----------------------------------------------------------------------

    @tasks.loop(hours=1)
    async def _monthly_reset_task(self):
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        for guild in self.bot.guilds:
            last = lb_store.get_last_reset(guild.id)
            if last == "":
                # First time seeing this guild — initialise without wiping data
                lb_store.set_last_reset(guild.id, current_month)
            elif last != current_month:
                await self._do_monthly_reset(guild, current_month)

    @_monthly_reset_task.before_loop
    async def _before_monthly_reset(self):
        await self.bot.wait_until_ready()

    async def _do_monthly_reset(self, guild: discord.Guild, current_month: str) -> None:
        """Liquidate stocks, archive last month's top 10, reset balances, post announcement."""
        # Derive the previous month label
        now = datetime.now(timezone.utc)
        prev_month = (
            f"{now.year - 1}-12" if now.month == 1
            else f"{now.year}-{now.month - 1:02d}"
        )

        # --- Stock liquidation ---
        # Credit stock proceeds to each user's balance BEFORE snapshotting
        try:
            payouts = await stocks.liquidate_guild_portfolios(guild.id)
            for user_id_str, pancakes in payouts.items():
                if pancakes > 0:
                    currency.add_balance(guild.id, int(user_id_str), pancakes)
            stocks.clear_guild_portfolios(guild.id)
            logger.info(
                f"Liquidated {len(payouts)} portfolio(s) for guild {guild.id} "
                f"before monthly reset"
            )
        except Exception as e:
            logger.error(f"Stock liquidation failed for guild {guild.id}: {e}")

        # Snapshot top 10 before wiping (balances now include liquidated stock proceeds)
        balances = currency.get_all_guild_balances(guild.id)
        top_entries = sorted(
            [{"user_id": uid, "balance": bal} for uid, bal in balances.items()],
            key=lambda x: x["balance"],
            reverse=True,
        )[:10]
        lb_store.save_snapshot(guild.id, prev_month, top_entries)

        # Wipe balances
        currency.reset_guild_balances(guild.id)
        lb_store.set_last_reset(guild.id, current_month)
        logger.info(f"Monthly reset complete for guild {guild.id} ({prev_month} -> {current_month})")

        # Post announcement if a channel is configured
        channel_id = lb_store.get_channel(guild.id)
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title=f"{PANCAKE} Monthly Results — {prev_month}",
            description=(
                "All stock holdings were **liquidated** at market price and added to balances.\n"
                "Balances have been **reset** for the new month. Here's how last month ended!"
            ),
            color=0xFFD700,
        )
        if top_entries:
            lines = []
            for i, entry in enumerate(top_entries):
                name = await self._resolve_username(guild, int(entry["user_id"]))
                medal = MEDALS[i] if i < 3 else f"{i + 1}."
                lines.append(f"{medal} **{name}** — {PANCAKE} {entry['balance']:,}")
            embed.add_field(name="Final Standings", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Final Standings", value="Nobody played last month!", inline=False)

        embed.set_footer(text=f"New month: {current_month} — Good luck everyone!")
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"Missing permissions to post leaderboard in guild {guild.id} channel {channel_id}")

    # --- /blackjack ---
    @app_commands.command(
        name="blackjack",
        description=f"Bet pancakes on a game of blackjack!",
    )
    @app_commands.describe(bet="How many pancakes to wager")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        user = interaction.user
        guild_id = interaction.guild_id

        if user.id in self._active:
            await interaction.response.send_message(
                "You already have an active game — finish it first!", ephemeral=True
            )
            return

        if bet <= 0:
            await interaction.response.send_message(
                f"Bet must be at least 1 {PANCAKE}!", ephemeral=True
            )
            return

        balance = currency.get_balance(guild_id, user.id)
        if balance < bet:
            await interaction.response.send_message(
                f"Not enough pancakes! Your balance: {PANCAKE} **{balance:,}**",
                ephemeral=True,
            )
            return

        # Deduct the initial bet upfront
        currency.subtract_balance(guild_id, user.id, bet)
        balance_after_bet = balance - bet

        game = BlackjackGame(bet=bet)
        game.deal()

        # Immediate blackjack — no buttons needed
        if game.state == STATE_BLACKJACK:
            currency.add_balance(guild_id, user.id, game.winnings())
            await interaction.response.send_message(
                embed=_build_embed(game, user, guild_id, game_over=True)
            )
            return

        self._active.add(user.id)
        view = BlackjackView(game, user, balance_after_bet, guild_id)
        await interaction.response.send_message(
            embed=_build_embed(game, user, guild_id, game_over=False), view=view
        )
        await view.wait()
        self._active.discard(user.id)

    # --- /pancakes ---
    @app_commands.command(
        name="pancakes",
        description="Check your pancake balance",
    )
    async def pancakes_cmd(self, interaction: discord.Interaction):
        bal = currency.get_balance(interaction.guild_id, interaction.user.id)
        embed = discord.Embed(
            title=f"{PANCAKE} Pancake Balance",
            description=f"**{interaction.user.display_name}** has **{bal:,}** {PANCAKE} pancakes!",
            color=0xFFD700,
        )
        await interaction.response.send_message(embed=embed)

    # --- /leaderboard ---
    @app_commands.command(
        name="leaderboard",
        description="Show the pancake leaderboard for this server",
    )
    async def leaderboard_cmd(self, interaction: discord.Interaction):
        guild = interaction.guild
        now = datetime.now(timezone.utc)
        current_month = now.strftime("%Y-%m")
        prev_month = (
            f"{now.year - 1}-12" if now.month == 1
            else f"{now.year}-{now.month - 1:02d}"
        )

        embed = discord.Embed(
            title=f"{PANCAKE} Pancake Leaderboard",
            color=0xFFD700,
        )

        # Current month standings
        balances = currency.get_all_guild_balances(guild.id)
        if balances:
            current_sorted = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
            lines = []
            for i, (uid, bal) in enumerate(current_sorted):
                name = await self._resolve_username(guild, int(uid))
                medal = MEDALS[i] if i < 3 else f"{i + 1}."
                lines.append(f"{medal} **{name}** — {PANCAKE} {bal:,}")
            embed.add_field(name=f"📅 This Month ({current_month})", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name=f"📅 This Month ({current_month})", value="No games played yet!", inline=False)

        # Previous month archive
        prev_entries = lb_store.get_snapshot(guild.id, prev_month)
        if prev_entries:
            lines = []
            for i, entry in enumerate(prev_entries):
                name = await self._resolve_username(guild, int(entry["user_id"]))
                medal = MEDALS[i] if i < 3 else f"{i + 1}."
                lines.append(f"{medal} **{name}** — {PANCAKE} {entry['balance']:,}")
            embed.add_field(name=f"🏆 Last Month ({prev_month})", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name=f"🏆 Last Month ({prev_month})", value="No data recorded.", inline=False)

        await interaction.response.send_message(embed=embed)

    # --- /setleaderboard ---
    @app_commands.command(
        name="setleaderboard",
        description="Set the channel where monthly leaderboard results are announced",
    )
    @app_commands.describe(channel="Channel to post monthly results in")
    @app_commands.default_permissions(manage_guild=True)
    async def set_leaderboard_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        lb_store.set_channel(interaction.guild_id, channel.id)
        embed = discord.Embed(
            title="✅ Leaderboard Channel Set",
            description=f"Monthly results will be posted in {channel.mention}.",
            color=0x00CC44,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Load the cog."""
    await bot.add_cog(BlackjackCog(bot))
