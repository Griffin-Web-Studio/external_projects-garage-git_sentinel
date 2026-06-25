from __future__ import annotations

from src.migrations import chain

# ───────────────────────────────────────────────────────────────────| chain |──


class TestMigrationsChain:
    """Tests the module-level chain discovers the expected migrations."""

    def test_chain_has_v0001_step(self) -> None:
        """The module-level chain contains the step that goes from v0 to v1."""
        assert 0 in chain._steps
        assert chain._steps[0].to_version == 1
