from typing import TYPE_CHECKING

from avocados.core.botobject import BotObject

if TYPE_CHECKING:
    from avocados.core.avocados import AvocaDOS


class UnitTag(BotObject):
    tag: int

    def __init__(self, bot: 'AvocaDOS', tag: int) -> None:
        super().__init__(bot)
        self.tag = tag

    def is_alive(self) -> bool:
        return self.tag in self.api.alive_tags
