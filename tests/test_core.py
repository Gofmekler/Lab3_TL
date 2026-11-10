"""Тесты физического ядра (Model)."""

import numpy as np
import pytest

from lj_md.core import (Boundary, LennardJones, ParticleSystem, Simulation,
                        SimulationParameters, Thermostat, lattice_positions,
                        maxwell_velocities, radial_distribution)


# --- потенциал -------------------------------------------------------------

def test_potential_minimum_at_r_min():
    lj = LennardJones(cutoff=10.0)
    r = np.linspace(0.95, 3.0, 4000)
    u = lj.energy(r)
    assert r[np.argmin(u)] == pytest.approx(lj.r_min, abs=1e-3)
    # глубина ямы = −ε (с поправкой на малый сдвиг)
    assert lj.energy(lj.r_min) + lj.shift == pytest.approx(-1.0)


def test_potential_is_zero_at_and_beyond_cutoff():
    lj = LennardJones(cutoff=2.5)
    assert lj.energy(2.5) == 0.0
    assert lj.energy(3.0) == 0.0
    assert lj.energy(2.4999) == pytest.approx(0.0, abs=1e-4)  # непрерывность


def test_force_is_minus_gradient_of_energy():
    lj = LennardJones(cutoff=5.0)
    h = 1e-6
    for r in (0.95, 1.1, 1.5, 2.2):
        numeric = -(lj.energy(r + h) - lj.energy(r - h)) / (2 * h)
        analytic = lj.force_over_r(r * r) * r
        assert analytic == pytest.approx(numeric, rel=1e-5)


def test_invalid_potential_parameters():
    with pytest.raises(ValueError):
        LennardJones(epsilon=-1)


# --- система и силы -----------------------------------------------------------

def make_system(n=27, dim=3, density=0.6, temperature=1.0, boundary="periodic", seed=1):
    box = (n / density) ** (1 / dim)
    rng = np.random.default_rng(seed)
    return ParticleSystem(
        positions=lattice_positions(n, dim, box),
        velocities=maxwell_velocities(n, dim, temperature, rng),
        box=box,
        boundary=boundary,
    )


def test_newtons_third_law_total_force_zero():
    system = make_system()
    system.positions += np.random.default_rng(0).normal(0, 0.1, system.positions.shape)
    system.apply_boundary()
    result = system.compute_forces()
    assert np.allclose(result.forces.sum(axis=0), 0.0, atol=1e-9)


def test_forces_match_numerical_gradient_of_total_energy():
    system = make_system(n=8, dim=2, density=0.4)
    system.positions += np.random.default_rng(3).normal(0, 0.15, system.positions.shape)
    forces = system.compute_forces().forces
    h = 1e-6
    for i, d in [(0, 0), (3, 1), (7, 0)]:
        system.positions[i, d] += h
        up = system.compute_forces().potential_energy
        system.positions[i, d] -= 2 * h
        down = system.compute_forces().potential_energy
        system.positions[i, d] += h
        assert forces[i, d] == pytest.approx(-(up - down) / (2 * h), rel=1e-4, abs=1e-6)


def test_minimum_image_convention():
    # две частицы у противоположных стенок на самом деле близки друг к другу
    system = ParticleSystem(positions=[[0.1, 5.0], [9.9, 5.0]],
                            velocities=np.zeros((2, 2)), box=10.0)
    assert system.pair_distances()[0] == pytest.approx(0.2)


def test_reflective_walls_keep_particles_inside_and_flip_velocity():
    system = ParticleSystem(positions=[[-0.2, 5.0], [10.3, 5.0]],
                            velocities=[[-1.0, 0.0], [2.0, 0.0]],
                            box=10.0, boundary=Boundary.REFLECTIVE)
    system.apply_boundary()
    assert np.all((system.positions >= 0) & (system.positions <= 10.0))
    assert system.positions[0, 0] == pytest.approx(0.2)
    assert system.positions[1, 0] == pytest.approx(9.7)
    assert system.velocities[0, 0] == 1.0 and system.velocities[1, 0] == -2.0


