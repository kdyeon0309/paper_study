import numpy as np


def scaled_dot_product_attention(q, k, v, mask=None):
    """q: [B, T, d], k: [B, S, d], v: [B, S, dv], mask: bool (True = 볼 수 있음) -> (out [B, T, dv], weights [B, T, S])"""
    raise NotImplementedError


def causal_mask(T):
    """[T, T] bool. 위치 i 가 위치 j (j <= i) 를 볼 수 있으면 True."""
    raise NotImplementedError
