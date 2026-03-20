"""Tests for ML utility modules."""
import pytest

torch = pytest.importorskip(
    "torch",
    reason="Install requirements-ml.txt to run ML utility tests.",
)

from ml.utils.device import get_device, seed_everything


def test_get_device_returns_torch_device():
    device = get_device(verbose=False)
    assert isinstance(device, torch.device)
    assert device.type in ("cpu", "cuda", "mps")


def test_seed_everything_is_deterministic():
    seed_everything(42)
    a = torch.randn(5)
    seed_everything(42)
    b = torch.randn(5)
    assert torch.allclose(a, b)


def test_different_seeds_differ():
    seed_everything(42)
    a = torch.randn(5)
    seed_everything(99)
    b = torch.randn(5)
    assert not torch.allclose(a, b)
