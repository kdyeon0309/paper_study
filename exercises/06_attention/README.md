# 06. Scaled Dot-Product Attention

ViT, DETR, CLIP, LLaVA가 모두 이 한 연산 위에 있다. 로드맵의 'Transformer와 ViT' 트랙을 읽기 전에.

## 구현할 것 (`solution.py`)

```python
scaled_dot_product_attention(q, k, v, mask=None)
    # q: [B, T, d], k: [B, S, d], v: [B, S, dv], mask: [B, T, S] 또는 브로드캐스트 가능한 bool (True = 볼 수 있음)
    # ->  (out: [B, T, dv], weights: [B, T, S])
causal_mask(T)
    # ->  [T, T] bool. i번째 위치가 j번째를 볼 수 있으면 True (j <= i)
```

- $\text{weights} = \text{softmax}\!\left(\frac{QK^\top}{\sqrt{d}} + \text{마스크}\right)$, $\text{out} = \text{weights}\cdot V$
- 마스크가 False인 자리의 가중치는 정확히 0이어야 한다.
- 점수가 매우 커도 nan이 나오면 안 된다.

## 손으로 먼저

1. $\sqrt{d}$ 로 나누는 이유: $q, k$ 의 성분이 평균 0, 분산 1로 독립이면 $q\cdot k$ 의 분산은 얼마인가? 나누지 않으면 softmax가 어떻게 되고 기울기는 어떻게 되는가?
2. self-attention의 연산량이 토큰 수 $T$ 에 대해 $O(T^2)$ 인 이유를 `weights` 의 모양으로 설명한다. Sparse DETR·Deformable DETR이 줄이려던 것이 바로 이 항이다.
3. attention은 순서를 모른다(입력을 섞으면 출력도 똑같이 섞인다). 그래서 무엇이 추가로 필요한가?

```bash
python exercises/06_attention/check.py
```
