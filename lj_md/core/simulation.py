"""Фасад модели: собирает систему, интегратор и термостат в одну симуляцию.

Это единственный класс core, с которым работает ViewModel.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import asdict, dataclass

import numpy as np

from .integrator import VelocityVerlet
from .observables import pressure, radial_distribution
from .potential import LennardJones
from .system import Boundary, ForceResult, ParticleSystem
from .thermostat import Thermostat, ThermostatKind


@dataclass
class SimulationParameters:
    """Все входные параметры эксперимента (в приведённых единицах LJ)."""

    n_particles: int = 64
    dim: int = 2
    density: float = 0.5               # ρ = N / V
    initial_temperature: float = 1.0
    dt: float = 0.005
    cutoff: float = 2.5
    boundary: str = Boundary.PERIODIC.value
    thermostat: str = ThermostatKind.NONE.value
    target_temperature: float = 1.0
    tau: float = 0.5
    seed: int = 42

    @property
    def box(self) -> float:
        return (self.n_particles / self.density) ** (1.0 / self.dim)

    def validate(self) -> dict[str, str]:
        """Физическая согласованность параметров. Возвращает {поле: ошибка}."""
        errors: dict[str, str] = {}
        if self.dim not in (2, 3):
            errors["dim"] = "Размерность должна быть 2 или 3"
        if not 2 <= self.n_particles <= 1000:
            errors["n_particles"] = "Число частиц: от 2 до 1000"
        if not 0 < self.density <= 1.2:
            errors["density"] = "Плотность: 0 < ρ ≤ 1.2"
        if self.initial_temperature <= 0:
            errors["initial_temperature"] = "Температура должна быть > 0"
        if not 0 < self.dt <= 0.02:
            errors["dt"] = "Шаг: 0 < dt ≤ 0.02 (иначе схема неустойчива)"
        if self.cutoff < 1.0:
            errors["cutoff"] = "Радиус обрезки r_c ≥ 1σ"
        if self.boundary not in {b.value for b in Boundary}:
            errors["boundary"] = "Неизвестный тип границ"
        if self.thermostat not in {t.value for t in ThermostatKind}:
            errors["thermostat"] = "Неизвестный термостат"
        if self.target_temperature <= 0:
            errors["target_temperature"] = "Температура должна быть > 0"
        if self.tau <= 0:
            errors["tau"] = "τ должно быть > 0"
        if ("cutoff" not in errors and "dim" not in errors and "n_particles" not in errors
                and "density" not in errors and self.boundary == Boundary.PERIODIC.value
                and self.cutoff > self.box / 2):
            errors["cutoff"] = (f"При PBC нужно r_c ≤ L/2 = {self.box / 2:.3f}; "
                                "увеличьте N или уменьшите ρ")
        return errors

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Snapshot:
    """Мгновенные значения наблюдаемых."""

    step: int
    time: float
    kinetic: float
    potential: float
    total: float
    temperature: float
    pressure: float

    def to_dict(self) -> dict:
        return asdict(self)


class SimulationError(RuntimeError):
    """Численная неустойчивость (NaN/inf, «взрыв» системы)."""


def lattice_positions(n: int, dim: int, box: float) -> np.ndarray:
    """Простая квадратная/кубическая решётка, равномерно заполняющая ячейку."""
    per_side = math.ceil(n ** (1.0 / dim) - 1e-9)
    spacing = box / per_side
    grid = np.stack(np.meshgrid(*[np.arange(per_side)] * dim, indexing="ij"), axis=-1)
    return (grid.reshape(-1, dim)[:n] + 0.5) * spacing


def maxwell_velocities(n: int, dim: int, temperature: float, rng: np.random.Generator,
                       remove_drift: bool = True) -> np.ndarray:
    """Скорости по Максвеллу с точной подгонкой к заданной температуре."""
    v = rng.normal(0.0, math.sqrt(temperature), size=(n, dim))
    if remove_drift:
        v -= v.mean(axis=0)
    dof = dim * (n - 1) if remove_drift else dim * n
    current = np.sum(v**2) / max(dof, 1)
    if current > 0:
        v *= math.sqrt(temperature / current)
    return v


class Simulation:
    HISTORY_LIMIT = 2000

    def __init__(self, params: SimulationParameters) -> None:
        errors = params.validate()
        if errors:
            raise ValueError("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.params = params
        rng = np.random.default_rng(params.seed)
        boundary = Boundary(params.boundary)
        positions = lattice_positions(params.n_particles, params.dim, params.box)
        velocities = maxwell_velocities(params.n_particles, params.dim,
                                        params.initial_temperature, rng,
                                        remove_drift=boundary is Boundary.PERIODIC)
        self.system = ParticleSystem(
            positions=positions,
            velocities=velocities,
            box=params.box,
            potential=LennardJones(cutoff=params.cutoff),
            boundary=boundary,
        )
        self.integrator = VelocityVerlet(params.dt)
        self.thermostat = Thermostat(params.thermostat, params.target_temperature, params.tau)
        self.step_count = 0
        self._forces: ForceResult = self.system.compute_forces()
        self.history: deque[Snapshot] = deque(maxlen=self.HISTORY_LIMIT)
        self.history.append(self.snapshot())

    @property
    def time(self) -> float:
        return self.step_count * self.params.dt

    def step(self, n: int = 1, record_every: int = 1) -> Snapshot:
        """Сделать n шагов интегрирования; в историю пишется каждый record_every-й."""
        for _ in range(n):
            self._forces = self.integrator.step(self.system, self._forces)
            self.thermostat.apply(self.system, self.params.dt)
            self.step_count += 1
            if not self._is_stable():
                raise SimulationError("Численная неустойчивость: уменьшите шаг dt "
                                      "или начальную температуру")
            if self.step_count % record_every == 0:
                self.history.append(self.snapshot())
        return self.snapshot()

    MAX_DISPLACEMENT = 0.5   # в σ за один шаг

    def _is_stable(self) -> bool:
        """Схема устойчива, если числа конечны и атом за шаг сдвигается < σ/2."""
        v = self.system.velocities
        if not (np.isfinite(self._forces.potential_energy) and np.all(np.isfinite(v))):
            return False
        return float(np.max(np.abs(v))) * self.params.dt < self.MAX_DISPLACEMENT

    def snapshot(self) -> Snapshot:
        ke = self.system.kinetic_energy()
        pe = self._forces.potential_energy
        return Snapshot(
            step=self.step_count,
            time=self.time,
            kinetic=ke,
            potential=pe,
            total=ke + pe,
            temperature=self.system.temperature(),
            pressure=pressure(self.system, self._forces.virial),
        )

    def rdf(self, bins: int = 60) -> tuple[np.ndarray, np.ndarray]:
        return radial_distribution(self.system, bins=bins)

    def set_thermostat(self, kind: str, target_temperature: float, tau: float) -> None:
        """Сменить термостат «на лету», не перезапуская симуляцию."""
        self.thermostat = Thermostat(kind, target_temperature, tau)
        self.params.thermostat = kind
        self.params.target_temperature = target_temperature
        self.params.tau = tau
