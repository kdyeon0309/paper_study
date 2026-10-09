import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from _check import Checker, close, load, numeric_grad

s = load(Path(__file__).parent)
rng = np.random.default_rng(0)

c = Checker("04. Batch Normalization")
N, D = 8, 5
x = rng.normal(loc=3.0, scale=2.0, size=(N, D))
gamma, beta = rng.uniform(0.5, 2.0, size=D), rng.normal(size=D)
rm, rv = rng.normal(size=D), rng.uniform(0.5, 2.0, size=D)


def train_statistics():
    out, _, _, _ = s.bn_forward(x, gamma, beta, rm, rv, True)
    close(out.mean(axis=0), beta, 1e-7, "학습 모드 출력의 평균(beta 와 같아야 함)")
    close(out.std(axis=0), gamma, 1e-4, "학습 모드 출력의 표준편차(gamma 와 같아야 함)")


def running_update():
    rm0, rv0 = rm.copy(), rv.copy()
    _, _, new_rm, new_rv = s.bn_forward(x, gamma, beta, rm, rv, True, momentum=0.8)
    close(new_rm, 0.8 * rm0 + 0.2 * x.mean(axis=0), 1e-9, "갱신된 running_mean")
    close(new_rv, 0.8 * rv0 + 0.2 * x.var(axis=0), 1e-9, "갱신된 running_var (배치 분산은 N으로 나눈 값)")
    close(rm, rm0, 0, "입력으로 준 running_mean (제자리에서 바꾸면 안 돼요)")
    close(rv, rv0, 0, "입력으로 준 running_var (제자리에서 바꾸면 안 돼요)")


def eval_mode():
    out, _, new_rm, new_rv = s.bn_forward(x, gamma, beta, rm, rv, False, eps=1e-5)
    close(out, gamma * (x - rm) / np.sqrt(rv + 1e-5) + beta, 1e-9, "추론 모드 출력(이동 통계로 정규화)")
    close(new_rm, rm, 0, "추론 모드의 running_mean (바뀌면 안 돼요)")
    close(new_rv, rv, 0, "추론 모드의 running_var (바뀌면 안 돼요)")
    single, _, _, _ = s.bn_forward(x[:1], gamma, beta, rm, rv, False)
    close(single, out[:1], 1e-9, "배치 크기 1의 추론 출력 (배치 구성에 좌우되면 안 돼요)")


def gradients():
    dout = rng.normal(size=(N, D))
    g, b_ = gamma.copy(), beta.copy()
    loss = lambda *_: float((s.bn_forward(x, g, b_, rm, rv, True)[0] * dout).sum())
    _, cache, _, _ = s.bn_forward(x, g, b_, rm, rv, True)
    dx, dgamma, dbeta = s.bn_backward(dout, cache)
    close(dx, numeric_grad(loss, x), 1e-6, "dx")
    close(dgamma, numeric_grad(loss, g), 1e-6, "dgamma")
    close(dbeta, numeric_grad(loss, b_), 1e-6, "dbeta")
    close(dx.sum(axis=0), np.zeros(D), 1e-8, "dx의 배치 방향 합(0이어야 함)")


c.check("학습 모드: 출력 평균 = beta, 표준편차 = gamma", train_statistics)
c.check("이동 통계 갱신", running_update)
c.check("추론 모드는 이동 통계만 사용", eval_mode)
c.check("역전파가 수치 기울기와 일치", gradients)
c.finish()
