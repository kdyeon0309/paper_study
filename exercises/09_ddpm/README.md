# 09. DDPM 한 스텝

생성 모델 트랙의 중심(arXiv:2006.11239). detection과 가장 먼 분야지만, 필요한 식은 가우시안 세 줄이다.

## 구현할 것 (`solution.py`)

```python
q_sample(x0, t, alphas_cumprod, noise)       # 노이즈 넣기:  x_t = sqrt(ab_t) x0 + sqrt(1 - ab_t) noise
predict_x0(xt, t, eps, alphas_cumprod)       # 예측한 노이즈 eps 로 x0 복원
p_mean(xt, t, eps, betas)                    # 역방향 한 스텝의 평균:  (x_t - beta_t / sqrt(1 - ab_t) * eps) / sqrt(alpha_t)
```

- `x0`, `xt`, `noise`, `eps`: `[B, ...]` (예: `[B, C, H, W]`). `t`: `[B]` 정수, 샘플마다 다를 수 있다.
- `betas`: `[T]`. $\alpha_t = 1 - \beta_t$, $\bar\alpha_t = \prod_{s \le t} \alpha_s$ (`alphas_cumprod`, 줄여서 ab).
- `t` 로 꺼낸 계수를 `[B, 1, 1, 1]` 처럼 펴서 곱해야 한다. 여기가 가장 흔한 버그다.

## 손으로 먼저

1. $q(x_t \mid x_{t-1}) = \mathcal N(\sqrt{\alpha_t}\,x_{t-1}, \beta_t I)$ 를 두 번 적용해 $q(x_t \mid x_0)$ 의 닫힌 꼴을 유도한다 (가우시안의 합).
2. `q_sample` 식을 $x_0$ 에 대해 풀어 `predict_x0` 를 얻는다.
3. 사후분포 $q(x_{t-1} \mid x_t, x_0)$ 의 평균
   $\tilde\mu = \frac{\sqrt{\bar\alpha_{t-1}}\,\beta_t}{1-\bar\alpha_t}x_0 + \frac{\sqrt{\alpha_t}\,(1-\bar\alpha_{t-1})}{1-\bar\alpha_t}x_t$
   에 2번의 $x_0$ 를 대입해 `p_mean` 의 식이 나오는지 확인한다. 채점은 이 두 식이 같은지를 본다.
4. 학습 loss가 왜 "노이즈를 맞히는 MSE" 하나로 줄어드는지 논문 3.2~3.4절에서 따라간다.

```bash
python exercises/09_ddpm/check.py
```
