import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from _check import Checker, close, load, numeric_grad

s = load(Path(__file__).parent)
rng = np.random.default_rng(0)

c = Checker("06. Scaled Dot-Product Attention")
B, T, S, d, dv = 2, 4, 5, 8, 3
q, k, v = rng.normal(size=(B, T, d)), rng.normal(size=(B, S, d)), rng.normal(size=(B, S, dv))


def ref(q, k, v, mask=None):
    out, weights = np.zeros((q.shape[0], q.shape[1], v.shape[2])), np.zeros((q.shape[0], q.shape[1], k.shape[1]))
    for b in range(q.shape[0]):
        for t in range(q.shape[1]):
            scores = np.array([q[b, t] @ k[b, j] / np.sqrt(q.shape[2]) for j in range(k.shape[1])])
            if mask is not None:
                scores = np.where(np.broadcast_to(mask, weights.shape)[b, t], scores, -np.inf)
            e = np.exp(scores - scores.max())
            weights[b, t] = e / e.sum()
            out[b, t] = weights[b, t] @ v[b]
    return out, weights


def basic():
    out, w = s.scaled_dot_product_attention(q, k, v)
    assert np.shape(out) == (B, T, dv) and np.shape(w) == (B, T, S), f"모양이 out {np.shape(out)}, weights {np.shape(w)} 예요"
    close(w.sum(axis=-1), np.ones((B, T)), 1e-9, "가중치의 합")
    want_out, want_w = ref(q, k, v)
    close(w, want_w, 1e-9, "가중치 (sqrt(d) 로 나눴는지 확인하세요)")
    close(out, want_out, 1e-9, "출력")


def zero_query_is_uniform():
    out, w = s.scaled_dot_product_attention(np.zeros((B, T, d)), k, v)
    close(w, np.full((B, T, S), 1 / S), 1e-12, "q = 0 일 때의 가중치(균등해야 함)")
    close(out, np.broadcast_to(v.mean(axis=1, keepdims=True), (B, T, dv)), 1e-12, "q = 0 일 때의 출력(v의 평균)")


def masking():
    mask = rng.random((B, T, S)) > 0.4
    mask[..., 0] = True   # 줄마다 볼 수 있는 자리가 하나는 있게
    out, w = s.scaled_dot_product_attention(q, k, v, mask)
    assert (w[~mask] == 0).all(), "마스크가 False인 자리의 가중치가 0이 아니에요"
    close(w.sum(axis=-1), np.ones((B, T)), 1e-9, "마스크를 건 뒤 가중치의 합")
    want_out, want_w = ref(q, k, v, mask)
    close(w, want_w, 1e-9, "마스크를 건 가중치")
    close(out, want_out, 1e-9, "마스크를 건 출력")


def causal():
    m = np.asarray(s.causal_mask(4))
    assert m.dtype == bool and m.shape == (4, 4), f"causal_mask(4) 는 (4, 4) bool 이어야 해요 (지금 {m.shape}, {m.dtype})"
    assert (m == np.tril(np.ones((4, 4), dtype=bool))).all(), "아래 삼각(대각 포함)만 True 여야 해요"
    x = rng.normal(size=(1, 6, d))
    out1, _ = s.scaled_dot_product_attention(x, x, x, s.causal_mask(6))
    x2 = x.copy()
    x2[0, 4:] += 5.0   # 뒤쪽 토큰을 바꿔도
    out2, _ = s.scaled_dot_product_attention(x2, x2, x2, s.causal_mask(6))
    close(out2[0, :4], out1[0, :4], 1e-9, "미래 토큰을 바꿨을 때 앞쪽 위치의 출력(변하면 안 돼요)")


def stable_and_equivariant():
    out, w = s.scaled_dot_product_attention(q * 1e3, k * 1e3, v)
    assert np.isfinite(out).all() and np.isfinite(w).all(), "점수가 클 때 nan/inf 가 나와요 (softmax 전에 최댓값을 빼세요)"
    perm = rng.permutation(S)
    out_p, _ = s.scaled_dot_product_attention(q, k[:, perm], v[:, perm])
    close(out_p, s.scaled_dot_product_attention(q, k, v)[0], 1e-9, "key/value 순서를 섞은 뒤의 출력(같아야 함)")


c.check("모양, 합이 1, 값", basic)
c.check("q = 0 이면 균등 가중치", zero_query_is_uniform)
c.check("마스크", masking)
c.check("causal mask: 미래를 보지 않음", causal)
c.check("수치 안정성, 순서 불변", stable_and_equivariant)
c.finish()
