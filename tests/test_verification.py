"""Верификация по эталонным (аналитическим) случаям.

Каждый тест сравнивает результат моделирования с заранее известным ответом,
а не только с качественным ожиданием. Таблица кейсов — docs/VERIFICATION.md.
"""

import math

import numpy as np
import pytest

from lj_md.core import (LennardJones, ParticleSystem, Simulation, SimulationParameters,
                        VelocityVerlet)

# U''(r_min) для LJ в приведённых единицах: 72 · 2^(−1/3) ε/σ²
LJ_STIFFNESS = 72.0 * 2.0 ** (-1.0 / 3.0)


def run(system: ParticleSystem, dt: float, steps: int, every=None):
    """Проинтегрировать систему; every(system) вызывается после каждого шага."""
    integrator = VelocityVerlet(dt)
    forces = system.compute_forces()
    for _ in range(steps):
        forces = integrator.step(system, forces)
        if every is not None:
            every(system)
    return forces


# --- Эталон 1: малые колебания пары атомов около минимума --------------------------

def test_two_atom_oscillation_period_matches_harmonic_limit():
    """Две частицы около r_min колеблются с периодом T = 2π·√(μ / U''(r_min)), μ = m/2."""
    lj = LennardJones(cutoff=2.5)
    r0 = lj.r_min + 0.005                      # малое отклонение → гармонический режим
    c = 10.0
    system = ParticleSystem(
        positions=[[c - r0 / 2, c], [c + r0 / 2, c]],
        velocities=np.zeros((2, 2)),
        box=2 * c, potential=lj, boundary="reflective",
    )
    dt = 0.0005
    distances = []
    run(system, dt, 6000, lambda s: distances.append(s.pair_distances()[0]))

    x = np.array(distances) - lj.r_min
    # моменты прохождения через r_min «сверху вниз» отстоят ровно на период
    crossings = np.where((x[:-1] > 0) & (x[1:] <= 0))[0]
    assert len(crossings) >= 3
    measured = np.mean(np.diff(crossings)) * dt

    expected = 2 * math.pi * math.sqrt(0.5 / LJ_STIFFNESS)   # ≈ 0.5877 τ
    assert measured == pytest.approx(expected, rel=0.01)


def test_two_atom_energy_at_rest_in_minimum_is_minus_epsilon():
    """Покоящаяся пара на расстоянии r_min: E_pot = −ε (с учётом сдвига), силы равны нулю."""
    lj = LennardJones(cutoff=2.5)
    system = ParticleSystem(
        positions=[[5.0, 5.0], [5.0 + lj.r_min, 5.0]],
        velocities=np.zeros((2, 2)), box=10.0, potential=lj, boundary="reflective",
    )
    result = system.compute_forces()
    assert result.potential_energy + lj.shift == pytest.approx(-1.0)
    assert np.allclose(result.forces, 0.0, atol=1e-10)


# --- Эталон 2: свободная частица и упругая стенка ----------------------------------------

def test_free_particle_reflects_from_wall_exactly():
    """Одна частица без взаимодействий: x(t) = отражение равномерного движения от стенок."""
    box, x0, v0 = 5.0, 1.0, 1.0
    system = ParticleSystem(positions=[[x0, 2.5]], velocities=[[v0, 0.0]],
                            box=box, boundary="reflective")
    dt, steps = 0.01, 600                     # t = 6: 1 → 5 (стенка) → 3
    run(system, dt, steps)
    assert system.positions[0, 0] == pytest.approx(3.0, abs=1e-9)
    assert system.velocities[0, 0] == pytest.approx(-1.0)
    assert system.kinetic_energy() == pytest.approx(0.5)


def test_free_particle_wraps_around_with_pbc():
    system = ParticleSystem(positions=[[4.0, 1.0]], velocities=[[1.0, 0.5]],
                            box=5.0, boundary="periodic")
    run(system, 0.01, 300)                    # t = 3: x = 7 → 2, y = 2.5
    assert system.positions[0] == pytest.approx([2.0, 2.5], abs=1e-9)


# --- Эталон 3: порядок точности схемы Верле -----------------------------------------------

def _energy_error(dt: float, t_end: float = 1.0) -> float:
    sim = Simulation(SimulationParameters(n_particles=36, dim=2, density=0.5, dt=dt,
                                          initial_temperature=1.0, seed=3))
    e0 = sim.snapshot().total
    sim.step(round(t_end / dt))
    return max(abs(h.total - e0) for h in sim.history)


def test_verlet_energy_error_is_second_order_in_dt():
    """Ошибка энергии схемы Верле ∝ dt²: при уменьшении шага вдвое — в ~4 раза меньше."""
    ratio = _energy_error(0.004) / _energy_error(0.002)
    assert 3.0 < ratio < 5.0
