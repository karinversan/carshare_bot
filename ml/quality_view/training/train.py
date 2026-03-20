#!/usr/bin/env python3
"""CLI: Train Quality + View multitask model (EfficientNet-B0).

Usage:
    python -m ml.quality_view.training.train \
        --config ml/quality_view/configs/efficientnet_b0_multitask.yaml
"""
import argparse, json, logging, sys
from pathlib import Path

import torch, torch.nn as nn, yaml
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ml.utils.device import get_device, seed_everything

QUALITY_CLASSES = ["good", "blur", "dark", "overexposed"]
VIEW_CLASSES = ["front_left_3q", "front_right_3q", "rear_left_3q", "rear_right_3q"]

class QVDataset(Dataset):
    def __init__(self, root: Path, split: str, size: int = 384):
        self.samples: list[tuple[Path, int, int]] = []
        d = root / split
        if not d.exists(): return
        for qi, q in enumerate(QUALITY_CLASSES):
            for vi, v in enumerate(VIEW_CLASSES):
                for p in sorted((d / f"{q}_{v}").glob("*.jpg")) + sorted((d / f"{q}_{v}").glob("*.png")) if (d / f"{q}_{v}").exists() else []:
                    self.samples.append((p, qi, vi))
        self.tf = transforms.Compose([transforms.Resize((size, size)), transforms.ToTensor(), transforms.Normalize([.485,.456,.406],[.229,.224,.225])])

    def __len__(self): return len(self.samples)
    def __getitem__(self, i):
        from PIL import Image
        p, q, v = self.samples[i]
        return self.tf(Image.open(p).convert("RGB")), q, v

class QVModel(nn.Module):
    def __init__(self, nq=4, nv=4, backbone="efficientnet_b0", pretrained=True):
        super().__init__()
        import timm
        self.backbone = timm.create_model(backbone, pretrained=pretrained, num_classes=0)
        d = self.backbone.num_features
        self.q_head = nn.Sequential(nn.Dropout(0.3), nn.Linear(d, nq))
        self.v_head = nn.Sequential(nn.Dropout(0.3), nn.Linear(d, nv))
    def forward(self, x):
        f = self.backbone(x)
        return self.q_head(f), self.v_head(f)

def train(cfg: dict):
    seed_everything(cfg.get("seed", 42))
    device = get_device()
    sz = cfg["data"]["image_size"]; bs = cfg["data"]["batch_size"]
    nw = cfg["data"].get("num_workers", 4); ep = cfg["trainer"]["epochs"]
    pat = cfg["trainer"].get("early_stopping_patience", 5)

    data_root = ROOT / "data" / "quality_view"
    tr_ds = QVDataset(data_root, "train", sz); va_ds = QVDataset(data_root, "val", sz)
    if not len(tr_ds):
        logger.error("No data at %s — run notebook 01 first.", data_root); sys.exit(1)

    tr_dl = DataLoader(tr_ds, bs, shuffle=True, num_workers=nw, pin_memory=True)
    va_dl = DataLoader(va_ds, bs, num_workers=nw, pin_memory=True)

    model = QVModel(backbone=cfg["model"]["backbone"], pretrained=cfg["model"].get("pretrained", True)).to(device)
    crit_q = nn.CrossEntropyLoss(); crit_v = nn.CrossEntropyLoss()
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=ep)

    wandb_run = None
    try:
        import wandb
        wandb_run = wandb.init(project=cfg.get("logging",{}).get("wandb_project","qv"), config=cfg, name=cfg.get("experiment_name"))
    except Exception: pass

    best_vl = float("inf"); no_imp = 0
    w_dir = ROOT / "ml" / "quality_view" / "weights"; w_dir.mkdir(parents=True, exist_ok=True)
    bp = w_dir / "best_quality_view.pt"

    for e in range(1, ep+1):
        model.train(); tl = 0.0
        for imgs, ql, vl in tr_dl:
            imgs, ql, vl = imgs.to(device), ql.to(device), vl.to(device)
            qo, vo = model(imgs); loss = crit_q(qo, ql) + crit_v(vo, vl)
            opt.zero_grad(); loss.backward(); opt.step()
            tl += loss.item() * imgs.size(0)
        sched.step(); tl /= len(tr_ds)

        model.eval(); vls = cq = cv = 0
        with torch.no_grad():
            for imgs, ql, vl in va_dl:
                imgs, ql, vl = imgs.to(device), ql.to(device), vl.to(device)
                qo, vo = model(imgs)
                vls += (crit_q(qo, ql) + crit_v(vo, vl)).item() * imgs.size(0)
                cq += (qo.argmax(1)==ql).sum().item(); cv += (vo.argmax(1)==vl).sum().item()
        vl_avg = vls / max(len(va_ds),1); qa = cq / max(len(va_ds),1); va = cv / max(len(va_ds),1)
        logger.info("E%d/%d tl=%.4f vl=%.4f qa=%.3f va=%.3f", e, ep, tl, vl_avg, qa, va)
        if wandb_run: wandb_run.log({"train_loss": tl, "val_loss": vl_avg, "q_acc": qa, "v_acc": va})

        if vl_avg < best_vl:
            best_vl = vl_avg; no_imp = 0; torch.save(model.state_dict(), bp); logger.info("Saved best (%.4f)", vl_avg)
        else:
            no_imp += 1
            if no_imp >= pat: logger.info("Early stop e%d", e); break

    (w_dir / "metadata.json").write_text(json.dumps({"model": cfg["model"]["backbone"], "best_val_loss": best_vl, "quality_classes": QUALITY_CLASSES, "view_classes": VIEW_CLASSES, "image_size": sz}, indent=2))
    logger.info("Done. Weights → %s", bp)
    if wandb_run: wandb_run.finish()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    cfg = yaml.safe_load(Path(p.parse_args().config).read_text())
    train(cfg)

if __name__ == "__main__": main()
