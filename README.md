# Lab3TL_LJ — MD: атомы в ячейке (потенциал Леннард-Джонса)

[![tests](https://github.com/Gofmekler/Lab3_TL/actions/workflows/tests.yml/badge.svg)](https://github.com/Gofmekler/Lab3_TL/actions/workflows/tests.yml)

Веб-приложение для моделирования движения атомов в ячейке методом
молекулярной динамики. Атомы взаимодействуют по потенциалу Леннард-Джонса,
уравнения движения интегрируются схемой Верле. Архитектура — **MVVM**.

## Возможности

- 2D и 3D (в 3D ячейку можно вращать мышью);
- периодические граничные условия или отражающие стенки;
- ансамбль NVE (без термостата) или NVT (термостат Берендсена / масштабирование скоростей);
- пресеты «Газ», «Жидкость», «Кристалл»;
- графики энергии (E<sub>kin</sub>, E<sub>pot</sub>, E), температуры, давления;
- функция радиального распределения g(r), усреднённая по времени;
- контроль сохранения энергии (дрейф E в NVE);
- выгрузка истории наблюдаемых в CSV и полного отчёта в JSON (параметры, итоги,
  история, g(r)) — по JSON эксперимент воспроизводится заново;
- верификация по эталонным аналитическим случаям и законам сохранения
  ([docs/VERIFICATION.md](docs/VERIFICATION.md)).

## Запуск в PyCharm (macOS)

1. **Python.** Нужен Python 3.10+. Проверьте в Терминале: `python3 --version`.
   Если Python нет — установите с [python.org](https://www.python.org/downloads/macos/)
   или через Homebrew: `brew install python`.
2. **Открыть проект.** PyCharm → *File → Open…* → выберите папку `Lab3TL_LJ`
   (или *Get from VCS* и вставьте ссылку на репозиторий).
3. **Интерпретатор.** PyCharm → *Settings* (⌘,) → *Project: Lab3TL_LJ →
   Python Interpreter* → *Add Interpreter → Add Local Interpreter →
   Virtualenv Environment → New*, базовый интерпретатор — `python3`,
   папка `.venv` внутри проекта → *OK*.
4. **Зависимости.** PyCharm сам предложит установить пакеты из
   `requirements.txt` (жёлтая плашка вверху редактора → *Install requirements*).
   Если плашки нет — откройте вкладку *Terminal* внизу (⌥F12) и выполните:
   ```bash
   pip install -r requirements.txt
   ```
5. **Запуск.** Справа вверху выберите конфигурацию **«Запуск приложения»**
   и нажмите зелёный ▶ (⌃R). Браузер откроется сам на
   <http://127.0.0.1:8000>. Остановка — красный квадрат (⌘F2).
6. **Тесты.** Конфигурация **«Тесты»** → ▶.

Конфигурации запуска лежат в `.idea/runConfigurations/` и подхватываются
автоматически. Если их не видно в списке — откройте `run.py` и нажмите ▶
рядом с `if __name__ == "__main__":`.

**Частые проблемы**

| Сообщение | Что делать |
|---|---|
| `Не установлена зависимость «flask»` | шаг 4: `pip install -r requirements.txt` в терминале PyCharm |
| `Порт 8000 занят` | приложение уже запущено — остановите старый запуск (⌘F2) или добавьте `--port 8001` в *Edit Configurations… → Parameters* |
| `No Python interpreter configured` | шаг 3 |
| Браузер не открылся | откройте вручную <http://127.0.0.1:8000> (ссылка кликабельна в консоли PyCharm) |

Порт по умолчанию — 8000: на macOS 12+ порт 5000 занят службой AirPlay Receiver.

## Запуск из терминала

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py                        # откроется http://127.0.0.1:8000
python -m pytest                     # тесты
```

## Структура

```
lj_md/
  core/                  # MODEL — физика, ничего не знает об интерфейсе
    potential.py         #   потенциал LJ (обрезка + сдвиг), сила
    system.py            #   частицы, ячейка, PBC/стенки, силы, T, KE
    integrator.py        #   velocity Verlet
    thermostat.py        #   Берендсен, rescale
    observables.py       #   давление (вириал), g(r)
    simulation.py        #   фасад: параметры, инициализация, шаги, история
  viewmodel/             # VIEWMODEL — состояние экрана и команды
    observable.py        #   ObservableProperty, Command (аналог INotifyPropertyChanged)
    simulation_vm.py     #   SimulationViewModel: валидация, команды, данные для графиков
  view/                  # VIEW — веб-интерфейс
    app.py               #   Flask: тонкие маршруты к ViewModel
    templates/index.html #   разметка с data-bind / data-command
    static/app.js        #   привязка DOM ↔ состояние ViewModel
    static/scene.js      #   отрисовка атомов (2D/3D)
    static/charts.js     #   графики на canvas
tests/
  test_core.py           # законы сохранения, силы, границы, термостаты
  test_verification.py   # эталонные случаи с аналитическим ответом
  test_viewmodel.py      # команды, валидация, контракт state(), экспорт
  test_web.py            # HTTP-маршруты
docs/                    # архитектура, API, верификация, роли, теория, аудит
.github/                 # CI (тесты на 3 ОС) и шаблон pull request
run.py                   # точка входа
```

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — как устроен MVVM в проекте и почему так;
- [docs/API.md](docs/API.md) — HTTP API: маршруты, формат `state()`, ошибки, экспорт;
- [docs/THEORY.md](docs/THEORY.md) — физическая модель и численные методы;
- [docs/VERIFICATION.md](docs/VERIFICATION.md) — как проверяется правильность расчёта;
- [docs/ROLES.md](docs/ROLES.md) — участники и зоны ответственности, порядок слияния;
- [docs/DESKTOP.md](docs/DESKTOP.md) — сборка в один исполняемый файл, чтобы отправить приложение без установки Python;
- [CONTRIBUTING.md](CONTRIBUTING.md) — ветки, pull request, Definition of Done;
- [docs/AUDIT.md](docs/AUDIT.md) — самоаудит по требованиям курса и задачи до защиты.
