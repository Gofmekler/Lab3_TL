"""Мини-инфраструктура MVVM: наблюдаемые свойства и команды.

Аналог INotifyPropertyChanged / RelayCommand из WPF, но на чистом Python.
"""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")
Listener = Callable[[str, Any], None]


class Observable:
    """Базовый класс: умеет оповещать подписчиков об изменении свойств."""

    def __init__(self) -> None:
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Подписаться на изменения. Возвращает функцию отписки."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def notify(self, name: str, value: Any) -> None:
        for listener in list(self._listeners):
            listener(name, value)


class ObservableProperty(Generic[T]):
    """Дескриптор: при присваивании нового значения вызывает ``notify``."""

    def __init__(self, default: T) -> None:
        self.default = default

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        self.attr = f"_{name}"

    def __get__(self, obj: Observable | None, objtype: type | None = None) -> T:
        if obj is None:
            return self  # type: ignore[return-value]
        return getattr(obj, self.attr, self.default)

    def __set__(self, obj: Observable, value: T) -> None:
        if getattr(obj, self.attr, self.default) != value:
            setattr(obj, self.attr, value)
            obj.notify(self.name, value)


class Command:
    """Команда View → ViewModel с проверкой доступности (``can_execute``)."""

    def __init__(self, execute: Callable[..., Any],
                 can_execute: Callable[[], bool] = lambda: True) -> None:
        self._execute = execute
        self._can_execute = can_execute

    @property
    def can_execute(self) -> bool:
        return bool(self._can_execute())

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if not self.can_execute:
            return None
        return self._execute(*args, **kwargs)
