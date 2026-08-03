"""
Stock investment cog
Handles: /invest /sell /portfolio

Each pancake = $1 USD when buying/selling shares (fractional shares supported).
Holdings are liquidated automatically at month-end by the blackjack cog's reset task.
"""
import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils import currency
from utils import stocks

logger = logging.getLogger(__name__)

PANCAKE = "🥞"
CHART = "📈"


class InvestCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------
    # /invest
    # ------------------------------------------------------------------

    @app_commands.command(
        name="invest",
        description="Invest pancakes into a real stock. Each pancake = $1 USD.",
    )
    @app_commands.describe(
        ticker="Stock ticker symbol (e.g. AAPL, TSLA, MSFT)",
        amount="Number of pancakes to invest",
    )
    async def invest(
        self,
        interaction: discord.Interaction,
        ticker: str,
        amount: int,
    ) -> None:
        await interaction.response.defer()

        guild_id = interaction.guild_id
        user = interaction.user
        ticker = ticker.upper().strip()

        if amount <= 0:
            await interaction.followup.send(
                f"Amount must be at least 1 {PANCAKE}!", ephemeral=True
            )
            return

        balance = currency.get_balance(guild_id, user.id)
        if balance < amount:
            await interaction.followup.send(
                f"You only have {PANCAKE} **{balance:,}** — can't invest {PANCAKE} **{amount:,}**!",
                ephemeral=True,
            )
            return

        price = await stocks.get_stock_price(ticker)
        if price is None or price <= 0:
            await interaction.followup.send(
                f"Could not fetch price for **{ticker}**. Make sure it's a valid stock ticker.",
                ephemeral=True,
            )
            return

        shares_bought = amount / price

        # Update portfolio with weighted-average cost basis
        portfolio = stocks.get_portfolio(guild_id, user.id)
        if ticker in portfolio:
            prev = portfolio[ticker]
            total_shares = prev["shares"] + shares_bought
            avg_cost = (prev["shares"] * prev["avg_cost"] + amount) / total_shares
            portfolio[ticker] = {"shares": total_shares, "avg_cost": avg_cost}
        else:
            portfolio[ticker] = {"shares": shares_bought, "avg_cost": price}

        stocks.set_portfolio(guild_id, user.id, portfolio)
        currency.subtract_balance(guild_id, user.id, amount)
        new_balance = currency.get_balance(guild_id, user.id)

        embed = discord.Embed(
            title=f"{CHART} Investment Successful!",
            color=0x00CC44,
        )
        embed.add_field(name="Stock", value=f"**{ticker}**", inline=True)
        embed.add_field(name="Share Price", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="Shares Bought", value=f"{shares_bought:.4f}", inline=True)
        embed.add_field(name="Pancakes Invested", value=f"{PANCAKE} **{amount:,}**", inline=True)
        embed.add_field(name="New Balance", value=f"{PANCAKE} **{new_balance:,}**", inline=True)
        embed.set_footer(
            text=f"Invested by {user.display_name} · Holdings liquidate at month end"
        )
        await interaction.followup.send(embed=embed)

    # ------------------------------------------------------------------
    # /sell
    # ------------------------------------------------------------------

    @app_commands.command(
        name="sell",
        description="Sell your stock holdings and receive pancakes.",
    )
    @app_commands.describe(
        ticker="Stock ticker symbol to sell (e.g. AAPL)",
        shares="Number of shares to sell — omit to sell everything",
    )
    async def sell(
        self,
        interaction: discord.Interaction,
        ticker: str,
        shares: float | None = None,
    ) -> None:
        await interaction.response.defer()

        guild_id = interaction.guild_id
        user = interaction.user
        ticker = ticker.upper().strip()

        portfolio = stocks.get_portfolio(guild_id, user.id)
        if ticker not in portfolio:
            await interaction.followup.send(
                f"You don't own any **{ticker}**. Check `/portfolio` for your holdings.",
                ephemeral=True,
            )
            return

        holding = portfolio[ticker]
        held_shares: float = holding["shares"]
        avg_cost: float = holding["avg_cost"]

        sell_shares = shares if shares is not None else held_shares

        if sell_shares <= 0:
            await interaction.followup.send(
                "Shares to sell must be a positive number.", ephemeral=True
            )
            return

        if sell_shares > held_shares + 1e-9:
            await interaction.followup.send(
                f"You only have **{held_shares:.4f}** shares of **{ticker}**.",
                ephemeral=True,
            )
            return

        price = await stocks.get_stock_price(ticker)
        if price is None or price <= 0:
            await interaction.followup.send(
                f"Could not fetch current price for **{ticker}**. Try again later.",
                ephemeral=True,
            )
            return

        pancakes_received = int(sell_shares * price)
        pnl_pct = ((price - avg_cost) / avg_cost) * 100
        pnl_pancakes = int(sell_shares * (price - avg_cost))

        # Update portfolio
        remaining = held_shares - sell_shares
        if remaining < 1e-8:
            del portfolio[ticker]
        else:
            portfolio[ticker]["shares"] = remaining

        stocks.set_portfolio(guild_id, user.id, portfolio)
        currency.add_balance(guild_id, user.id, pancakes_received)
        new_balance = currency.get_balance(guild_id, user.id)

        pnl_sign = "+" if pnl_pct >= 0 else ""
        color = 0x00CC44 if pnl_pct >= 0 else 0xFF3333

        embed = discord.Embed(
            title=f"{CHART} Sold **{ticker}**!",
            color=color,
        )
        embed.add_field(name="Shares Sold", value=f"{sell_shares:.4f}", inline=True)
        embed.add_field(name="Sell Price", value=f"${price:,.2f}", inline=True)
        embed.add_field(
            name="Pancakes Received", value=f"{PANCAKE} **{pancakes_received:,}**", inline=True
        )
        embed.add_field(name="Avg Buy Price", value=f"${avg_cost:,.2f}", inline=True)
        embed.add_field(
            name="P&L",
            value=f"{pnl_sign}{pnl_pct:.2f}% ({pnl_sign}{pnl_pancakes:,} {PANCAKE})",
            inline=True,
        )
        embed.add_field(name="New Balance", value=f"{PANCAKE} **{new_balance:,}**", inline=True)
        embed.set_footer(text=f"Sold by {user.display_name}")
        await interaction.followup.send(embed=embed)

    # ------------------------------------------------------------------
    # /portfolio
    # ------------------------------------------------------------------

    @app_commands.command(
        name="portfolio",
        description="View your current stock holdings and their performance.",
    )
    async def portfolio(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        guild_id = interaction.guild_id
        user = interaction.user

        holdings = stocks.get_portfolio(guild_id, user.id)
        if not holdings:
            await interaction.followup.send(
                f"You have no stock investments! Use `/invest <ticker> <amount>` to get started.",
                ephemeral=True,
            )
            return

        # Fetch all prices concurrently
        prices = await stocks.get_prices_bulk(set(holdings.keys()))

        embed = discord.Embed(
            title=f"{CHART} {user.display_name}'s Portfolio",
            color=0x0099FF,
        )

        total_invested = 0.0
        total_value = 0.0

        for ticker, holding in holdings.items():
            held_shares = holding["shares"]
            avg_cost = holding["avg_cost"]
            invested = held_shares * avg_cost
            total_invested += invested

            current_price = prices.get(ticker)
            if current_price and current_price > 0:
                current_value = held_shares * current_price
                pnl_pct = ((current_price - avg_cost) / avg_cost) * 100
                pnl_sign = "+" if pnl_pct >= 0 else ""
                total_value += current_value
                value_str = (
                    f"Shares: **{held_shares:.4f}**\n"
                    f"Avg buy: ${avg_cost:,.2f} · Now: ${current_price:,.2f}\n"
                    f"Value: {PANCAKE} **{int(current_value):,}** "
                    f"({pnl_sign}{pnl_pct:.2f}%)"
                )
            else:
                current_value = invested
                total_value += current_value
                value_str = (
                    f"Shares: **{held_shares:.4f}**\n"
                    f"Avg buy: ${avg_cost:,.2f} · Price: *unavailable*\n"
                    f"Value: {PANCAKE} ~**{int(invested):,}**"
                )

            embed.add_field(name=f"📊 {ticker}", value=value_str, inline=False)

        if total_invested > 0:
            overall_pnl = (total_value - total_invested) / total_invested * 100
        else:
            overall_pnl = 0.0
        pnl_sign = "+" if overall_pnl >= 0 else ""

        cash_balance = currency.get_balance(guild_id, user.id)
        embed.add_field(
            name="── Summary ──",
            value=(
                f"Portfolio Value: {PANCAKE} **{int(total_value):,}** "
                f"({pnl_sign}{overall_pnl:.2f}%)\n"
                f"Cash Balance: {PANCAKE} **{cash_balance:,}**\n"
                f"Total Net Worth: {PANCAKE} **{int(total_value) + cash_balance:,}**"
            ),
            inline=False,
        )
        embed.set_footer(
            text="Holdings are liquidated at month end and added to your pancake balance."
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InvestCog(bot))
