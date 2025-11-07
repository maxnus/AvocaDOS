from collections.abc import Callable
from typing import Any


class CallbackOnAccess[T]:
    value: T
    callback: Callable[[...], Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def __init__(self, value: T, callback: Callable[[...], Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.value = value
        self.callback = callback
        self.args = args
        self.kwargs = kwargs

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.value})"

    def access(self) -> T:
        self.callback(*self.args, **self.kwargs)
        return self.value
