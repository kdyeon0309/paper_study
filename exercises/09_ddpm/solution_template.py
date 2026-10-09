import numpy as np


def q_sample(x0, t, alphas_cumprod, noise):
    """x0: [B, ...], t: [B] 정수, alphas_cumprod: [T] -> x_t"""
    raise NotImplementedError


def predict_x0(xt, t, eps, alphas_cumprod):
    """x_t 와 노이즈 예측 eps 로 x0 를 복원한다."""
    raise NotImplementedError


def p_mean(xt, t, eps, betas):
    """역방향 한 스텝 p(x_{t-1} | x_t) 의 평균. betas: [T]"""
    raise NotImplementedError
