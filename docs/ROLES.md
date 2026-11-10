# Роли и зоны ответственности

Проект рассчитан на команду из трёх человек; слои MVVM разделены так,
чтобы каждый мог работать независимо, договорившись только об интерфейсах.
Правила веток, review и Definition of Done — в [CONTRIBUTING.md](../CONTRIBUTING.md),
автоматическое назначение ревьюеров — `.github/CODEOWNERS`.

## Тимлид (интеграция)

- архитектура и структура репозитория, точка входа `run.py`, конфигурации PyCharm;
- контракты между слоями: `SimulationParameters`, `Snapshot`, `state()`,
  HTTP API ([API.md](API.md)), формат экспорта;
- CI (`.github/workflows/ci.yml`), документация, лицензия;
- десктопная сборка (`desktop.py`, `build_desktop.py`, `.github/workflows/desktop.yml`);
- review PR обеих ролей, финальный PR `development → main`.

## Core (Model + верификация)

- `lj_md/core/` целиком: потенциал, силы, граничные условия, интегратор,
  термостаты, наблюдаемые (T, P, g(r)), единицы;
- физическая валидация параметров (`SimulationParameters.validate`),
  обнаружение неустойчивости и откат;
- верификация: `tests/test_core.py`, `tests/test_verification.py`,
  `verification/` и отчёт [VERIFICATION.md](VERIFICATION.md).

## UI (ViewModel + View + экспорт изображений)

UI отвечает за весь путь «данные ядра → экран»: решает, какие данные нужны
интерфейсу и в каком виде, и сам их готовит.

- ViewModel (`lj_md/viewmodel/`): фазы и команды, разбор и валидация ввода,
  схема формы, пресеты, подготовка данных для графиков, экспорт/импорт CSV/JSON;
- `lj_md/view/`: Flask-маршруты, HTML, CSS, JS;
- отрисовка ячейки (2D, 3D с вращением), графики с подписями осей и единицами,
  форма параметров по схеме, PNG-экспорт, импорт файла эксперимента;
- обработка ошибок связи и кодов ответа, адаптивная вёрстка, тёмная тема;
- `tests/test_viewmodel.py`, `tests/test_web.py`, `tests/e2e/`, скриншоты (`scripts/make_screenshots.py`).

## Контракты (о чём договариваются заранее)

| Между | Контракт | Где закреплён |
|---|---|---|
| Core ↔ UI (ViewModel) | `Simulation`, `SimulationParameters`, `Snapshot`, `SimulationError` | `tests/test_core.py`, `tests/test_viewmodel.py` |
| ViewModel ↔ View (внутри UI) | `state()`, имена команд, `schema()`, коды ошибок | `docs/API.md`, `tests/test_web.py` |
| Экспорт | CSV/JSON, `schema_version` | `docs/API.md`, `tests/test_viewmodel.py` |

## Порядок работы

1. Тимлид — каркас, контракты, документация, CI.
2. Core и UI работают параллельно в `feature/*`: UI может начинать с
   зафиксированного формата `state()`.
3. PR в `development` с review участника другой роли; тимлид интегрирует.
4. Перед защитой — чек-лист в CONTRIBUTING.md и финальный PR в `main`.
