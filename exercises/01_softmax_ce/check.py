import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from _check import Checker, close, load, numeric_grad

s = load(Path(__file__).parent)
rng = np.random.default_rng(0)

c = Checker("01. Softmax와 Cross-Entropy")
z = rng.normal(size=(5, 7))
y = rng.integers(0, 7, size=5)


def sums_to_one():
    p = s.softmax(z)
    close(p.sum(axis=1), np.ones(5), 1e-9, "행별 확률의 합")
    assert (p > 0).all(), "확률은 모두 양수여야 해요"


def shift_invariant():
    close(s.softmax(z + 100.0), s.softmax(z), 1e-9, "상수를 더한 뒤의 softmax")


def stable():
    big = np.array([[1000.0, 1001.0, 999.0], [-1000.0, 0.0, 1000.0]])
    p = s.softmax(big)
    assert np.isfinite(p).all(), "큰 logits에서 nan/inf 가 나와요. 최댓값을 빼고 exp 하세요"
    close(p[0], [0.24472847, 0.66524096, 0.09003057], 1e-6, "큰 logits의 softmax")
    loss, grad = s.cross_entropy(big, np.array([1, 0]))
    assert np.isfinite(loss) and np.isfinite(grad).all(), "큰 logits에서 loss나 기울기가 nan/inf 예요 (log(0) 을 피하세요)"


def uniform_loss():
    loss, _ = s.cross_entropy(np.zeros((4, 10)), np.array([0, 3, 5, 9]))
    close(loss, np.log(10), 1e-9, "균등 logits의 loss")


def gradient():
    loss, grad = s.cross_entropy(z, y)
    want = numeric_grad(lambda v: s.cross_entropy(v, y)[0], z.copy())
    close(grad, want, 1e-6, "dlogits")
    close(grad.sum(axis=1), np.zeros(5), 1e-9, "dlogits의 행별 합(0이어야 함)")


c.check("확률의 합이 1", sums_to_one)
c.check("상수 이동에 불변", shift_invariant)
c.check("큰 값에서 수치적으로 안정", stable)
c.check("균등 logits에서 loss = log C", uniform_loss)
c.check("기울기가 수치 기울기와 일치", gradient)
c.finish()
