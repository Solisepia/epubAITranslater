from __future__ import annotations

from .models import TranslationResult


def post_edit(results: list[TranslationResult]) -> list[TranslationResult]:
    # Reserved for deterministic punctuation/style normalization in future revisions.
    return results
