"""Система частиц в ячейке и вычисление сил.

Поддерживаются два типа границ:

* ``periodic``   — периодические граничные условия + соглашение
                   о ближайшем образе (minimum image);
* ``reflective`` — жёсткие стенки, упругое отражение.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from .potential import LennardJones


class Boundary(str, Enum):
    PERIODIC = "periodic"
    REFLECTIVE = "reflective"


@dataclass
class ForceResult:
    forces: np.ndarray        # (N, d)
    potential_energy: float   # Σ U(r_ij)
    virial: float             # Σ r_ij · F_ij  (для давления)


@dataclass
class ParticleSystem:
    positions: np.ndarray     # (N, d)
    velocities: np.ndarray    # (N, d)
    box: float                # длина ребра квадратной/кубической ячейки
    potential: LennardJones = field(default_factory=LennardJones)
    boundary: Boundary = Boundary.PERIODIC
    mass: float = 1.0

    def __post_init__(self) -> None:
        self.positions = np.asarray(self.positions, dtype=float)
        self.velocities = np.asarray(self.velocities, dtype=float)
        if self.positions.shape != self.velocities.shape:
            raise ValueError("positions и velocities должны иметь одинаковую форму")
        if self.positions.ndim != 2 or self.positions.shape[1] not in (2, 3):
            raise ValueError("Ожидается массив формы (N, 2) или (N, 3)")
        self.boundary = Boundary(self.boundary)

    # --- базовые величины ---------------------------------------------------

    @property
    def n(self) -> int:
        return self.positions.shape[0]

    @property
    def dim(self) -> int:
        return self.positions.shape[1]

    @property
    def volume(self) -> float:
        return self.box**self.dim

    @property
    def density(self) -> float:
        return self.n / self.volume

    # --- геометрия ----------------------------------------------------------

    def pair_vectors(self) -> np.ndarray:
        """Векторы r_ij = r_i − r_j, форма (N, N, d), с учётом PBC."""
        delta = self.positions[:, None, :] - self.positions[None, :, :]
        if self.boundary is Boundary.PERIODIC:
            delta -= self.box * np.round(delta / self.box)
        return delta

    def pair_distances(self) -> np.ndarray:
        """Расстояния для всех уникальных пар (i < j), одномерный массив."""
        r = np.sqrt(np.sum(self.pair_vectors() ** 2, axis=-1))
        i, j = np.triu_indices(self.n, k=1)
        return r[i, j]

    def apply_boundary(self) -> None:
        """Вернуть частицы в ячейку после шага интегратора."""
        if self.boundary is Boundary.PERIODIC:
            self.positions %= self.box
            return
        # Отражающие стенки: зеркально отражаем координату и меняем знак скорости.
        low = self.positions < 0.0
        self.positions[low] = -self.positions[low]
        self.velocities[low] = -self.velocities[low]
        high = self.positions > self.box
        self.positions[high] = 2.0 * self.box - self.positions[high]
        self.velocities[high] = -self.velocities[high]
        np.clip(self.positions, 0.0, self.box, out=self.positions)

    # --- силы ---------------------------------------------------------------

    def compute_forces(self) -> ForceResult:
        """Парные силы LJ, потенциальная энергия и вириал. Сложность O(N²)."""
        delta = self.pair_vectors()
        r2 = np.sum(delta**2, axis=-1)
        np.fill_diagonal(r2, np.inf)  # исключаем взаимодействие i с самим собой

        f_over_r = self.potential.force_over_r(r2)          # (N, N)
        forces = np.sum(f_over_r[:, :, None] * delta, axis=1)

        i, j = np.triu_indices(self.n, k=1)
        r2_pairs = r2[i, j]
        potential_energy = float(np.sum(self.potential.energy(np.sqrt(r2_pairs))))
        virial = float(np.sum(f_over_r[i, j] * r2_pairs))
        return ForceResult(forces, potential_energy, virial)

    # --- кинематика ---------------------------------------------------------

    def kinetic_energy(self) -> float:
        return float(0.5 * self.mass * np.sum(self.velocities**2))

    def momentum(self) -> np.ndarray:
        return self.mass * np.sum(self.velocities, axis=0)

    @property
    def degrees_of_freedom(self) -> int:
        # При PBC импульс центра масс сохраняется и обнулён → минус d степеней.
        if self.boundary is Boundary.PERIODIC:
            return max(self.dim * (self.n - 1), 1)
        return self.dim * self.n

    def temperature(self) -> float:
        """T = 2·KE / N_f  (k_B = 1)."""
        return 2.0 * self.kinetic_energy() / self.degrees_of_freedom
