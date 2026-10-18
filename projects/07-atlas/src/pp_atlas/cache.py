"""Bounded result LRU. Keys include all authorization, query and ranking inputs."""

from collections import OrderedDict
from typing import Generic, TypeVar

T = TypeVar("T")


class LRU(Generic[T]):
    def __init__(self, capacity: int = 128) -> None:
        self.capacity = capacity
        self._items: OrderedDict[tuple[object, ...], T] = OrderedDict()

    def get(self, key: tuple[object, ...]) -> T | None:
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
        return value

    def put(self, key: tuple[object, ...], value: T) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)
