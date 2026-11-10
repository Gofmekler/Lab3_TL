# HTTP API (контракт View ↔ ViewModel)

Единственный источник данных для интерфейса — `SimulationViewModel.state()`.
Сервер (`lj_md/view/app.py`) не содержит логики: каждый маршрут вызывает
один метод ViewModel и возвращает её состояние. Контракт закреплён тестами
`tests/test_web.py` (`assert_state_contract`) — изменение формата без
обновления этого документа и тестов роняет CI.

Сессия: cookie `lj_md_session` (httponly, SameSite=Lax); у каждой сессии
своя ViewModel (до 32 сессий, старые вытесняются). Сервер по умолчанию
слушает только `127.0.0.1`.

## Маршруты

| Метод | Путь | Действие ViewModel | Успех |
|---|---|---|---|
| GET | `/` | — (страница) | 200 HTML |
| GET | `/api/schema` | `schema()` — поля формы, пресеты, версия | 200 |
| GET | `/api/state` | `state()` | 200 |
| POST | `/api/tick` | `tick()` — кадр анимации (если фаза `running`) | 200 |
| POST | `/api/command/{start\|pause\|step\|reset}` | `execute(name)` | 200 |
| POST | `/api/params` | `update_parameters(body)` | 200 |
| POST | `/api/preset/{gas\|liquid\|solid}` | `apply_preset(name)` | 200 |
| POST | `/api/experiment` | `load_experiment(body)` — повтор из JSON | 200 |
| GET | `/api/export.csv` | `export_csv()` | 200 text/csv |
| GET | `/api/export.json` | `export_json()` | 200 application/json |

Тело успешного ответа на все POST и `GET /api/state` — объект **state** (ниже).

## Ошибки

```json
{"error": {"code": "validation_failed", "message": "Исправьте выделенные поля"},
 "state": { ... }}
```

`state` присутствует, если запрос дошёл до ViewModel (интерфейс сразу
показывает ошибки у полей и актуальную фазу).

| HTTP | code | Когда |
|---|---|---|
| 400 | `bad_request` | тело не JSON или не объект |
| 400 | `bad_format` | файл эксперимента не соответствует схеме (версия, лишние/недостающие параметры) |
| 404 | `unknown_command`, `unknown_preset`, `not_found` | неизвестное имя или маршрут |
| 405 | `method_not_allowed` | неверный метод |
| 409 | `command_unavailable` | команда недоступна в текущей фазе (например, `start` в `running`) |
| 413 | `too_large` | тело больше 64 КБ |
| 422 | `validation_failed` | значения разобраны, но не прошли проверку; подробности в `state.errors` |
| 500 | `internal_error` | непредвиденная ошибка сервера (пишется в журнал) |

## Объект state

```jsonc
{
  "phase": "idle" | "running" | "paused" | "completed" | "failed",
  "is_running": false,
  "status": {"text": "Готово к запуску", "kind": "info" | "error"},
  "can": {"start": true, "pause": false, "step": true, "reset": true},
  "params": {                       // текущие применённые параметры
    "n_particles": 64, "dim": 2, "density": 0.5, "initial_temperature": 1.0,
    "dt": 0.005, "cutoff": 2.5, "boundary": "periodic" | "reflective",
    "thermostat": "none" | "berendsen" | "rescale", "target_temperature": 1.0,
    "tau": 0.5, "seed": 42, "t_max": 0.0, "steps_per_frame": 10
  },
  "errors": {"dt": "Шаг: 0 < dt ≤ 0.02 (иначе схема неустойчива)"},   // по полям
  "display": {                      // готовые к показу строки, View ничего не форматирует
    "phase", "step", "time", "progress", "temperature", "temperature_si", "time_si",
    "kinetic_per_atom", "potential_per_atom", "total_per_atom", "pressure",
    "pressure_si", "pressure_wall", "energy_drift", "box", "density", "n",
    "steps_per_frame"
  },
  "frame": {"dim": 2, "box": 11.31, "boundary": "periodic",
            "positions": [[x, y], ...], "speeds": [v, ...]},
  "rdf": {"r": [...], "g": [...], "samples": 12},
  "series": {"time": [...], "kinetic": [...], "potential": [...], "total": [...],
             "temperature": [...], "pressure": [...]}   // ≤ ~400 точек, энергии на атом
}
```

Все числа конечные (строгий JSON без `NaN`/`Infinity`): при численном сбое
система откатывается к последнему устойчивому состоянию, фаза — `failed`.

## Тело `POST /api/params`

Любое подмножество полей `params`; значения — числа или строки
(допускается десятичная запятая). Проверяются **все** поля до применения;
при ошибке не меняется ничего. Поля с `live: true` в схеме (`thermostat`,
`target_temperature`, `tau`, `t_max`, `steps_per_frame`) применяются без
пересоздания системы, остальные пересоздают её (фаза `idle`).

## Файл эксперимента (`export.json`, `POST /api/experiment`)

```jsonc
{
  "app": "lj_md", "app_version": "1.1.0", "schema_version": 1,
  "exported_at": "2026-10-27T12:00:00+00:00",
  "units": "...", "potential": "...", "integrator": "velocity Verlet",
  "parameters": { ...все поля params... },
  "termination": {"phase": "completed", "reason": "t_max_reached" | "numerical_instability"
                  | "stopped_by_user_or_in_progress", "message": null, "steps": 600, "time": 3.0},
  "summary": {"final": {...Snapshot...}, "pressure_wall": null, "energy_reference": -69.8},
  "history": {"columns": ["step", "time_tau", "E_kin_eps", "E_pot_eps", "E_total_eps",
                          "T_eps_per_kB", "P_virial_reduced"], "rows": [[...], ...]},
  "rdf": {"r": [...], "g": [...], "samples": 60}
}
```

Для повтора эксперимента клиент отправляет только `schema_version` и
`parameters`. Схема строгая: неизвестные и отсутствующие параметры — `400 bad_format`,
недопустимые значения — `422`.

## CSV (`export.csv`)

Строки `# ключ: значение` — метаданные (версия, единицы, все параметры,
причина завершения), затем таблица в полной точности:

```
step,time_tau,E_kin_eps,E_pot_eps,E_total_eps,T_eps_per_kB,P_virial_reduced
```

Чтение: `pandas.read_csv("lj_md_history.csv", comment="#")`.
