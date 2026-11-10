"""ViewModel главного экрана.

Отвечает за:
* хранение параметров формы и их валидацию (ошибки по полям);
* команды: старт, пауза, шаг, сброс, применение параметров, пресеты;
* подготовку данных для отображения (округление, прореживание графиков,
  форматирование чисел) — View ничего не считает сам.

ViewModel не знает, что View — это веб-страница: наружу отдаётся обычный
словарь ``state()``, который можно отрисовать хоть в Tkinter, хоть в Qt.
"""

from __future__ import annotations

import io
import json
import threading
from dataclasses import dataclass, fields, replace
from typing import Any

import numpy as np

from ..core import (Boundary, RdfAverager, Simulation, SimulationError,
                    SimulationParameters, ThermostatKind)
from .observable import Command, Observable, ObservableProperty


@dataclass(frozen=True)
class FieldSpec:
    """Описание поля формы — View строит по нему элементы управления."""

    name: str
    label: str
    kind: str                                  # "int" | "float" | "choice"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: tuple[tuple[Any, str], ...] = ()
    live: bool = False                         # можно менять без перезапуска
    hint: str = ""

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in ("name", "label", "kind", "min", "max",
                                           "step", "live", "hint")}
        d["options"] = [{"value": v, "label": label} for v, label in self.options]
        return d


FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("n_particles", "Число частиц N", "int", 2, 1000, 1,
              hint="Сложность O(N²): больше 400 будет медленно"),
    FieldSpec("dim", "Размерность", "choice", options=((2, "2D"), (3, "3D"))),
    FieldSpec("density", "Плотность ρ", "float", 0.01, 1.2, 0.01,
              hint="ρ = N / V, задаёт размер ячейки L"),
    FieldSpec("initial_temperature", "Начальная T₀", "float", 0.01, 10, 0.05),
    FieldSpec("dt", "Шаг по времени dt", "float", 0.0005, 0.02, 0.0005),
    FieldSpec("cutoff", "Радиус обрезки r_c", "float", 1.0, 5.0, 0.1),
    FieldSpec("boundary", "Границы ячейки", "choice",
              options=((Boundary.PERIODIC.value, "Периодические (PBC)"),
                       (Boundary.REFLECTIVE.value, "Отражающие стенки"))),
    FieldSpec("seed", "Seed генератора", "int", 0, 2**31 - 1, 1),
    FieldSpec("thermostat", "Термостат", "choice", live=True,
              options=((ThermostatKind.NONE.value, "Нет (NVE)"),
                       (ThermostatKind.BERENDSEN.value, "Берендсен"),
                       (ThermostatKind.RESCALE.value, "Масштабирование скоростей"))),
    FieldSpec("target_temperature", "Целевая T термостата", "float", 0.01, 10, 0.05,
              live=True),
    FieldSpec("tau", "τ термостата", "float", 0.01, 10, 0.05, live=True),
    FieldSpec("steps_per_frame", "Шагов за кадр", "int", 1, 200, 1, live=True,
              hint="Скорость анимации"),
)
FIELD_BY_NAME = {f.name: f for f in FIELDS}

PRESETS: dict[str, dict[str, Any]] = {
    "gas":    {"density": 0.05, "initial_temperature": 2.0, "thermostat": "none"},
    "liquid": {"density": 0.70, "initial_temperature": 1.0, "thermostat": "berendsen",
               "target_temperature": 0.8},
    "solid":  {"density": 0.90, "initial_temperature": 0.3, "thermostat": "berendsen",
               "target_temperature": 0.2},
}
PRESET_LABELS = {"gas": "Газ", "liquid": "Жидкость", "solid": "Кристалл"}

MAX_SERIES_POINTS = 400


@dataclass(frozen=True)
class _Status:
    text: str = "Готово к запуску"
    kind: str = "info"   # info | error