def test_initial_velocities_have_exact_temperature_and_zero_momentum():
    system = make_system(n=64, dim=3, temperature=1.7)
    assert system.temperature() == pytest.approx(1.7)
    assert np.allclose(system.momentum(), 0.0, atol=1e-12)


def test_lattice_positions_inside_box_and_unique():
    pos = lattice_positions(50, 2, 10.0)
    assert pos.shape == (50, 2)
    assert np.all((pos > 0) & (pos < 10.0))
    assert len({tuple(p) for p in pos}) == 50


# --- интегрирование ------------------------------------------------------------

@pytest.mark.parametrize("dim", [2, 3])
def test_energy_conservation_nve(dim):
    sim = Simulation(SimulationParameters(n_particles=64, dim=dim, density=0.5,
                                          dt=0.004, cutoff=2.0 if dim == 3 else 2.5))
    e0 = sim.snapshot().total
    sim.step(1000)
    energies = np.array([h.total for h in sim.history])
    # колебания полной энергии на атом малы по сравнению с T ~ 1
    assert np.max(np.abs(energies - e0)) / sim.system.n < 0.005
    # и нет систематического дрейфа
    assert abs(energies[-100:].mean() - energies[:100].mean()) / sim.system.n < 0.002


def test_momentum_conserved_with_pbc():
    sim = Simulation(SimulationParameters(n_particles=49, density=0.6))
    sim.step(300)
    assert np.allclose(sim.system.momentum(), 0.0, atol=1e-9)


def test_verlet_is_time_reversible():
    sim = Simulation(SimulationParameters(n_particles=25, density=0.4))
    start = sim.system.positions.copy()
    sim.step(200)
    sim.system.velocities *= -1
    sim._forces = sim.system.compute_forces()
    sim.step(200)
    assert np.allclose(sim.system.positions, start, atol=1e-6)


def test_berendsen_thermostat_drives_temperature_to_target():
    params = SimulationParameters(n_particles=64, density=0.5, initial_temperature=2.0,
                                  thermostat="berendsen", target_temperature=0.5, tau=0.1)
    sim = Simulation(params)
    sim.step(1500)
    recent = [h.temperature for h in list(sim.history)[-300:]]
    assert np.mean(recent) == pytest.approx(0.5, rel=0.05)


def test_rescale_thermostat_sets_exact_temperature():
    system = make_system(temperature=3.0)
    Thermostat("rescale", target_temperature=1.2).apply(system, dt=0.005)
    assert system.temperature() == pytest.approx(1.2)


def test_ideal_gas_limit_pressure():
    # при очень малой плотности P ≈ ρT
    params = SimulationParameters(n_particles=100, density=0.005, initial_temperature=1.5)
    snap = Simulation(params).snapshot()
    assert snap.pressure == pytest.approx(params.density * snap.temperature, rel=0.05)


# --- параметры и наблюдаемые ---------------------------------------------------

def test_parameters_validation_cutoff_vs_box():
    errors = SimulationParameters(n_particles=8, dim=3, density=1.0, cutoff=2.5).validate()
    assert "cutoff" in errors


def test_parameters_validation_ok_for_defaults():
    assert SimulationParameters().validate() == {}


def test_simulation_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        Simulation(SimulationParameters(dt=-1))


def test_rdf_tends_to_one_for_ideal_gas():
    rng = np.random.default_rng(0)
    box = 30.0
    system = ParticleSystem(positions=rng.uniform(0, box, (800, 2)),
                            velocities=np.zeros((800, 2)), box=box)
    r, g = radial_distribution(system, bins=30)
    assert np.mean(g[5:]) == pytest.approx(1.0, abs=0.05)


def test_dense_liquid_rdf_has_first_peak_near_sigma():
    sim = Simulation(SimulationParameters(n_particles=100, density=0.7,
                                          thermostat="berendsen", target_temperature=0.8))
    sim.step(400)
    r, g = sim.rdf()
    assert 0.95 < r[np.argmax(g)] < 1.3
    assert g.max() > 1.5
    assert np.all(g[r < 0.8] == 0)  # атомы не перекрываются
