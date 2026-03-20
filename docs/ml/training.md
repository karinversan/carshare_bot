# Training

## Quality + viewpoint
Entry point:
`ml/quality_view/training/train.py`

Example:
`python -m ml.quality_view.training.train --config ml/quality_view/configs/efficientnet_b0_multitask.yaml`

Outputs:
- `ml/quality_view/weights/best_quality_view.pt`
- `ml/quality_view/weights/metadata.json`

## Damage segmentation
Entry point:
`ml/damage_seg/training/train_yolo.py`

Example:
`python -m ml.damage_seg.training.train_yolo --config ml/damage_seg/configs/yolo_seg_v1.yaml`

Outputs:
- `ml/damage_seg/weights/best_damage_seg.pt`
- `ml/damage_seg/weights/metadata.json`
- `ml/damage_seg/weights/*_metrics.json`

## Paired evaluation
Entry point:
`ml/evaluation/paired_eval/run_paired_eval.py`

Example:
`python -m ml.evaluation.paired_eval.run_paired_eval --config ml/evaluation/paired_eval/configs/default.yaml`

Unified quality report:
`python -m ml.evaluation.build_model_quality_report --refresh-paired`

The repo already contains working training/evaluation entrypoints suitable for demo workflows.
W&B/MLflow logging remains optional and can be enabled via environment/config.
