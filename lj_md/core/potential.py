"""Потенциал Леннард-Джонса.

    U(r) = 4ε [ (σ/r)^12 − (σ/r)^6 ]

Используются приведённые (безразмерные) единицы: σ = ε = m = k_B = 1.
Потенциал обрезается на радиусе r_c и сдвигается так, чтобы U(r_c) = 0
(truncated & shifted) — тогда энергия непрерывна и полная энергия
сохраняется лучше.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LennardJones:
    epsilon: float = 1.0
    sigma: float = 1.0
    cutoff: float = 2.5

    def __post_init__(self) -> None:
        if self.epsilon <= 0 or self.sigma <= 0:
            raise ValueError("epsilon и sigma должны быть положительными")
        if self.cutoff <= 0:
            raise ValueError("Радиус обрезки должен быть положительным")

    @property
    def shift(self) -> float:
        """U(r_c) без сдвига — вычитается из энергии каждой пары."""
        sr6 = (self.sigma / self.cutoff) ** 6
        return 4.0 * self.epsilon * (sr6 * sr6 - sr6)

    @property
    def r_min(self) -> float:
        """Положение минимума потенциала: 2^(1/6) σ."""
        return 2.0 ** (1.0 / 6.0) * self.sigma

    def energy(self, r: np.ndarray | float) -> np.ndarray:
        """Энергия пары на расстоянии r (с обрезкой и сдвигом)."""
        r = np.asarray(r, dtype=float)
        sr6 = (self.sigma / r) ** 6
        u = 4.0 * self.epsilon * (sr6 * sr6 - sr6) - self.shift
        return np.where(r < self.cutoff, u, 0.0)

    def force_over_r(self, r2: np.ndarray) -> np.ndarray:
        """|F|/r как функция r² — удобно для векторной силы F = (|F|/r)·r_vec.

        F(r) = −dU/dr = 24ε/r [ 2(σ/r)^12 − (σ/r)^6 ]
        """
        r2 = np.asarray(r2, dtype=float)
        sr2 = self.sigma**2 / r2
        sr6 = sr2 * sr2 * sr2
        f = 24.0 * self.epsilon * (2.0 * sr6 * sr6 - sr6) / r2
        return np.where(r2 < self.cutoff**2, f, 0.0)
