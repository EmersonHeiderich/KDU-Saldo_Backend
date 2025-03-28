# src/config/__init__.py
# Makes 'config' a package. Exports relevant items.

from .settings import config, Config, load_config

__all__ = ["config", "Config", "load_config"]