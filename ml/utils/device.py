"""Helpers for ML device selection and seeding.

These utilities are optional at runtime. The main product stack can run in mock
mode without installing heavyweight ML dependencies from ``requirements-ml.txt``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch


def _require_torch():
    try:
        import torch
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyTorch is not installed. Install requirements-ml.txt to use ML utilities."
        ) from exc
    return torch


def get_device(verbose: bool = True) -> "torch.device":
    """Select the best available compute device.

    Priority: CUDA (NVIDIA GPU) > MPS (Apple Silicon) > CPU.
    """
    torch = _require_torch()

    if torch.cuda.is_available():
        device = torch.device("cuda")
        name = torch.cuda.get_device_name(0)
        if verbose:
            print(f"[Device] Using CUDA: {name}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        if verbose:
            print("[Device] Using MPS (Apple Silicon)")
    else:
        device = torch.device("cpu")
        if verbose:
            print("[Device] Using CPU")
    return device


def get_device_str() -> str:
    """Return device string for libraries that expect 'cuda' / 'mps' / 'cpu'."""
    return str(get_device(verbose=False))


def seed_everything(seed: int = 42) -> None:
    """Set random seeds for reproducibility across all backends."""
    import random
    import numpy as np
    torch = _require_torch()

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