class SimulationViewModel(Observable):
    is_running: bool = ObservableProperty(False)  # type: ignore[assignment]
    status: _Status = ObservableProperty(_Status())  # type: ignore[assignment]

    def __init__(self, params: SimulationParameters | None = None,
                 steps_per_frame: int = 10) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self.params = params or SimulationParameters()
        self.steps_per_frame = steps_per_frame
        self.errors: dict[str, str] = {}
        self._rdf = RdfAverager(bins=60)
        self._build()

        # Команды (View вызывает их по имени через ``execute``)
        self.commands: dict[str, Command] = {
            "start": Command(self._start, lambda: not self.is_running and self._ok),
            "pause": Command(self._pause, lambda: self.is_running),
            "step":  Command(self._step, lambda: not self.is_running and self._ok),
            "reset": Command(self._reset),
        }

    # --- служебное ----------------------------------------------------------

    @property
    def _ok(self) -> bool:
        return self.simulation is not None

    def _build(self) -> None:
        self.simulation: Simulation | None = Simulation(replace(self.params))
        self._rdf.reset()
        self._energy_ref = self.simulation.snapshot().total

    def _advance(self, n: int) -> None:
        assert self.simulation is not None
        record_every = max(1, self.steps_per_frame // 5)
        try:
            self.simulation.step(n, record_every=record_every)
        except SimulationError as exc:
            self.is_running = False
            self.simulation = None
            self.status = _Status(f"{exc}. Нажмите «Сброс».", "error")
            return
        self._rdf.sample(self.simulation.system)

    # --- команды ------------------------------------------------------------

    def _start(self) -> None:
        self.is_running = True
        self.status = _Status("Моделирование идёт")

    def _pause(self) -> None:
        self.is_running = False
        self.status = _Status("Пауза")

    def _step(self) -> None:
        self._advance(self.steps_per_frame)
        if self._ok:
            self.status = _Status(f"Сделано {self.steps_per_frame} шагов")

    def _reset(self) -> None:
        self.is_running = False
        self._build()
        self.status = _Status("Система переинициализирована")

    def execute(self, name: str) -> bool:
        """Выполнить команду по имени. Возвращает False, если она недоступна."""
        with self._lock:
            cmd = self.commands.get(name)
            if cmd is None:
                raise KeyError(f"Неизвестная команда: {name}")
            if not cmd.can_execute:
                return False
            cmd()
            return True

    def tick(self) -> None:
        """Вызывается View на каждом кадре анимации."""
        with self._lock:
            if self.is_running and self._ok:
                self._advance(self.steps_per_frame)

    # --- параметры ----------------------------------------------------------

    def parameter_values(self) -> dict[str, Any]:
        values = self.params.to_dict()
        values["steps_per_frame"] = self.steps_per_frame
        return values

    @staticmethod
    def _parse(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        parsed: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for name, value in raw.items():
            spec = FIELD_BY_NAME.get(name)
            if spec is None:
                continue
            try:
                if spec.kind == "int":
                    num = float(value)
                    if not num.is_integer():
                        raise ValueError
                    parsed[name] = int(num)
                elif spec.kind == "float":
                    parsed[name] = float(str(value).replace(",", "."))
                    if not np.isfinite(parsed[name]):
                        raise ValueError
                else:
                    allowed = {str(v): v for v, _ in spec.options}
                    if str(value) not in allowed:
                        errors[name] = "Недопустимое значение"
                        continue
                    parsed[name] = allowed[str(value)]
            except (TypeError, ValueError):
                errors[name] = "Введите целое число" if spec.kind == "int" else "Введите число"
        return parsed, errors

    def update_parameters(self, raw: dict[str, Any]) -> bool:
        """Применить значения из формы.

        Если изменились только «живые» поля (термостат, скорость анимации) —
        симуляция продолжается. Иначе система пересоздаётся и ставится на паузу.
        Возвращает True при успехе; ошибки — в ``self.errors``.
        """
        with self._lock:
            parsed, errors = self._parse(raw)
            steps = parsed.pop("steps_per_frame", self.steps_per_frame)
            spf = FIELD_BY_NAME["steps_per_frame"]
            if "steps_per_frame" not in errors and not spf.min <= steps <= spf.max:
                errors["steps_per_frame"] = f"От {spf.min:g} до {spf.max:g}"

            known = {f.name for f in fields(SimulationParameters)}
            candidate = replace(self.params, **{k: v for k, v in parsed.items() if k in known})
            for name, msg in candidate.validate().items():
                errors.setdefault(name, msg)

            self.errors = errors
            if errors:
                self.status = _Status("Исправьте выделенные поля", "error")
                self.notify("errors", errors)
                return False

            self.steps_per_frame = steps
            changed = {k for k in known if getattr(candidate, k) != getattr(self.params, k)}
            needs_rebuild = any(not FIELD_BY_NAME[k].live for k in changed) or not self._ok
            self.params = candidate
            if needs_rebuild:
                self.is_running = False
                self._build()
                self.status = _Status("Параметры применены, система пересоздана")
            elif changed:
                assert self.simulation is not None
                self.simulation.set_thermostat(candidate.thermostat,
                                               candidate.target_temperature, candidate.tau)
                self._rdf.reset()
                self._energy_ref = self.simulation.snapshot().total
                self.status = _Status("Термостат обновлён без перезапуска")
            self.notify("params", self.parameter_values())
            return True

    def apply_preset(self, name: str) -> bool:
        if name not in PRESETS:
            raise KeyError(f"Неизвестный пресет: {name}")
        ok = self.update_parameters(PRESETS[name])
        if ok:
            self.status = _Status(f"Пресет «{PRESET_LABELS[name]}» загружен")
        return ok

    # --- данные для View ----------------------------------------------------

    @staticmethod
    def schema() -> dict:
        return {
            "fields": [f.to_dict() for f in FIELDS],
            "presets": [{"name": k, "label": v} for k, v in PRESET_LABELS.items()],
        }

    def _display(self) -> dict[str, str]:
        sim = self.simulation
        if sim is None:
            return {}
        s = sim.snapshot()
        if self.params.thermostat == ThermostatKind.NONE.value and self._energy_ref != 0:
            drift = f"{(s.total - self._energy_ref) / abs(self._energy_ref) * 100:+.3f} %"
        else:
            drift = "— (NVT)"
        return {
            "step": f"{s.step}",
            "time": f"{s.time:.3f}",
            "temperature": f"{s.temperature:.4f}",
            "kinetic_per_atom": f"{s.kinetic / sim.system.n:.4f}",
            "potential_per_atom": f"{s.potential / sim.system.n:.4f}",
            "total_per_atom": f"{s.total / sim.system.n:.4f}",
            "pressure": f"{s.pressure:.4f}",
            "energy_drift": drift,
            "box": f"{sim.system.box:.3f}",
            "density": f"{sim.system.density:.3f}",
            "n": f"{sim.system.n}",
        }

    def _series(self) -> dict[str, list[float]]:
        if self.simulation is None:
            return {}
        hist = list(self.simulation.history)
        stride = max(1, len(hist) // MAX_SERIES_POINTS)
        hist = hist[::stride]
        n = self.simulation.system.n
        return {
            "time": [round(h.time, 4) for h in hist],
            "kinetic": [round(h.kinetic / n, 5) for h in hist],
            "potential": [round(h.potential / n, 5) for h in hist],
            "total": [round(h.total / n, 5) for h in hist],
            "temperature": [round(h.temperature, 5) for h in hist],
            "pressure": [round(h.pressure, 5) for h in hist],
        }

    def _frame(self) -> dict | None:
        sim = self.simulation
        if sim is None:
            return None
        speeds = np.linalg.norm(sim.system.velocities, axis=1)
        return {
            "dim": sim.system.dim,
            "box": sim.system.box,
            "boundary": sim.system.boundary.value,
            "positions": np.round(sim.system.positions, 4).tolist(),
            "speeds": np.round(speeds, 4).tolist(),
        }

    def _rdf_data(self) -> dict:
        if self._rdf.r is None:
            return {"r": [], "g": [], "samples": 0}
        return {"r": np.round(self._rdf.r, 4).tolist(),
                "g": np.round(self._rdf.g, 4).tolist(),
                "samples": self._rdf.samples}

    def state(self, include_series: bool = True) -> dict:
        """Полное состояние для отрисовки. Единственный «контракт» с View."""
        with self._lock:
            data = {
                "is_running": self.is_running,
                "status": {"text": self.status.text, "kind": self.status.kind},
                "can": {name: cmd.can_execute for name, cmd in self.commands.items()},
                "params": self.parameter_values(),
                "errors": dict(self.errors),
                "display": self._display(),
                "frame": self._frame(),
                "rdf": self._rdf_data(),
            }
            if include_series:
                data["series"] = self._series()
            return data

    def export_csv(self) -> str:
        """История наблюдаемых в CSV — для отчёта по лабораторной."""
        with self._lock:
            buf = io.StringIO()
            buf.write("step,time,kinetic,potential,total,temperature,pressure\n")
            if self.simulation is not None:
                for h in self.simulation.history:
                    buf.write(f"{h.step},{h.time:.6f},{h.kinetic:.8f},{h.potential:.8f},"
                              f"{h.total:.8f},{h.temperature:.8f},{h.pressure:.8f}\n")
            return buf.getvalue()

    def export_json(self) -> str:
        """Полный отчёт об эксперименте: параметры (вкл. seed), итоговые величины,
        история наблюдаемых и g(r). По параметрам эксперимент воспроизводится заново."""
        with self._lock:
            history = list(self.simulation.history) if self.simulation is not None else []
            report = {
                "format": "lj_md-report/1",
                "units": "reduced LJ: sigma = epsilon = m = k_B = 1",
                "parameters": self.parameter_values(),
                "status": {"text": self.status.text, "kind": self.status.kind},
                "summary": self._display(),
                "history": [h.to_dict() for h in history],
                "rdf": self._rdf_data(),
            }
            return json.dumps(report, ensure_ascii=False, indent=2)
