# 01. Softmax와 Cross-Entropy

분류 모델의 마지막 단. 거의 모든 논문의 loss가 여기서 출발한다.

## 구현할 것 (`solution.py`)

```python
softmax(logits)            # logits: [N, C]  ->  probs: [N, C]
cross_entropy(logits, y)   # y: [N] 정수 라벨  ->  (loss, dlogits)
```

- `loss` 는 배치 평균 스칼라: $L = -\frac{1}{N}\sum_i \log p_{i, y_i}$
- `dlogits` 는 $\partial L / \partial \text{logits}$, 모양 `[N, C]`

## 손으로 먼저

1. $p = \text{softmax}(z)$ 일 때 $\partial L/\partial z_k = p_k - \mathbb{1}[k = y]$ 임을 유도한다 (배치 평균이면 $1/N$ 이 붙는다).
2. logits에 상수를 더해도 softmax가 변하지 않음을 보인다. 이것이 수치 안정화(최댓값 빼기)의 근거다.

## 채점이 보는 것

- 확률의 합이 1, 상수 이동에 불변
- logits가 1000처럼 커도 nan/inf가 없다 (`exp` 를 그대로 쓰면 터진다)
- 균등 logits에서 loss가 $\log C$
- `dlogits` 가 수치 기울기와 일치

```bash
python exercises/01_softmax_ce/check.py
```
