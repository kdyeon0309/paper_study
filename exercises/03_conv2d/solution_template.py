import numpy as np


def conv2d_forward(x, w, b, stride=1, pad=0):
    """x: [N, C, H, W], w: [F, C, kh, kw], b: [F] -> out: [N, F, H', W']"""
    raise NotImplementedError


def conv2d_backward(dout, x, w, b, stride=1, pad=0):
    """dout: [N, F, H', W'] -> (dx, dw, db). 각각 x, w, b 와 같은 모양."""
    raise NotImplementedError
