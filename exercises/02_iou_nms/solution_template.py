import numpy as np


def box_iou(a, b):
    """a: [N, 4], b: [M, 4], 좌표는 (x1, y1, x2, y2) -> IoU 행렬 [N, M]"""
    raise NotImplementedError


def nms(boxes, scores, iou_threshold):
    """남긴 상자의 인덱스를 점수 내림차순으로 돌려준다. IoU > iou_threshold 인 상자를 지운다."""
    raise NotImplementedError
