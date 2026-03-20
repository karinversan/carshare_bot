"""Custom Ultralytics trainer that avoids background-only train batches."""

from __future__ import annotations

import math
import os
import random
from typing import Iterator

import numpy as np
import torch
from torch.utils.data import Sampler
from ultralytics.data import build_dataloader
from ultralytics.data.build import InfiniteDataLoader, seed_worker
from ultralytics.models.yolo.segment.train import SegmentationTrainer
from ultralytics.utils import LOGGER, RANK
from ultralytics.utils.torch_utils import torch_distributed_zero_first


class PositiveBatchSampler(Sampler[int]):
    """Sampler that ensures each batch contains at least one positive example when possible."""

    def __init__(self, dataset, batch_size: int, seed: int = 42):
        self.dataset = dataset
        self.batch_size = max(int(batch_size), 1)
        self.seed = int(seed)
        self.epoch = 0

        self.positive_indices = [i for i, label in enumerate(dataset.labels) if len(label.get("cls", [])) > 0]
        self.negative_indices = [i for i, label in enumerate(dataset.labels) if len(label.get("cls", [])) == 0]
        self.num_samples = len(dataset)
        self.num_batches = math.ceil(self.num_samples / self.batch_size) if self.num_samples else 0

        if not self.positive_indices:
            raise ValueError("PositiveBatchSampler requires at least one positive-labeled sample.")
        if len(self.positive_indices) < self.num_batches:
            LOGGER.warning(
                "PositiveBatchSampler cannot guarantee a positive in every batch: %d positive images for %d batches.",
                len(self.positive_indices),
                self.num_batches,
            )

    def __len__(self) -> int:
        return self.num_samples

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def __iter__(self) -> Iterator[int]:
        rnd = random.Random(self.seed + self.epoch)
        positives = list(self.positive_indices)
        negatives = list(self.negative_indices)
        rnd.shuffle(positives)
        rnd.shuffle(negatives)

        batches = [[] for _ in range(self.num_batches)]

        reserved = min(len(positives), self.num_batches)
        for batch_idx in range(reserved):
            batches[batch_idx].append(positives.pop())

        remaining = positives + negatives
        rnd.shuffle(remaining)

        cursor = 0
        for sample_idx in remaining:
            while cursor < self.num_batches and len(batches[cursor]) >= self.batch_size:
                cursor += 1
            if cursor >= self.num_batches:
                break
            batches[cursor].append(sample_idx)

        rnd.shuffle(batches)
        flat_indices = [sample_idx for batch in batches for sample_idx in batch]
        if len(flat_indices) != self.num_samples:
            raise RuntimeError(f"Sampler produced {len(flat_indices)} indices for dataset of size {self.num_samples}")
        return iter(flat_indices)


class PositiveBatchSegmentationTrainer(SegmentationTrainer):
    """Segmentation trainer with a positive-aware train sampler."""

    def get_dataloader(self, dataset_path: str, batch_size: int = 16, rank: int = 0, mode: str = "train"):
        assert mode in {"train", "val"}, f"Mode must be 'train' or 'val', not {mode}."
        with torch_distributed_zero_first(rank):
            dataset = self.build_dataset(dataset_path, mode, batch_size)

        shuffle = mode == "train"
        if getattr(dataset, "rect", False) and shuffle and not np.all(dataset.batch_shapes == dataset.batch_shapes[0]):
            LOGGER.warning("'rect=True' is incompatible with DataLoader shuffle, setting shuffle=False")
            shuffle = False

        if mode != "train" or rank != -1:
            return build_dataloader(
                dataset,
                batch=batch_size,
                workers=self.args.workers if mode == "train" else self.args.workers * 2,
                shuffle=shuffle,
                rank=rank,
                drop_last=self.args.compile and mode == "train",
            )

        effective_batch = min(batch_size, len(dataset))
        sampler = PositiveBatchSampler(dataset, batch_size=effective_batch, seed=getattr(self.args, "seed", 42))
        nd = torch.cuda.device_count()
        nw = min(os.cpu_count() // max(nd, 1), self.args.workers)
        generator = torch.Generator()
        generator.manual_seed(6148914691236517205 + RANK)

        LOGGER.info(
            "Using PositiveBatchSampler for train: %d positive, %d background, batch=%d",
            len(sampler.positive_indices),
            len(sampler.negative_indices),
            effective_batch,
        )

        return InfiniteDataLoader(
            dataset=dataset,
            batch_size=effective_batch,
            shuffle=False,
            num_workers=nw,
            sampler=sampler,
            prefetch_factor=4 if nw > 0 else None,
            pin_memory=nd > 0,
            collate_fn=getattr(dataset, "collate_fn", None),
            worker_init_fn=seed_worker,
            generator=generator,
            drop_last=self.args.compile and len(dataset) % effective_batch != 0,
        )

