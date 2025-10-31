from typing import Optional

from .buildorder import BuildOrder
from .massmarine import MassMarine
from .proxymarine import ProxyMarine
from .proxyreaper import ProxyReaper


build_orders: dict[str, type[BuildOrder]] = {
    'massmarine': MassMarine,
    'proxyreaper': ProxyReaper,
    'proxymarine': ProxyMarine,
}


def get_build_order(name: Optional[str] = None) -> type[BuildOrder]:
    if name is None:
        name = 'proxymarine'
    return build_orders[name]
