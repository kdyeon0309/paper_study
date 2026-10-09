import numpy as np


def focal_loss(logits, targets, alpha=0.25, gamma=2.0):
    """logits: [N], targets: [N] (0/1) -> (배치 평균 loss, dlogits [N])"""
    raise NotImplementedError
