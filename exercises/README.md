# 구현 과제

읽기만으로는 채워지지 않는 기초를 손으로 채우는 과제들. numpy만 쓴다.

## 하는 법

```bash
cp exercises/02_iou_nms/solution_template.py exercises/02_iou_nms/solution.py   # 1. 틀 복사
# 2. README.md 의 '손으로 먼저'를 종이에 풀고, solution.py 의 함수를 채운다
python exercises/02_iou_nms/check.py                                            # 3. 채점
```

채점기는 정답 코드를 보여주지 않는다. 손으로 계산한 값, 느리지만 명백히 맞는 for 문 구현, 수치 기울기, 완전 탐색과 비교해 통과·실패를 알려준다. 모두 통과하면 웹의 '로드맵 → 구현 과제'에서 완료로 표시한다.

막혔을 때는 Claude Code에 답을 달라고 하지 말고 "힌트만" 또는 "내 코드에서 틀린 줄만"이라고 요청한다. 답을 받아 적으면 채점은 통과해도 남는 것이 없다.

numpy가 필요하다: `pip install numpy`

## 목록

| 과제 | 분량 | 관련 |
|---|---|---|
| [01. Softmax와 Cross-Entropy](01_softmax_ce/README.md) | 약 40분 | 기초 |
| [02. IoU와 NMS](02_iou_nms/README.md) | 약 50분 | 기초 |
| [03. Conv2d 순전파와 역전파](03_conv2d/README.md) | 약 90분 | 기초 |
| [04. Batch Normalization](04_batchnorm/README.md) | 약 70분 | 기초 |
| [05. Adam과 AdamW](05_adam/README.md) | 약 45분 | 기초 |
| [06. Scaled Dot-Product Attention](06_attention/README.md) | 약 60분 | 논문 |
| [07. Focal Loss](07_focal_loss/README.md) | 약 50분 | 논문 |
| [08. DETR의 이분 매칭](08_hungarian/README.md) | 약 120분 | 논문 |
| [09. DDPM 한 스텝](09_ddpm/README.md) | 약 70분 | 새 영역 |
