import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from _check import Checker, close, load, numeric_grad

s = load(Path(__file__).parent)
rng = np.random.default_rng(0)

c = Checker("03. Conv2d 순전파와 역전파")


def ref_forward(x, w, b, stride, pad):
    n, ch, h, wd = x.shape
    f, _, kh, kw = w.shape
    xp = np.pad(x, ((0, 0), (0, 0), (pad, pad), (pad, pad)))
    oh, ow = (h + 2 * pad - kh) // stride + 1, (wd + 2 * pad - kw) // stride + 1
    out = np.zeros((n, f, oh, ow))
    for i in range(n):
        for j in range(f):
            for p in range(oh):
                for q in range(ow):
                    out[i, j, p, q] = (xp[i, :, p * stride:p * stride + kh, q * stride:q * stride + kw] * w[j]).sum() + b[j]
    return out


CASES = [(1, 0), (1, 1), (2, 0), (2, 1)]


def shapes():
    x, w, b = rng.normal(size=(2, 3, 7, 8)), rng.normal(size=(4, 3, 3, 3)), rng.normal(size=4)
    for stride, pad in CASES:
        got = np.shape(s.conv2d_forward(x, w, b, stride, pad))
        want = (2, 4, (7 + 2 * pad - 3) // stride + 1, (8 + 2 * pad - 3) // stride + 1)
        assert got == want, f"stride={stride}, pad={pad} 에서 출력 모양이 {got} 인데 {want} 이어야 해요"


def forward_values():
    x, w, b = rng.normal(size=(2, 3, 6, 7)), rng.normal(size=(4, 3, 3, 2)), rng.normal(size=4)
    for stride, pad in CASES:
        close(s.conv2d_forward(x, w, b, stride, pad), ref_forward(x, w, b, stride, pad), 1e-9, f"출력(stride={stride}, pad={pad})")


def one_by_one():
    x, w, b = rng.normal(size=(2, 3, 4, 4)), rng.normal(size=(5, 3, 1, 1)), rng.normal(size=5)
    want = np.einsum("nchw,fc->nfhw", x, w[:, :, 0, 0]) + b[None, :, None, None]
    close(s.conv2d_forward(x, w, b), want, 1e-9, "1x1 conv 출력 (채널별 선형 변환과 같아야 함)")


def backward():
    for stride, pad in CASES:
        x, w, b = rng.normal(size=(2, 2, 5, 6)), rng.normal(size=(3, 2, 3, 3)), rng.normal(size=3)
        dout = rng.normal(size=ref_forward(x, w, b, stride, pad).shape)
        loss = lambda *_: float((s.conv2d_forward(x, w, b, stride, pad) * dout).sum())
        dx, dw, db = s.conv2d_backward(dout, x, w, b, stride, pad)
        tag = f"(stride={stride}, pad={pad})"
        close(dx, numeric_grad(loss, x), 1e-6, f"dx {tag}")
        close(dw, numeric_grad(loss, w), 1e-6, f"dw {tag}")
        close(db, numeric_grad(loss, b), 1e-6, f"db {tag}")


c.check("출력 크기", shapes)
c.check("순전파 값 (for 문 구현과 비교)", forward_values)
c.check("1x1 conv는 채널별 선형 변환", one_by_one)
c.check("역전파가 수치 기울기와 일치", backward)
c.finish()
