"""Интегратор Верле в скоростной форме (velocity Verlet).

    v(t + dt/2) = v(t) + F(t)/m · dt/2
    r(t + dt)   = r(t) + v(t + dt/2) · dt
    v(t + dt)   = v(t + dt/2) + F(t + dt)/m · dt/2

Схема симплектическая и обратимая во времени — полная энергия в NVE
не дрейфует, а лишь колеблется с амплитудой ~dt².
"""

from __future__ import annotations

from .system import ForceResult, ParticleSystem


class VelocityVerlet:
    def __init__(self, dt: float) -> None:
        if dt <= 0:
            raise ValueError("Шаг по времени должен быть положительным")
        self.dt = dt

    def step(self, system: ParticleSystem, current: ForceResult) -> ForceResult:
        """Сделать один шаг. Принимает силы в момент t, возвращает силы в t + dt."""
        half = 0.5 * self.dt / system.mass
        system.velocities += half * current.forces
        system.positions += self.dt * system.velocities
        system.apply_boundary()
        new = system.compute_forces()
        system.velocities += half * new.forces
        return new
