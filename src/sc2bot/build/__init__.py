from typing import Optional

from .buildorder import BuildOrder

from .proxyreaper import ProxyReaper


def get_build_order(name: Optional[str] = None) -> type[BuildOrder]:
    if name is None:
        name = 'proxyreaper'

    if name == 'proxyreaper':
        return ProxyReaper

    raise ValueError(f'Unknown build order {name}')
