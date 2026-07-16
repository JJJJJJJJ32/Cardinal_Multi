"""
modules/cardinal_bridge — мост между Cardinal и Cardinal_Multi.

Обеспечивает интеграцию без изменения кода Cardinal.
"""

from modules.cardinal_bridge.hooks import install_hooks, remove_hooks, generate_plugin_file
from modules.cardinal_bridge.compatibility import (
    check_all_plugins,
    log_compatibility_report,
    get_incompatible_plugins,
    PluginCompatInfo,
)

__all__ = [
    "install_hooks",
    "remove_hooks",
    "generate_plugin_file",
    "check_all_plugins",
    "log_compatibility_report",
    "get_incompatible_plugins",
    "PluginCompatInfo",
]