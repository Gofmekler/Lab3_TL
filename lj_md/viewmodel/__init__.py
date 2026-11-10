"""ViewModel (MVVM): состояние экрана и команды, без привязки к конкретному UI."""

from .observable import Command, Observable, ObservableProperty
from .simulation_vm import FIELDS, PRESETS, FieldSpec, SimulationViewModel

__all__ = ["Command", "FIELDS", "FieldSpec", "Observable", "ObservableProperty",
           "PRESETS", "SimulationViewModel"]
