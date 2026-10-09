import numpy as np


def matching_cost(pred_probs, pred_boxes, gt_labels, gt_boxes, w_class=1.0, w_l1=5.0):
    """-> cost [Q, G]"""
    raise NotImplementedError


def match(cost):
    """cost: [Q, G], Q >= G -> [(q, g), ...] 비용 합이 최소인 일대일 짝."""
    raise NotImplementedError
