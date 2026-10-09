import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from _check import Checker, close, load, numeric_grad

s = load(Path(__file__).parent)
rng = np.random.default_rng(0)

c = Checker("05. Adam과 AdamW")


def first_step_size():
    for scale in (1e-3, 1.0, 1e3):
        g = rng.normal(size=6) * scale
        p, m, v = s.adam_step(np.zeros(6), g, np.zeros(6), np.zeros(6), 1, lr=0.01)
        close(p, -0.01 * g / (np.abs(g) + 1e-8), 1e-9, f"첫 스텝의 변화량 (기울기 크기 {scale:g}). 크기가 거의 lr 이어야 해요. bias correction을 확인하세요")
        close(m, 0.1 * g, 1e-9 * max(1, scale), "첫 스텝의 m")
        close(v, 0.001 * g * g, 1e-9 * max(1, scale * scale), "첫 스텝의 v")


def several_steps():
    p, m, v = 1.0, 0.0, 0.0   # 스칼라로 식을 그대로 따라간 값과 비교
    P, M, V = np.array([1.0]), np.zeros(1), np.zeros(1)
    for t, g in enumerate([0.5, -0.2, 0.8, 0.1], start=1):
        m = 0.9 * m + 0.1 * g
        v = 0.999 * v + 0.001 * g * g
        p = p - 0.1 * (m / (1 - 0.9 ** t)) / ((v / (1 - 0.999 ** t)) ** 0.5 + 1e-8)
        P, M, V = s.adam_step(P, np.array([g]), M, V, t, lr=0.1)
        close(P, [p], 1e-9, f"{t}번째 스텝의 파라미터")
    close(M, [m], 1e-12, "4스텝 뒤의 m")
    close(V, [v], 1e-12, "4스텝 뒤의 v")


def no_mutation():
    p0, g0, m0, v0 = (rng.normal(size=4) for _ in range(4))
    v0 = np.abs(v0)
    copies = [a.copy() for a in (p0, g0, m0, v0)]
    s.adam_step(p0, g0, m0, v0, 3)
    s.adamw_step(p0, g0, m0, v0, 3)
    for name, a, b in zip(("param", "grad", "m", "v"), (p0, g0, m0, v0), copies):
        close(a, b, 0, f"입력 {name} (제자리에서 바꾸면 안 돼요)")


def decay_is_decoupled():
    p0 = np.array([2.0, -4.0])
    p, m, v = s.adamw_step(p0, np.zeros(2), np.zeros(2), np.zeros(2), 1, lr=0.1, weight_decay=0.5)
    close(p, p0 * (1 - 0.1 * 0.5), 1e-9, "기울기가 0일 때의 AdamW (감쇠만 걸려야 함)")
    close(m, np.zeros(2), 0, "기울기가 0일 때의 m (감쇠가 m에 섞이면 안 돼요)")

    g = np.array([10.0, 0.01])   # 기울기 크기가 달라도 감쇠 비율은 같아야 한다
    p, _, _ = s.adamw_step(p0, g, np.zeros(2), np.zeros(2), 1, lr=0.1, weight_decay=0.5)
    plain, _, _ = s.adam_step(p0, g, np.zeros(2), np.zeros(2), 1, lr=0.1)
    close(p - plain, -0.1 * 0.5 * p0, 1e-9, "AdamW와 Adam의 차이(= -lr * weight_decay * param)")
    l2, _, _ = s.adam_step(p0, g + 0.5 * p0, np.zeros(2), np.zeros(2), 1, lr=0.1)
    assert np.max(np.abs(p - l2)) > 1e-3, "AdamW가 'L2를 기울기에 더한 Adam'과 같은 값을 내요. 감쇠를 기울기에 섞지 마세요"


c.check("첫 스텝의 크기는 lr (bias correction)", first_step_size)
c.check("여러 스텝을 식 그대로 따라간 값과 일치", several_steps)
c.check("입력 배열을 바꾸지 않음", no_mutation)
c.check("AdamW의 감쇠는 기울기와 분리", decay_is_decoupled)
c.finish()
