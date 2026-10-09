# 03. Conv2d 순전파와 역전파

프레임워크가 해주던 것을 한 번은 손으로. backbone 논문의 연산량·수용 영역 이야기가 여기서 구체적이 된다.

## 구현할 것 (`solution.py`)

```python
conv2d_forward(x, w, b, stride=1, pad=0)             # x: [N, C, H, W], w: [F, C, kh, kw], b: [F]  ->  [N, F, H', W']
conv2d_backward(dout, x, w, b, stride=1, pad=0)      # dout: [N, F, H', W']  ->  (dx, dw, db)
```

- 출력 크기: $H' = \lfloor (H + 2\,\text{pad} - k_h) / \text{stride} \rfloor + 1$
- 패딩은 0으로 채운다. 딥러닝 프레임워크처럼 교차상관(커널을 뒤집지 않음)이다.
- 먼저 for 문으로 맞게 짠다. 벡터화는 통과한 다음에.

## 손으로 먼저

1. 1차원에서 `x = [x0, x1, x2, x3]`, `w = [w0, w1]`, stride 1 일 때 출력 세 개를 쓰고, $\partial L/\partial x_1$ 을 `dout` 으로 표현한다. 한 입력이 여러 출력에 쓰인다는 점이 역전파의 전부다.
2. `dw` 의 모양이 왜 `w` 와 같은지, `db` 가 왜 `dout` 을 `(N, H', W')` 축으로 더한 것인지 설명한다.
3. 3x3 conv를 두 번 쌓은 수용 영역과 5x5 한 번의 수용 영역·파라미터 수를 비교한다 (VGG의 논거).

```bash
python exercises/03_conv2d/check.py
```
