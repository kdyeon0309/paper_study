# 08. DETR의 이분 매칭 (Hungarian matching)

DETR(arXiv:2005.12872)이 NMS와 anchor를 없앨 수 있었던 이유. 예측과 정답을 일대일로 짝지어 loss를 건다.

## 구현할 것 (`solution.py`)

```python
matching_cost(pred_probs, pred_boxes, gt_labels, gt_boxes, w_class=1.0, w_l1=5.0)
    # pred_probs: [Q, C] (softmax 뒤), pred_boxes: [Q, 4], gt_labels: [G] 정수, gt_boxes: [G, 4]
    # ->  cost: [Q, G],   cost[q, g] = -w_class * pred_probs[q, gt_labels[g]] + w_l1 * (상자의 L1 거리)
match(cost)
    # cost: [Q, G], Q >= G   ->   [(q, g), ...]  모든 정답 g 가 서로 다른 예측 q 와 한 번씩 짝지어지고, 비용의 합이 최소
```

- `scipy.optimize.linear_sum_assignment` 를 쓰지 말고 직접 짠다.
- 작은 입력은 완전 탐색으로도 통과하지만, 마지막 항목(80 x 60)은 다항 시간 알고리즘이어야 제한 시간 안에 끝난다. 헝가리안 알고리즘(Kuhn-Munkres, $O(n^3)$)을 권한다.

## 손으로 먼저

1. `cost = [[1, 2], [1, 100]]` 에서 "행마다 가장 싼 열을 고르는" 탐욕법의 결과와 최적해를 비교한다. 탐욕법이 왜 틀리는가?
2. 분류 비용에 `-log p` 가 아니라 `-p` 를 쓰는 이유를 논문에서 찾아본다.
3. 매칭되지 않은 예측(Q - G개)은 loss에서 어떻게 다뤄지는가? ("no object" 클래스)
4. YOLO의 정답 할당(grid cell + anchor IoU)과 비교해, 일대일 매칭이 NMS를 필요 없게 만드는 이유를 한 문단으로 쓴다.

```bash
python exercises/08_hungarian/check.py
```
