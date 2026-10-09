import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from _check import Checker, close, load, numeric_grad

s = load(Path(__file__).parent)
rng = np.random.default_rng(0)

c = Checker("02. IoU와 NMS")


def ref_iou(p, q):
    w = max(0.0, min(p[2], q[2]) - max(p[0], q[0]))
    h = max(0.0, min(p[3], q[3]) - max(p[1], q[1]))
    inter = w * h
    union = (p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - inter
    return inter / union if union > 0 else 0.0


def ref_nms(boxes, scores, thr):
    order = sorted(range(len(boxes)), key=lambda i: -scores[i])
    keep = []
    for i in order:
        if all(ref_iou(boxes[i], boxes[j]) <= thr for j in keep):
            keep.append(i)
    return keep


def random_boxes(n):
    xy = rng.uniform(0, 10, size=(n, 2))
    wh = rng.uniform(0.5, 6, size=(n, 2))
    return np.concatenate([xy, xy + wh], axis=1)


def hand_cases():
    a = np.array([[0, 0, 2, 2]], dtype=float)
    b = np.array([[0, 0, 2, 2], [1, 0, 3, 2], [2, 0, 4, 2], [5, 5, 6, 6], [0.5, 0.5, 1.5, 1.5]], dtype=float)
    close(s.box_iou(a, b), [[1.0, 1 / 3, 0.0, 0.0, 0.25]], 1e-9, "IoU")


def shape_and_reference():
    a, b = random_boxes(6), random_boxes(9)
    got = s.box_iou(a, b)
    assert np.shape(got) == (6, 9), f"모양이 {np.shape(got)} 인데 (6, 9) 이어야 해요"
    close(got, [[ref_iou(p, q) for q in b] for p in a], 1e-9, "IoU 행렬")
    close(s.box_iou(a, a).diagonal(), np.ones(6), 1e-9, "자기 자신과의 IoU")


def degenerate():
    a = np.array([[1, 1, 1, 1], [0, 0, 2, 2]], dtype=float)
    got = s.box_iou(a, a)
    assert np.isfinite(got).all(), "넓이 0인 상자에서 nan/inf 가 나와요 (0으로 나누는 곳을 확인하세요)"
    close(got[0, 1], 0.0, 1e-12, "넓이 0인 상자와의 IoU")


def nms_hand():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [20, 20, 30, 30], [0, 0, 10, 9]], dtype=float)
    scores = np.array([0.9, 0.8, 0.7, 0.95])
    got = [int(i) for i in s.nms(boxes, scores, 0.5)]
    assert got == [3, 2], f"기대 [3, 2], 실제 {got} (점수가 가장 높은 3번이 0번과 1번을 지워야 해요)"
    assert [int(i) for i in s.nms(boxes, scores, 0.95)] == [3, 0, 1, 2], "임계값이 높으면 모두 남고, 순서는 점수 내림차순이어야 해요"


def nms_boundary():
    boxes = np.array([[0, 0, 2, 2], [1, 0, 3, 2]], dtype=float)   # IoU = 정확히 1/3
    scores = np.array([0.9, 0.8])
    assert [int(i) for i in s.nms(boxes, scores, 1 / 3)] == [0, 1], "IoU가 임계값과 같으면 남겨야 해요 (지우는 조건은 '>')"
    assert [int(i) for i in s.nms(boxes, scores, 0.3)] == [0], "IoU가 임계값보다 크면 지워야 해요"


def nms_random():
    for n in (1, 5, 40):
        boxes, scores = random_boxes(n), rng.permutation(n) / n
        for thr in (0.1, 0.4, 0.7):
            got = [int(i) for i in s.nms(boxes, scores, thr)]
            assert got == ref_nms(boxes, scores, thr), f"상자 {n}개, 임계값 {thr} 에서 결과가 달라요: {got}"
    assert len(s.nms(np.zeros((0, 4)), np.zeros(0), 0.5)) == 0, "상자가 없으면 빈 결과를 돌려줘야 해요"


c.check("손으로 계산한 IoU 값", hand_cases)
c.check("N x M 행렬, 무작위 상자", shape_and_reference)
c.check("넓이 0인 상자", degenerate)
c.check("NMS 기본 동작과 순서", nms_hand)
c.check("NMS 임계값 경계 ('>')", nms_boundary)
c.check("NMS 무작위 입력, 빈 입력", nms_random)
c.finish()
