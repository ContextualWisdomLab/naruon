from api.search import resolve_fusion_settings
from core.config import settings


def test_resolve_fusion_settings_loads_from_config(monkeypatch):
    """Resolve rank-fusion settings from the configured application values."""

    monkeypatch.setattr(settings, "SEARCH_FUSION_STRATEGY", "reciprocal_rank_fusion")
    monkeypatch.setattr(settings, "SEARCH_FUSION_SEMANTIC_WEIGHT", 0.9)
    monkeypatch.setattr(settings, "SEARCH_RRF_RANK_CONSTANT", 100)

    result = resolve_fusion_settings()

    assert result.strategy_name == "reciprocal_rank_fusion"
    assert result.semantic_weight_alpha == 0.9
    assert result.rank_constant_eta == 100
