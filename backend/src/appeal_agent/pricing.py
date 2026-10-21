"""Token cost in USD, from the per-1M-token prices in config.toml."""

from appeal_agent.config import settings


def cost_usd(
    model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int
) -> float | None:
    """Cost of one call, or None if the model has no configured price.

    Cached tokens are part of prompt_tokens and billed at the cached rate.
    """
    price = settings().get("pricing", {}).get(model)
    if price is None:
        return None
    uncached = prompt_tokens - cached_tokens
    return (
        uncached * price["input"]
        + cached_tokens * price["cached_input"]
        + completion_tokens * price["output"]
    ) / 1_000_000
