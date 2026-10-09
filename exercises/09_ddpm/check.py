import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from _check import Checker, close, load, numeric_grad

s = load(Path(__file__).parent)
rng = np.random.default_rng(0)

c = Checker("09. DDPM 한 스텝")
T = 200
betas = np.linspace(1e-4, 0.02, T)
alphas = 1.0 - betas
ab = np.cumprod(alphas)
x0 = rng.normal(size=(6, 3, 4, 4))
noise = rng.normal(size=x0.shape)
t = np.array([0, 1, 17, 99, 150, 199])


def per_sample_coefficients():
    xt = s.q_sample(x0, t, ab, noise)
    assert np.shape(xt) == x0.shape, f"모양이 {np.shape(xt)} 인데 {x0.shape} 이어야 해요"
    for i, ti in enumerate(t):
        close(xt[i], np.sqrt(ab[ti]) * x0[i] + np.sqrt(1 - ab[ti]) * noise[i], 1e-12, f"{i}번째 샘플(t={ti})의 x_t. 샘플마다 자기 t 의 계수를 써야 해요")
    flat = s.q_sample(x0.reshape(6, -1), t, ab, noise.reshape(6, -1))
    close(flat, xt.reshape(6, -1), 1e-12, "[B, D] 모양 입력의 x_t (차원 수가 달라도 동작해야 해요)")


def noise_schedule_ends():
    close(s.q_sample(x0, np.zeros(6, dtype=int), ab, noise), x0, 0.1, "t=0 의 x_t (거의 x0 여야 함)")
    big = rng.normal(size=(4000, 8)) * 0 + 3.0   # 평균 3인 데이터
    xt = s.q_sample(big, np.full(4000, T - 1), ab, rng.normal(size=big.shape))
    assert abs(xt.var() - (1 - ab[-1])) < 0.05, f"t=T-1 에서 x_t 의 분산이 {xt.var():.3f} 인데 {1 - ab[-1]:.3f} 근처여야 해요"
    assert abs(xt.mean() - 3.0 * np.sqrt(ab[-1])) < 0.05, "t=T-1 에서 x_t 의 평균이 sqrt(ab) * x0 와 달라요"


def round_trip():
    xt = s.q_sample(x0, t, ab, noise)
    close(s.predict_x0(xt, t, noise, ab), x0, 1e-9, "진짜 노이즈를 넣어 복원한 x0")


def reverse_mean():
    xt = s.q_sample(x0, t, ab, noise)
    eps = noise + 0.3 * rng.normal(size=x0.shape)   # 완벽하지 않은 노이즈 예측
    got = s.p_mean(xt, t, eps, betas)
    x0_hat = s.predict_x0(xt, t, eps, ab)
    for i, ti in enumerate(t):
        ab_prev = ab[ti - 1] if ti > 0 else 1.0
        want = (np.sqrt(ab_prev) * betas[ti] / (1 - ab[ti])) * x0_hat[i] + (np.sqrt(alphas[ti]) * (1 - ab_prev) / (1 - ab[ti])) * xt[i]
        close(got[i], want, 1e-9, f"{i}번째 샘플(t={ti})의 평균. 사후분포 q(x_(t-1) | x_t, x0) 의 평균과 같아야 해요")


c.check("샘플마다 다른 t 의 계수", per_sample_coefficients)
c.check("노이즈 스케줄의 양 끝", noise_schedule_ends)
c.check("x0 → x_t → x0 왕복", round_trip)
c.check("역방향 평균 = 사후분포의 평균", reverse_mean)
c.finish()
