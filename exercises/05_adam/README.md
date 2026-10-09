# 05. Adam과 AdamW

매일 쓰는 옵티마이저 두 줄의 차이. `weight_decay` 를 Adam에 주는 것과 AdamW에 주는 것은 다른 알고리즘이다.

## 구현할 것 (`solution.py`)

```python
adam_step(param, grad, m, v, t, lr=1e-3, beta1=0.9, beta2=0.999, eps=1e-8)                        # -> (param, m, v)
adamw_step(param, grad, m, v, t, lr=1e-3, beta1=0.9, beta2=0.999, eps=1e-8, weight_decay=1e-2)    # -> (param, m, v)
```

- `t` 는 1부터 시작하는 스텝 번호다.
- Adam: $m \leftarrow \beta_1 m + (1-\beta_1) g$, $v \leftarrow \beta_2 v + (1-\beta_2) g^2$,
  $\hat m = m/(1-\beta_1^t)$, $\hat v = v/(1-\beta_2^t)$, $\theta \leftarrow \theta - \text{lr}\cdot \hat m / (\sqrt{\hat v} + \epsilon)$
- AdamW: 감쇠를 기울기에 섞지 않고 파라미터에 직접 건다. 먼저 $\theta \leftarrow \theta\,(1 - \text{lr}\cdot\lambda)$, 그다음 위의 Adam 갱신(기울기는 감쇠 전 그대로).
- 입력 배열을 제자리에서 바꾸지 말고 새 값을 돌려준다.

## 손으로 먼저

1. $m_0 = v_0 = 0$ 에서 첫 스텝의 $\hat m$, $\hat v$ 를 계산해, 첫 갱신의 크기가 기울기 크기와 무관하게 거의 `lr` 임을 보인다. bias correction이 없으면 첫 갱신은 `lr` 의 몇 배가 되는가?
2. L2 정규화($g \leftarrow g + \lambda\theta$)를 Adam에 넣으면, 기울기가 큰 파라미터는 감쇠가 **약해진다**. 왜인지 $\sqrt{\hat v}$ 로 나누는 부분을 보고 설명한다. 이것이 AdamW 논문의 출발점이다.

```bash
python exercises/05_adam/check.py
```
