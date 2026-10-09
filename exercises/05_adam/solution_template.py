import numpy as np


def adam_step(param, grad, m, v, t, lr=1e-3, beta1=0.9, beta2=0.999, eps=1e-8):
    """한 스텝. t 는 1부터. -> (param, m, v)"""
    raise NotImplementedError


def adamw_step(param, grad, m, v, t, lr=1e-3, beta1=0.9, beta2=0.999, eps=1e-8, weight_decay=1e-2):
    """decoupled weight decay. -> (param, m, v)"""
    raise NotImplementedError
