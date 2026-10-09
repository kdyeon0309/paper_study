import numpy as np


def bn_forward(x, gamma, beta, running_mean, running_var, train, momentum=0.9, eps=1e-5):
    """x: [N, D] -> (out, cache, running_mean, running_var)"""
    raise NotImplementedError


def bn_backward(dout, cache):
    """학습 모드의 역전파. -> (dx, dgamma, dbeta)"""
    raise NotImplementedError
