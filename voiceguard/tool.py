from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class TrainResult:
    origin: str
    destination: str
    trains: list[str]


@dataclass(frozen=True)
class TransferResult:
    amount: int
    recipient: str
    status: str


async def search_trains(
    origin: str,
    destination: str,
    *,
    min_delay: float = 3.0,
    max_delay: float = 8.0,
    rng: random.Random | None = None,
) -> TrainResult:
    """Fake delayed train-search tool."""
    if min_delay < 0 or max_delay < min_delay:
        raise ValueError("invalid delay range")

    delay = (rng or random).uniform(min_delay, max_delay)

    await asyncio.sleep(delay)

    return TrainResult(
        origin=origin,
        destination=destination,
        trains=[
            "08:10 Express",
            "10:45 Intercity",
            "14:20 Regional",
        ],
    )


async def simulate_transfer(
    amount: int,
    recipient: str,
    *,
    min_delay: float = 3.0,
    max_delay: float = 8.0,
    rng: random.Random | None = None,
) -> TransferResult:
    """
    Fake banking transfer tool.

    This never performs a real financial transaction.
    The delay intentionally creates an in-flight computation
    that VoxLock can cancel or supersede.
    """
    if amount <= 0:
        raise ValueError("transfer amount must be positive")

    if not recipient.strip():
        raise ValueError("recipient must not be empty")

    if min_delay < 0 or max_delay < min_delay:
        raise ValueError("invalid delay range")

    delay = (rng or random).uniform(min_delay, max_delay)

    await asyncio.sleep(delay)

    return TransferResult(
        amount=amount,
        recipient=recipient.strip(),
        status="simulated",
    )