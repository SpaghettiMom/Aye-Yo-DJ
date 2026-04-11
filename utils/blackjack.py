"""
Blackjack game module
Handles blackjack game logic and gameplay
"""
import random

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RANK_VALUES = {
    "A": 11, "2": 2, "3": 3, "4": 4, "5": 5,
    "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 10, "Q": 10, "K": 10,
}

# State constants
STATE_PLAYING = "playing"
STATE_BLACKJACK = "blackjack"
STATE_PLAYER_BUST = "player_bust"
STATE_DEALER_BUST = "dealer_bust"
STATE_WIN = "win"
STATE_LOSE = "lose"
STATE_PUSH = "push"


def _make_deck() -> list:
    return [(rank, suit) for suit in SUITS for rank in RANKS]


def card_str(card: tuple) -> str:
    return f"{card[0]}{card[1]}"


def hand_str(hand: list, hide_second: bool = False) -> str:
    """Return a human-readable string for a hand of cards."""
    if not hand:
        return "(empty)"
    if hide_second and len(hand) >= 2:
        return f"{card_str(hand[0])}  🂠"
    return "  ".join(card_str(c) for c in hand)


def hand_value(hand: list) -> int:
    """Calculate the best value of a hand, counting Aces as 1 or 11."""
    value = sum(RANK_VALUES[rank] for rank, _ in hand)
    aces = sum(1 for rank, _ in hand if rank == "A")
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value


class BlackjackGame:
    """Manages a single round of blackjack."""

    def __init__(self, bet: int):
        self.initial_bet = bet
        self.total_bet = bet          # doubles if player doubles down
        self.deck = _make_deck()
        random.shuffle(self.deck)
        self.player_hand: list = []
        self.dealer_hand: list = []
        self.state: str = STATE_PLAYING

    def deal(self) -> None:
        """Deal two cards each to the player and dealer."""
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        if hand_value(self.player_hand) == 21:
            self.state = STATE_BLACKJACK

    def hit(self) -> None:
        """Player draws one more card."""
        self.player_hand.append(self.deck.pop())
        if hand_value(self.player_hand) > 21:
            self.state = STATE_PLAYER_BUST

    def stand(self) -> None:
        """Player stands; dealer plays out."""
        self._dealer_play()

    def double_down(self) -> None:
        """Double the bet, deal exactly one card, then stand."""
        self.total_bet *= 2
        self.player_hand.append(self.deck.pop())
        if hand_value(self.player_hand) > 21:
            self.state = STATE_PLAYER_BUST
        else:
            self._dealer_play()

    def _dealer_play(self) -> None:
        """Dealer draws until reaching 17+ then determines winner."""
        while hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        player_val = hand_value(self.player_hand)
        dealer_val = hand_value(self.dealer_hand)

        if dealer_val > 21:
            self.state = STATE_DEALER_BUST
        elif player_val > dealer_val:
            self.state = STATE_WIN
        elif player_val < dealer_val:
            self.state = STATE_LOSE
        else:
            self.state = STATE_PUSH

    def winnings(self) -> int:
        """
        Return the gross amount to credit back to the player.
        The initial bet has already been deducted; this is what gets added back.
          - Blackjack (3:2): total_bet + floor(total_bet * 1.5)
          - Win / dealer bust: total_bet * 2
          - Push: total_bet (bet returned)
          - Lose / player bust: 0
        """
        if self.state == STATE_BLACKJACK:
            return self.total_bet + int(self.total_bet * 1.5)
        if self.state in (STATE_WIN, STATE_DEALER_BUST):
            return self.total_bet * 2
        if self.state == STATE_PUSH:
            return self.total_bet
        return 0


# Upcoming blackjack command template:
# @app_commands.command(name="blackjack")
# async def blackjack(self, interaction: discord.Interaction, bet_amount: int):
#     """Play blackjack!"""
#     # Implementation will go here
#     pass
