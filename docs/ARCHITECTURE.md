# Архитектура: MVVM

```
┌──────────────────────── Браузер ───────────────────────┐
│  VIEW (клиент)  index.html + app.js / scene.js / charts │
│   data-bind="display.temperature"   → текст            │
│   data-command="start"              → кнопка           │
│   форма строится по схеме полей из ViewModel           │
└───────────────▲──────────────────────────┬─────────────┘
                │ JSON state()             │ команды / параметры (HTTP)
┌───────────────┴──────────────────────────▼─────────────┐
│  VIEW (сервер)  view/app.py — Flask, без логики         │
├────────────────────────────────────────────────────────┤
│  VIEWMODEL  viewmodel/simulation_vm.py                  │
│   • свойства: is_running, status, errors, params        │
│   • команды:  start, pause, step, reset                 │
│   • update_parameters / apply_preset (валидация)        │
│   • state(): форматированные числа, ряды для графиков   │
├────────────────────────────────────────────────────────┤
│  MODEL  core/                                           │
│   Simulation → ParticleSystem, VelocityVerlet,          │
│                Thermostat, LennardJones, observables    │
└────────────────────────────────────────────────────────┘
```

Зависимости направлены строго вниз: `view → viewmodel → core`.
Ядро не импортирует ничего из верхних слоёв, ViewModel не импортирует Flask.

## Model (`lj_md/core`)

Чистая физика на NumPy. Единственная точка входа для верхних слоёв —
`Simulation(SimulationParameters)`:

| Метод | Что делает |
|---|---|
| `step(n, record_every)` | n шагов Верле + термостат, запись истории |
| `snapshot()` | мгновенные E<sub>kin</sub>, E<sub>pot</sub>, E, T, P |
| `history` | кольцевой буфер `Snapshot` (до 2000 точек) |
| `set_thermostat(...)` | смена термостата без перезапуска |
| `SimulationParameters.validate()` | физическая согласованность (например, r<sub>c</sub> ≤ L/2 при PBC) |

При «взрыве» системы (NaN или смещение атома > σ/2 за шаг) выбрасывается
`SimulationError` — ядро не решает, как об этом сообщить пользователю.

## ViewModel (`lj_md/viewmodel`)

- `ObservableProperty` и `Observable.subscribe` — уведомления об изменениях
  (аналог `INotifyPropertyChanged` в WPF). Подписаться может любой View:
  веб, консоль, Qt.
- `Command(execute, can_execute)` — аналог `RelayCommand`. Доступность кнопок
  в интерфейсе берётся из `state()["can"]`, View сам ничего не решает.
- Описание полей формы (`FIELDS`: подпись, тип, диапазон, «live») живёт во
  ViewModel — View строит форму по схеме `/api/schema`.
- Разбор пользовательского ввода (в т. ч. десятичная запятая), ошибки по полям.
- Поля с `live=True` (термостат, скорость анимации) применяются на лету,
  остальные пересоздают систему.
- `SimulationError` превращается в статус ошибки, а не в исключение.
- Подготовка данных: округление, прореживание рядов до 400 точек, энергия
  на атом, дрейф энергии, усреднение g(r).
- Экспорт: `export_csv()` (история) и `export_json()` (воспроизводимый отчёт).

ViewModel тестируется без браузера и без сервера (`tests/test_viewmodel.py`).

## View (`lj_md/view`)

Сервер (`app.py`) — только маршрутизация: каждое действие пользователя
передаётся во ViewModel, ответ — всегда `vm.state()`.

| Маршрут | Действие ViewModel |
|---|---|
| `GET /api/schema` | `SimulationViewModel.schema()` |
| `GET /api/state` | `state()` |
| `POST /api/tick` | `tick()` — кадр анимации |
| `POST /api/command/<name>` | `execute(name)` |
| `POST /api/params` | `update_parameters(json)` |
| `POST /api/preset/<name>` | `apply_preset(name)` |
| `GET /api/export.csv` | `export_csv()` |
| `GET /api/export.json` | `export_json()` |

У каждого браузера своя ViewModel (cookie-сессия, `ViewModelRegistry`).
Форматы запросов и ответов с примерами — [API.md](API.md).

Клиент (`static/app.js`) реализует декларативную привязку:
`data-bind="путь.в.state"` и `data-command="имя"`. Единственное
собственное состояние View — положение камеры в 3D (чисто визуальное).

## Почему так

- Ядро можно проверить тестами на физические законы (сохранение энергии
  и импульса, обратимость, предел идеального газа) и на эталонные случаи
  с аналитическим ответом независимо от UI — см. [VERIFICATION.md](VERIFICATION.md).
- UI можно заменить (например, на PyQt) без изменения ядра и ViewModel —
  достаточно нового View, вызывающего те же команды и читающего `state()`.
- Разделение совпадает с ролями в команде: Core — Model, UI — ViewModel и View,
  тимлид — контракты между ними. См. [ROLES.md](ROLES.md).
