import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from _check import Checker, close, load, numeric_grad

s = load(Path(__file__).parent)
rng = np.random.default_rng(0)

c = Checker("07. Focal Loss")
x = rng.normal(scale=2.0, size=12)
y = rng.integers(0, 2, size=12).astype(float)


def bce(x, y):
    return np.mean(np.maximum(x, 0) - x * y + np.log1p(np.exp(-np.abs(x))))


def reduces_to_bce():
    loss, _ = s.focal_loss(x, y, alpha=0.5, gamma=0.0)
    close(loss, 0.5 * bce(x, y), 1e-9, "gamma=0, alpha=0.5 일 때의 loss (BCE의 절반이어야 함)")


def hand_values():
    loss, _ = s.focal_loss(np.array([0.0]), np.array([1.0]))
    close(loss, 0.25 * 0.25 * np.log(2), 1e-12, "x=0, y=1 의 loss")
    loss, _ = s.focal_loss(np.array([0.0]), np.array([0.0]))
    close(loss, 0.75 * 0.25 * np.log(2), 1e-12, "x=0, y=0 의 loss (음성 예제의 alpha_t 는 1 - alpha)")


def down_weights_easy():
    logit = np.log(0.9 / 0.1)   # p = 0.9
    easy, _ = s.focal_loss(np.array([logit]), np.array([1.0]), alpha=1.0, gamma=2.0)
    hard, _ = s.focal_loss(np.array([-logit]), np.array([1.0]), alpha=1.0, gamma=2.0)
    close(easy, 0.1 ** 2 * -np.log(0.9), 1e-12, "쉬운 예제(p_t=0.9)의 loss")
    close(hard, 0.9 ** 2 * -np.log(0.1), 1e-12, "어려운 예제(p_t=0.1)의 loss")


def gradient():
    for alpha, gamma in ((0.25, 2.0), (0.6, 0.0), (0.5, 3.5)):
        _, grad = s.focal_loss(x, y, alpha, gamma)
        want = numeric_grad(lambda v: s.focal_loss(v, y, alpha, gamma)[0], x.copy())
        close(grad, want, 1e-7, f"dlogits (alpha={alpha}, gamma={gamma})")


def stable():
    big = np.array([-500.0, 500.0, -50.0, 50.0])
    for t in (np.zeros(4), np.ones(4)):
        loss, grad = s.focal_loss(big, t)
        assert np.isfinite(loss) and np.isfinite(grad).all(), "큰 logits에서 nan/inf 가 나와요. log(sigmoid(x)) 대신 log-sum-exp 꼴을 쓰세요"
    loss, _ = s.focal_loss(np.array([-50.0]), np.array([1.0]), alpha=1.0, gamma=0.0)
    close(loss, 50.0, 1e-9, "x=-50, y=1 의 loss (gamma=0 이면 약 50)")


c.check("gamma = 0 이면 가중 BCE", reduces_to_bce)
c.check("손으로 계산한 값", hand_values)
c.check("쉬운 예제의 loss를 줄임", down_weights_easy)
c.check("기울기가 수치 기울기와 일치", gradient)
c.check("큰 logits에서 수치적으로 안정", stable)
c.finish()
