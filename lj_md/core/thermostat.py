"""Термостаты для перехода от NVE к (приближённо) NVT."""

from __future__ import annotations

from enum import Enum

import numpy as np

from .system import ParticleSystem


class ThermostatKind(str, Enum):
    NONE = "none"                # микроканонический ансамбль, E = const
    RESCALE = "rescale"          # жёсткое перемасштабирование скоростей
    BERENDSEN = "berendsen"      # мягкая релаксация к T0 с временем τ


class Thermostat:
    def __init__(self, kind: ThermostatKind | str = ThermostatKind.NONE,
                 target_temperature: float = 1.0, tau: float = 0.5) -> None:
        self.kind = ThermostatKind(kind)
        if target_temperature <= 0:
            raise ValueError("Целевая температура должна быть положительной")
        if tau <= 0:
            raise ValueError("Время релаксации τ должно быть положительным")
        self.target_temperature = target_temperature
        self.tau = tau

    def apply(self, system: ParticleSystem, dt: float) -> None:
        if self.kind is ThermostatKind.NONE:
            return
        t = system.temperature()
        if t <= 0:
            return
        if self.kind is ThermostatKind.RESCALE:
            lam = np.sqrt(self.target_temperature / t)
        else:  # Berendsen: λ² = 1 + dt/τ (T0/T − 1)
            lam = np.sqrt(max(1.0 + dt / self.tau * (self.target_temperature / t - 1.0), 0.0))
        system.velocities *= lam
