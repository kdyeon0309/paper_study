import numpy as np


def softmax(logits):
    """logits: [N, C] -> probs: [N, C]. 큰 값에서도 넘치지 않아야 한다."""
    raise NotImplementedError


def cross_entropy(logits, y):
    """logits: [N, C], y: [N] 정수 라벨 -> (배치 평균 loss, dlogits [N, C])"""
    raise NotImplementedError
