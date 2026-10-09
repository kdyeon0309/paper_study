# 04. Batch Normalization

학습 때와 추론 때 다르게 동작하는 첫 번째 층. "eval 모드를 안 켜서 성능이 떨어졌다"의 정체다.

## 구현할 것 (`solution.py`)

```python
bn_forward(x, gamma, beta, running_mean, running_var, train, momentum=0.9, eps=1e-5)
    # x: [N, D]  ->  (out, cache, running_mean, running_var)
bn_backward(dout, cache)
    # ->  (dx, dgamma, dbeta)
```

- `train=True`: 배치 평균 $\mu$ 와 배치 분산 $\sigma^2$ (N으로 나눈 값)로 정규화하고, 이동 통계를 갱신해 돌려준다.
  `running = momentum * running + (1 - momentum) * 배치 통계`
- `train=False`: 이동 통계로 정규화하고, 이동 통계는 그대로 돌려준다.
- 출력: $y = \gamma \cdot \frac{x - \mu}{\sqrt{\sigma^2 + \epsilon}} + \beta$
- `cache` 에는 역전파에 필요한 것을 마음대로 담는다. 입력으로 받은 배열을 제자리에서 바꾸지 않는다.
- `bn_backward` 는 학습 모드의 역전파다.

## 손으로 먼저

1. 계산 그래프를 그린다: $x \to \mu \to (x - \mu) \to \sigma^2 \to \hat{x} \to y$. $x$ 가 $\mu$ 와 $\sigma^2$ 를 거쳐 **세 갈래**로 영향을 준다는 점이 핵심이다.
2. 그래프를 거꾸로 따라가며 `dx` 를 유도한다. 정리하면
   $\frac{\partial L}{\partial x_i} = \frac{\gamma}{N\sqrt{\sigma^2+\epsilon}}\left(N\,\frac{\partial L}{\partial y_i} - \sum_j \frac{\partial L}{\partial y_j} - \hat{x}_i \sum_j \frac{\partial L}{\partial y_j}\hat{x}_j\right)$
3. 왜 $\sum_i \partial L/\partial x_i = 0$ 인가? (채점 항목에 있다)

```bash
python exercises/04_batchnorm/check.py
```
