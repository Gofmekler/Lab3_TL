# Верификация модели

Как мы проверяем, что программа считает физику правильно. Все проверки
автоматические (`python -m pytest`) и запускаются в CI на Linux, macOS и
Windows при каждом push и PR (`.github/workflows/tests.yml`).

Проверки двух видов:
- **эталонные случаи** — результат сравнивается с аналитическим ответом
  с заданной точностью (`tests/test_verification.py`);
- **законы сохранения и предельные случаи** — свойства, которые должны
  выполняться для любой корректной MD-программы (`tests/test_core.py`).

## Эталонные случаи (аналитический ответ)

| # | Случай | Эталон | Допуск | Тест |
|---|---|---|---|---|
| 1 | Пара атомов, покой на r<sub>min</sub> | E<sub>pot</sub> = −ε, F = 0 | 1e-10 | `test_two_atom_energy_at_rest_in_minimum_is_minus_epsilon` |
| 2 | Малые колебания пары около r<sub>min</sub> | T = 2π√(μ/U″(r<sub>min</sub>)), U″ = 72·2<sup>−1/3</sup> ≈ 57.15, μ = ½ → **T ≈ 0.5877 τ** | 1 % | `test_two_atom_oscillation_period_matches_harmonic_limit` |
| 3 | Свободная частица, упругая стенка: x₀ = 1, v = 1, L = 5, t = 6 | x = 3, v = −1, E<sub>kin</sub> = ½ | 1e-9 | `test_free_particle_reflects_from_wall_exactly` |
| 4 | Свободная частица, PBC: (4; 1), v = (1; 0.5), L = 5, t = 3 | (2; 2.5) | 1e-9 | `test_free_particle_wraps_around_with_pbc` |
| 5 | Порядок схемы Верле | ошибка энергии ∝ dt²: при dt → dt/2 уменьшается в 4 раза | 3…5 раз | `test_verlet_energy_error_is_second_order_in_dt` |
| 6 | Минимум потенциала | r<sub>min</sub> = 2<sup>1/6</sup>σ ≈ 1.1225, U(r<sub>min</sub>) = −ε | 1e-3 | `test_potential_minimum_at_r_min` |
| 7 | Обрезка потенциала | U(r ≥ r<sub>c</sub>) = 0, U непрерывна в r<sub>c</sub> | 1e-4 | `test_potential_is_zero_at_and_beyond_cutoff` |
| 8 | Идеальный газ (ρ → 0) | P = ρT | 5 % | `test_ideal_gas_limit_pressure` |
| 9 | Идеальный газ | g(r) → 1 | ±0.05 | `test_rdf_tends_to_one_for_ideal_gas` |

## Законы сохранения и свойства схемы

| Свойство | Тест |
|---|---|
| F = −∇U для пары (численная производная) | `test_force_is_minus_gradient_of_energy` |
| F = −∇E<sub>pot</sub> для всей системы | `test_forces_match_numerical_gradient_of_total_energy` |
| Третий закон Ньютона: ΣF = 0 | `test_newtons_third_law_total_force_zero` |
| Сохранение энергии в NVE (2D и 3D), нет дрейфа | `test_energy_conservation_nve` |
| Сохранение импульса при PBC | `test_momentum_conserved_with_pbc` |
| Обратимость Верле во времени | `test_verlet_is_time_reversible` |
| Ближайший образ при PBC | `test_minimum_image_convention` |
| Стенки: частицы внутри, скорость отражается | `test_reflective_walls_keep_particles_inside_and_flip_velocity` |
| Начальные условия: точная T₀, нулевой импульс | `test_initial_velocities_have_exact_temperature_and_zero_momentum` |
| Термостаты приводят T к целевой | `test_berendsen_thermostat_drives_temperature_to_target`, `test_rescale_thermostat_sets_exact_temperature` |
| Жидкость: первый пик g(r) около σ | `test_dense_liquid_rdf_has_first_peak_near_sigma` |

## Отказ при некорректных данных

Программа не считает заведомо неверную задачу, а объясняет, что не так.

| Ввод | Результат | Тест |
|---|---|---|
| ε ≤ 0 | `ValueError` в ядре | `test_invalid_potential_parameters` |
| r<sub>c</sub> > L/2 при PBC | ошибка у поля `cutoff` с подсказкой | `test_parameters_validation_cutoff_vs_box` |
| Нечисловой ввод, дробное N | ошибки по полям, симуляция не сбрасывается | `test_invalid_input_produces_field_errors_and_keeps_simulation` |
| Десятичная запятая `0,002` | принимается | `test_decimal_comma_is_accepted` |
| «Взрыв» системы (NaN, слишком большой dt) | статус-ошибка, а не падение сервера | `test_blowup_is_reported_not_raised` |
| Неизвестная команда / пресет | HTTP 404 с текстом ошибки | `test_unknown_command_and_preset` |
| Тело запроса не JSON | игнорируется, ответ 200 | `test_bad_json_body_is_handled` |

## Воспроизводимость

Одинаковые параметры и `seed` дают одинаковую траекторию. JSON-отчёт
(`/api/export.json`) содержит все параметры, и тест
`test_export_json_is_reproducible_report` проверяет, что по ним получается
тот же результат.

## Как проверить вручную в интерфейсе

1. **Сохранение энергии.** Пресет «Газ» или параметры по умолчанию, термостат
   «Нет (NVE)» → Старт. Плитка «Дрейф E» остаётся в пределах долей процента;
   при dt = 0.02 дрейф заметно растёт.
2. **Идеальный газ.** ρ = 0.01, T₀ = 2 → давление ≈ ρT = 0.02.
3. **g(r).** Пресеты «Газ», «Жидкость», «Кристалл» дают три характерные
   формы g(r) (см. [THEORY.md](THEORY.md#наблюдаемые)).
