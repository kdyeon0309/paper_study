"""구현 과제 채점 도우미. 각 과제의 check.py 가 사용한다. numpy 만 필요하다."""
import importlib.util
import sys
from pathlib import Path

import numpy as np


def load(folder: str):
    """과제 폴더의 solution.py 를 불러온다."""
    path = Path(folder) / "solution.py"
    if not path.exists():
        sys.exit(f"{path} 가 없어요.\nsolution_template.py 를 solution.py 로 복사한 뒤 함수를 채워주세요.")
    spec = importlib.util.spec_from_file_location("solution", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def close(got, want, tol=1e-6, what="값"):
    got, want = np.asarray(got, dtype=float), np.asarray(want, dtype=float)
    assert got.shape == want.shape, f"{what}의 모양이 {got.shape} 인데 {want.shape} 이어야 해요"
    err = float(np.max(np.abs(got - want))) if got.size else 0.0
    assert np.isfinite(got).all(), f"{what}에 nan/inf 가 있어요"
    assert err <= tol, f"{what}이 기대와 달라요 (최대 오차 {err:.3g}, 허용 {tol:g})"


def numeric_grad(f, x, h=1e-5):
    """f(x) -> 스칼라 의 기울기를 중앙 차분으로 구한다. x 는 제자리에서 잠깐 바뀌었다 돌아온다."""
    grad = np.zeros_like(x, dtype=float)
    it = np.nditer(x, flags=["multi_index"])
    while not it.finished:
        i = it.multi_index
        old = x[i]
        x[i] = old + h
        hi = f(x)
        x[i] = old - h
        lo = f(x)
        x[i] = old
        grad[i] = (hi - lo) / (2 * h)
        it.iternext()
    return grad


class Checker:
    def __init__(self, title: str):
        self.title, self.passed, self.failed = title, 0, 0
        print(f"\n{title}\n" + "-" * 48)

    def check(self, name: str, fn):
        try:
            fn()
        except AssertionError as e:
            self.failed += 1
            print(f"  실패  {name}\n        {e}")
        except AttributeError as e:
            self.failed += 1
            print(f"  실패  {name}\n        함수가 없거나 이름이 달라요: {e}")
        except Exception as e:  # 과제 코드의 어떤 오류든 채점은 끝까지 간다
            self.failed += 1
            print(f"  실패  {name}\n        실행 중 오류: {type(e).__name__}: {e}")
        else:
            self.passed += 1
            print(f"  통과  {name}")

    def finish(self):
        total = self.passed + self.failed
        print("-" * 48)
        if self.failed:
            print(f"{total}개 중 {self.passed}개 통과. 실패한 항목을 고친 뒤 다시 돌려보세요.")
            sys.exit(1)
        print(f"{total}개 모두 통과. 웹의 '구현 과제'에서 완료로 표시하세요.")
