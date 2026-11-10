# HTTP API (контракт ViewModel ↔ UI)

Сервер — `lj_md/view/app.py`. Каждый маршрут вызывает один метод
`SimulationViewModel` и почти всегда возвращает её `state()` в JSON.
Логики в маршрутах нет: валидация, ошибки и тексты статуса формируются во ViewModel.

Базовый адрес при локальном запуске: `http://127.0.0.1:8000`.

## Сессии

У каждого браузера своя симуляция. При первом запросе сервер выдаёт cookie
`lj_md_session` (`HttpOnly`, `SameSite=Lax`); по ней находится ViewModel
(`ViewModelRegistry`, не более 32 сессий, самые старые вытесняются).
Состояние хранится в памяти процесса, поэтому сервер запускается **одним
процессом** (для gunicorn: `-w 1 --threads N`).

**CORS не нужен и не включён:** страница и API отдаются одним сервером
(один origin). Сторонние сайты обращаться к API не должны.

## Маршруты

| Метод и путь | Тело запроса | Ответ | Метод ViewModel |
|---|---|---|---|
| `GET /` | — | HTML-страница | — |
| `GET /api/schema` | — | схема формы (см. ниже) | `schema()` |
| `GET /api/state` | — | `state` | `state()` |
| `POST /api/tick` | — | `state` после кадра | `tick()` |
| `POST /api/command/<name>` | — | `state`; **404** `{"error"}` для неизвестной команды | `execute(name)` |
| `POST /api/params` | JSON `{поле: значение}` | `state` (ошибки — в `state.errors`) | `update_parameters()` |
| `POST /api/preset/<name>` | — | `state`; **404** для неизвестного пресета | `apply_preset(name)` |
| `GET /api/export.csv` | — | CSV-файл истории | `export_csv()` |
| `GET /api/export.json` | — | JSON-отчёт эксперимента | `export_json()` |

Команды: `start`, `pause`, `step`, `reset`. Недоступная в данный момент
команда (например, `start` во время работы) не выполняется, ответ — обычный
`state`; доступность кнопок View берёт из `state.can`.

Пресеты: `gas`, `liquid`, `solid`.

## Ошибки ввода

Неверный ввод — не HTTP-ошибка, а часть состояния: ответ `200`, в
`state.errors` — сообщения по полям, в `state.status` — `kind: "error"`.
Симуляция при этом не пересоздаётся. Десятичная запятая принимается.

```http
POST /api/params
Content-Type: application/json

{"density": "abc", "dt": "0,002"}
```
```json
{
  "errors": {"density": "Введите число"},
  "status": {"text": "Исправьте выделенные поля", "kind": "error"},
  "...": "остальные поля state"
}
```

Проверки: типы и диапазоны полей (по схеме), затем физическая
согласованность в ядре (`SimulationParameters.validate`, например
r<sub>c</sub> ≤ L/2 при PBC). Тело, не являющееся JSON, игнорируется.

Численная неустойчивость («взрыв» системы) тоже не ломает API:
`status.kind = "error"`, `frame = null`, доступна только команда `reset`.

## Формат `state`

```json
{
  "is_running": false,
  "status": {"text": "Готово к запуску", "kind": "info"},
  "can": {"start": true, "pause": false, "step": true, "reset": true},
  "params": {"n_particles": 64, "dim": 2, "density": 0.5, "initial_temperature": 1.0,
             "dt": 0.005, "cutoff": 2.5, "boundary": "periodic", "thermostat": "none",
             "target_temperature": 1.0, "tau": 0.5, "seed": 42, "steps_per_frame": 10},
  "errors": {},
  "display": {"step": "0", "time": "0.000", "temperature": "1.0000",
              "kinetic_per_atom": "…", "potential_per_atom": "…", "total_per_atom": "…",
              "pressure": "…", "energy_drift": "+0.000 %", "box": "11.314",
              "density": "0.500", "n": "64"},
  "frame": {"dim": 2, "box": 11.314, "boundary": "periodic",
            "positions": [[0.7, 0.7], "…"], "speeds": [1.21, "…"]},
  "rdf": {"r": ["…"], "g": ["…"], "samples": 0},
  "series": {"time": [], "kinetic": [], "potential": [], "total": [],
             "temperature": [], "pressure": []}
}
```

- `display` — уже отформатированные строки: View выводит их как есть.
- `series` — ряды для графиков, энергии на атом, не более 400 точек.
- `rdf` — g(r), усреднённая по времени с момента последнего изменения параметров.

## Схема формы (`/api/schema`)

```json
{
  "fields": [{"name": "density", "label": "Плотность ρ", "kind": "float",
              "min": 0.01, "max": 1.2, "step": 0.01, "live": false,
              "hint": "ρ = N / V, задаёт размер ячейки L", "options": []}, "…"],
  "presets": [{"name": "gas", "label": "Газ"}, "…"]
}
```

`kind`: `int`, `float`, `choice` (варианты — в `options`). Поля с
`live: true` (термостат, скорость анимации) применяются без перезапуска.

## Экспорт

**CSV** (`/api/export.csv`) — история наблюдаемых, полные (не на атом) величины:

```
step,time,kinetic,potential,total,temperature,pressure
0,0.000000,63.00000000,-71.20000000,-8.20000000,1.00000000,0.61000000
```

**JSON** (`/api/export.json`) — отчёт, по которому эксперимент можно
воспроизвести (одинаковые параметры и `seed` дают одинаковую траекторию):

```json
{
  "format": "lj_md-report/1",
  "units": "reduced LJ: sigma = epsilon = m = k_B = 1",
  "parameters": {"…": "как state.params"},
  "status": {"text": "…", "kind": "info"},
  "summary": {"…": "как state.display"},
  "history": [{"step": 0, "time": 0.0, "kinetic": 63.0, "potential": -71.2,
               "total": -8.2, "temperature": 1.0, "pressure": 0.61}],
  "rdf": {"r": [], "g": [], "samples": 0}
}
```

Контракт проверяется тестами `tests/test_viewmodel.py::test_state_contract`
и `tests/test_web.py`.
