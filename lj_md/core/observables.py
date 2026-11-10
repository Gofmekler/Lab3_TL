"""Макроскопические наблюдаемые: давление, функция радиального распределения."""

from __future__ import annotations

import math

import numpy as np

from .system import ParticleSystem


def pressure(system: ParticleSystem, virial: float) -> float:
    """Давление по теореме вириала: P = (N·T + W/d) / V, W = Σ r_ij·F_ij."""
    return (system.n * system.temperature() + virial / system.dim) / system.volume


def radial_distribution(system: ParticleSystem, bins: int = 60,
                        r_max: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Функция радиального распределения g(r).

    Возвращает (центры бинов, g). Нормировка на идеальный газ той же
    плотности; корректна для периодических границ при r_max ≤ L/2.
    """
    if r_max is None:
        r_max = system.box / 2.0
    if system.n < 2:
        centers = np.linspace(0, r_max, bins, endpoint=False) + r_max / bins / 2
        return centers, np.zeros(bins)

    distances = system.pair_distances()
    hist, edges = np.histogram(distances, bins=bins, range=(0.0, r_max))
    centers = 0.5 * (edges[1:] + edges[:-1])

    if system.dim == 2:
        shell = math.pi * (edges[1:] ** 2 - edges[:-1] ** 2)
    else:
        shell = 4.0 / 3.0 * math.pi * (edges[1:] ** 3 - edges[:-1] ** 3)

    # Ожидаемое число пар в слое для идеального газа: N/2 · ρ · V_слоя
    rho = system.n / system.volume
    # При отражающих стенках часть слоя «выходит» за ячейку, поэтому g(r)
    # на больших r занижена — для качественной картины этого достаточно.
    ideal = 0.5 * system.n * rho * shell
    g = np.divide(hist, ideal, out=np.zeros_like(ideal), where=ideal > 0)
    return centers, g


class RdfAverager:
    """Усреднение g(r) по времени: мгновенная g(r) слишком шумная."""

    def __init__(self, bins: int = 60) -> None:
        self.bins = bins
        self.reset()

    def reset(self) -> None:
        self.r: np.ndarray | None = None
        self._sum: np.ndarray | None = None
        self.samples = 0

    def sample(self, system: ParticleSystem) -> None:
        r, g = radial_distribution(system, bins=self.bins)
        if self._sum is None:
            self.r, self._sum = r, np.zeros_like(g)
        self._sum += g
        self.samples += 1

    @property
    def g(self) -> np.ndarray:
        if self._sum is None or self.samples == 0:
            return np.zeros(self.bins)
        return self._sum / self.samples
