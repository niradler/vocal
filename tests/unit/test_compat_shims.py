"""Tests for the transformers compatibility shims in ``_compat``."""

import pytest

transformers = pytest.importorskip("transformers")

from vocal_core.adapters import _compat  # noqa: E402


class TestValidateLayerType:
    """transformers 5.3.x lacks PretrainedConfig.validate_layer_type."""

    def test_method_exists_after_shims(self):
        _compat.apply_transformers_shims()
        from transformers.configuration_utils import PretrainedConfig

        assert hasattr(PretrainedConfig, "validate_layer_type")

    def test_accepts_known_layer_types(self):
        _compat.apply_transformers_shims()
        from transformers.configuration_utils import PretrainedConfig

        config = PretrainedConfig()
        config.layer_types = ["full_attention", "sliding_attention"]
        config.validate_layer_type()  # must not raise

    def test_rejects_unknown_layer_type(self):
        _compat.apply_transformers_shims()
        from transformers.configuration_utils import PretrainedConfig

        config = PretrainedConfig()
        config.layer_types = ["full_attention", "quantum_attention"]
        with pytest.raises(ValueError, match="quantum_attention"):
            config.validate_layer_type()

    def test_tolerates_configs_without_layer_types(self):
        _compat.apply_transformers_shims()
        from transformers.configuration_utils import PretrainedConfig

        PretrainedConfig().validate_layer_type()  # must not raise

    def test_shims_are_idempotent(self):
        _compat.apply_transformers_shims()
        from transformers.configuration_utils import PretrainedConfig

        first = PretrainedConfig.validate_layer_type
        _compat._shims_applied = False
        try:
            _compat.apply_transformers_shims()
        finally:
            _compat._shims_applied = True
        assert PretrainedConfig.validate_layer_type is first
