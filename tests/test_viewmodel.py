"""Тесты ViewModel: команды, валидация, состояние для View. Без браузера и сервера."""

import pytest

from lj_md.core import SimulationParameters
from lj_md.viewmodel import Command, Observable, ObservableProperty, SimulationViewModel


class Dummy(Observable):
    value = ObservableProperty(0)


def test_observable_property_notifies_only_on_change():
    obj, log = Dummy(), []
    unsubscribe = obj.subscribe(lambda name, v: log.append((name, v)))
    obj.value = 5
    obj.value = 5
    obj.value = 7
    unsubscribe()
    obj.value = 9
    assert log == [("value", 5), ("value", 7)]


def test_command_respects_can_execute():
    calls = []
    enabled = {"on": False}
    cmd = Command(lambda: calls.append(1), lambda: enabled["on"])
    cmd()
    enabled["on"] = True
    cmd()
    assert calls == [1]


@pytest.fixture
def vm():
    return SimulationViewModel(SimulationParameters(n_particles=36), steps_per_frame=5)


def test_start_pause_and_command_availability(vm):
    assert vm.state()["can"] == {"start": True, "pause": False, "step": True, "reset": True}
    assert vm.execute("start")
    assert vm.is_running
    assert vm.state()["can"]["start"] is False
    assert not vm.execute("start")          # недоступна во время работы
    assert vm.execute("pause")
    assert not vm.is_running


def test_tick_advances_only_when_running(vm):
    vm.tick()
    assert vm.simulation.step_count == 0
    vm.execute("start")
    vm.tick()
    vm.tick()
    assert vm.simulation.step_count == 10


def test_step_command(vm):
    vm.execute("step")
    assert vm.state()["display"]["step"] == "5"


def test_reset_returns_to_initial_state(vm):
    vm.execute("start")
    vm.tick()
    vm.execute("reset")
    assert not vm.is_running
    assert vm.simulation.step_count == 0


def test_invalid_input_produces_field_errors_and_keeps_simulation(vm):
    sim_before = vm.simulation
    ok = vm.update_parameters({"n_particles": "abc", "dt": "0.5", "boundary": "nope"})
    assert not ok
    assert set(vm.errors) == {"n_particles", "dt", "boundary"}
    assert vm.status.kind == "error"
    assert vm.simulation is sim_before


def test_decimal_comma_is_accepted(vm):
    assert vm.update_parameters({"density": "0,3"})
    assert vm.params.density == pytest.approx(0.3)


def test_structural_change_rebuilds_and_pauses(vm):
    vm.execute("start")
    assert vm.update_parameters({"n_particles": "49"})
    assert not vm.is_running
    assert vm.simulation.system.n == 49


def test_live_change_keeps_running(vm):
    vm.execute("start")
    vm.tick()
    sim = vm.simulation
    assert vm.update_parameters({"thermostat": "berendsen", "target_temperature": "0.4",
                                 "steps_per_frame": "20"})
    assert vm.is_running
    assert vm.simulation is sim
    assert vm.simulation.thermostat.target_temperature == 0.4
    assert vm.steps_per_frame == 20


def test_presets(vm):
    assert vm.apply_preset("gas")
    assert vm.params.density == pytest.approx(0.05)
    with pytest.raises(KeyError):
        vm.apply_preset("plasma")


def test_unknown_command(vm):
    with pytest.raises(KeyError):
        vm.execute("explode")


def test_state_contract(vm):
    vm.execute("step")
    state = vm.state()
    for key in ("is_running", "status", "can", "params", "errors", "display",
                "frame", "rdf", "series"):
        assert key in state
    assert len(state["frame"]["positions"]) == 36
    assert len(state["series"]["time"]) == len(state["series"]["total"])
    assert state["params"]["steps_per_frame"] == 5


def test_series_are_downsampled():
    vm = SimulationViewModel(SimulationParameters(n_particles=16, density=0.3),
                             steps_per_frame=5)
    vm.simulation.step(1500)
    assert len(vm.state()["series"]["time"]) <= 800


def test_blowup_is_reported_not_raised():
    vm = SimulationViewModel(SimulationParameters(n_particles=16, density=0.3))
    vm.simulation.system.positions[1] = vm.simulation.system.positions[0] + 1e-9
    vm.simulation._forces = vm.simulation.system.compute_forces()
    vm.execute("start")
    vm.tick()
    assert not vm.is_running
    assert vm.status.kind == "error"
    assert vm.state()["frame"] is None
    assert vm.execute("reset")
    assert vm.simulation is not None


def test_export_csv(vm):
    vm.execute("step")
    lines = vm.export_csv().strip().splitlines()
    assert lines[0].startswith("step,time")
    assert len(lines) >= 2


def test_export_json_is_reproducible_report(vm):
    import json
    vm.execute("step")
    report = json.loads(vm.export_json())
    assert report["format"] == "lj_md-report/1"
    assert report["parameters"]["seed"] == vm.params.seed
    assert report["history"] and {"step", "time", "total"} <= set(report["history"][0])
    assert set(report["rdf"]) == {"r", "g", "samples"}
    # по параметрам из отчёта получается тот же начальный кадр
    from lj_md.viewmodel import SimulationViewModel
    params = {k: v for k, v in report["parameters"].items() if k != "steps_per_frame"}
    again = SimulationViewModel(SimulationParameters(**params),
                                steps_per_frame=report["parameters"]["steps_per_frame"])
    again.execute("step")
    assert again.export_json() == vm.export_json()
