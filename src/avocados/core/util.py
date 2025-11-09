from collections.abc import Callable
from typing import Any, Optional


class WithCallback[T]:
    value: T
    callback: Optional[Callable[[...], Any]]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def __init__(self, value: T, callback: Optional[Callable[[...], Any]], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.value = value
        self.callback = callback
        self.args = args
        self.kwargs = kwargs

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.value})"

    def peak(self) -> T:
        return self.value

    def access(self) -> T:
        if self.callback is not None:
            self.callback(*self.args, **self.kwargs)
        return self.value
