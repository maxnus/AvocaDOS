from abc import abstractmethod, ABC

from sc2bot.core.system import System


class BuildOrder(System, ABC):

    @abstractmethod
    def load(self) -> None:
        pass
