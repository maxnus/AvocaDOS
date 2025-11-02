from typing import Optional, Any, Generic, TypeVar


class Mutable[T]:
    value: Optional[T]

    def __init__(self, value: Optional[T] = None) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"Mutable({self.value})"

    def has_value(self) -> bool:
        return self.value is not None


class UncertainMeta(type):
    def __instancecheck__(cls, instance: Any) -> bool:
        # Allow isinstance(x, T) to pass if x is Uncertain[T]
        if isinstance(instance, Uncertain):
            return isinstance(instance.value, cls)
        return super().__instancecheck__(instance)


T = TypeVar('T')
class Uncertain(Generic[T], metaclass=UncertainMeta):
    value: T
    probability: float

    def __init__(self, value: T, probability: float) -> None:
        self.value = value
        self.probability = probability

    def make_certain(self, value: Optional[T] = None) -> None:
        if value is not None:
            self.value = value
        self.probability = 1

    @property
    def is_certain(self) -> bool:
        return self.probability == 1

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.value, attr)

    def __setattr__(self, attr: str, value: Any) -> None:
        if attr in {'value', 'probability'}:
            object.__setattr__(self, attr, value)
        setattr(self.value, attr, value)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.value(*args, **kwargs)

    def __getitem__(self, item: Any) -> Any:
        return self.value[item]

    def __setitem__(self, item: Any, value: Any) -> Any:
        self.value[item] = value

    def __eq__(self, other: Any) -> bool:
        return self.value == other

    def __hash__(self) -> int:
        return self.value.__hash__()

# class Probabilities[T]:
#     elements: list[tuple[T, float]]
#
#     def __init__(self, elements: list[tuple[T, float]] = None) -> None:
#         self.elements = elements or []
#         self._sort()
#
#     def __getitem__(self, index: int) -> T:
#         return self.elements[0][0]
#
#     def add(self, item: T, probability: float) -> None:
#         self.elements.append((item, probability))
#         self._sort()
#
#     def most_likely(self) -> T:
#         return self.elements[0]
#
#     def _sort(self) -> None:
#         self.elements.sort(key=lambda x: x[1], reverse=True)
