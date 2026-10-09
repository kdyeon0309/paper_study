import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from _check import Checker, close, load, numeric_grad

s = load(Path(__file__).parent)
rng = np.random.default_rng(0)

import itertools
import time

c = Checker("08. DETR의 이분 매칭")


def total(cost, pairs):
    return sum(cost[q, g] for q, g in pairs)


def valid(cost, pairs):
    pairs = [(int(q), int(g)) for q, g in pairs]
    Q, G = cost.shape
    assert sorted(g for _, g in pairs) == list(range(G)), f"모든 정답이 정확히 한 번씩 짝지어져야 해요 (정답 {G}개, 결과 {pairs})"
    assert len({q for q, _ in pairs}) == G and all(0 <= q < Q for q, _ in pairs), "한 예측이 두 정답과 짝지어졌거나 범위를 벗어났어요"
    return pairs


def brute(cost):
    Q, G = cost.shape
    return min(sum(cost[q, g] for g, q in enumerate(perm)) for perm in itertools.permutations(range(Q), G))


def cost_values():
    probs = np.array([[0.7, 0.2, 0.1], [0.1, 0.1, 0.8]])
    boxes = np.array([[0.5, 0.5, 0.2, 0.2], [0.1, 0.1, 0.4, 0.4]])
    gt_labels, gt_boxes = np.array([2, 0, 2]), np.array([[0.1, 0.1, 0.4, 0.4], [0.5, 0.5, 0.2, 0.3], [0.0, 0.0, 0.0, 0.0]])
    got = s.matching_cost(probs, boxes, gt_labels, gt_boxes, w_class=1.0, w_l1=5.0)
    want = np.array([[-0.1 + 5 * 1.2, -0.7 + 5 * 0.1, -0.1 + 5 * 1.4],
                     [-0.8 + 5 * 0.0, -0.1 + 5 * 1.1, -0.8 + 5 * 1.0]])
    close(got, want, 1e-9, "비용 행렬")
    close(s.matching_cost(probs, boxes, gt_labels, gt_boxes, w_class=2.0, w_l1=0.0), -2 * probs[:, gt_labels], 1e-9, "가중치를 바꾼 비용 행렬")


def greedy_trap():
    cost = np.array([[1.0, 2.0], [1.0, 100.0]])
    pairs = valid(cost, s.match(cost))
    close(total(cost, pairs), 3.0, 1e-9, "비용의 합 (행마다 가장 싼 열을 고르면 101이 돼요)")


def small_random():
    for Q, G in ((1, 1), (3, 3), (5, 3), (6, 6), (7, 4)):
        for _ in range(8):
            cost = rng.normal(size=(Q, G))
            pairs = valid(cost, s.match(cost))
            close(total(cost, pairs), brute(cost), 1e-9, f"{Q}x{G} 비용의 합(완전 탐색의 최솟값과 같아야 함)")
    tie = np.zeros((4, 4))
    valid(tie, s.match(tie))


def large():
    # 최적값을 아는 문제를 만든다: cost = u[q] + v[g] + slack, slack >= 0 이고 숨긴 짝에서만 0
    Q, G = 80, 60
    u, v = rng.uniform(0, 5, size=Q), rng.uniform(0, 5, size=G)
    hidden = rng.permutation(Q)[:G]
    slack = rng.uniform(0.5, 3.0, size=(Q, G))
    slack[hidden, np.arange(G)] = 0.0
    u[np.setdiff1d(np.arange(Q), hidden)] += 10.0   # 짝이 없는 예측은 쓰면 손해
    cost = u[:, None] + v[None, :] + slack
    print("        (80x60 문제를 푸는 중. 완전 탐색이면 끝나지 않으니 Ctrl+C 로 멈추고 알고리즘을 바꾸세요)", flush=True)
    start = time.perf_counter()
    pairs = valid(cost, s.match(cost))
    took = time.perf_counter() - start
    close(total(cost, pairs), u[hidden].sum() + v.sum(), 1e-6, "80x60 비용의 합(최적값)")
    assert took < 20, f"80x60 에 {took:.1f}초 걸렸어요 (제한 20초). 다항 시간 알고리즘이 필요해요"


c.check("비용 행렬", cost_values)
c.check("탐욕법이 틀리는 경우", greedy_trap)
c.check("작은 무작위 문제 (완전 탐색과 비교)", small_random)
c.check("80x60: 최적이고 제한 시간 안", large)
c.finish()
