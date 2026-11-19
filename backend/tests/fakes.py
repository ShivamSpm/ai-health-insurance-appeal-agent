"""Shared test doubles. The scripted model itself lives in the package, so that
`appeal-agent serve --fake-model` can use it for end-to-end UI tests."""

from appeal_agent.agent.scripted import perfect_findings, scripted_model

__all__ = ["perfect_findings", "perfect_model"]


def perfect_model(case_ids_seen: list):
    """A fake model that reads the case ID from the task and answers from the labels."""
    return scripted_model(case_ids_seen)
