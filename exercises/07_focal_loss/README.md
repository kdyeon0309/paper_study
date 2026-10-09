# 07. Focal Loss

one-stage detector의 클래스 불균형을 loss 하나로 푼 논문(RetinaNet, arXiv:1708.02002). YOLO 계열의 objectness·분류 loss와 직접 비교되는 지점이다.

## 구현할 것 (`solution.py`)

```python
focal_loss(logits, targets, alpha=0.25, gamma=2.0)    # logits: [N], targets: [N] (0 또는 1)  ->  (loss, dlogits)
```

- $p = \sigma(x)$, $p_t = p$ (정답이 1) 또는 $1 - p$ (정답이 0), $\alpha_t$ 도 같은 방식
- $\text{FL} = -\alpha_t\,(1 - p_t)^\gamma \log p_t$, `loss` 는 배치 평균
- `dlogits` 는 $\partial\,\text{loss}/\partial\,\text{logits}$
- $|x|$ 가 수백이어도 nan/inf가 없어야 한다. `log(sigmoid(x))` 를 그대로 쓰면 터진다.

## 손으로 먼저

1. $\gamma = 0$ 이면 무엇이 되는가?
2. $p_t = 0.9$ (쉬운 예제)와 $p_t = 0.1$ (어려운 예제)의 loss가 cross-entropy 대비 각각 몇 배로 줄어드는지 $\gamma = 2$ 에서 계산한다.
3. $\partial\,\text{FL}/\partial x$ 를 유도한다. $\partial p_t/\partial x = \pm\, p_t(1 - p_t)$ 에서 시작한다.
4. 배경 상자가 전경의 1000배인 상황에서 $\alpha$ 와 $\gamma$ 가 각각 무슨 역할을 하는지 구분해 설명한다.

```bash
python exercises/07_focal_loss/check.py
```
