"""
modules/cardinal_bridge/compatibility.py
─────────────────────────────────────────
Проверка совместимости Cardinal_Multi с известными плагинами Cardinal.

Проверяемые плагины:
    - adv_profile_stat    (статистика профиля)
    - copy_lots_plugin    (копирование лотов)
    - review_chat_reply   (ответы на отзывы)

Правило: если плагин не работает → логируем, НЕ останавливаем Cardinal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from cardinal import Cardinal  # type: ignore[import]


# ─── Структуры данных ─────────────────────────────────────────────────────────

@dataclass
class PluginCompatInfo:
    """Информация о совместимости плагина."""

    name: str
    """Отображаемое имя плагина."""

    filename: str
    """Имя файла плагина (без пути)."""

    is_present: bool = False
    """Плагин найден в папке plugins/."""

    is_compatible: bool = True
    """Плагин совместим с Cardinal_Multi."""

    warning: str | None = None
    """Предупреждение если плагин несовместим (None = совместим)."""

    notes: list[str] = field(default_factory=list)
    """Дополнительные примечания."""


# ─── Известные плагины и правила совместимости ────────────────────────────────

KNOWN_PLUGINS: list[dict] = [
    {
        "name":     "adv_profile_stat",
        "filename": "adv_profile_stat.py",
        "checks":   [],  # совместим без ограничений
        "notes":    ["Работает с основным аккаунтом (account_id=1)."],
    },
    {
        "name":     "copy_lots_plugin",
        "filename": "copy_lots_plugin.py",
        "checks":   [],
        "notes":    [
            "Копирует лоты только основного аккаунта.",
            "Для копирования между аккаунтами используй модуль multi.",
        ],
    },
    {
        "name":     "review_chat_reply",
        "filename": "review_chat_reply.py",
        "checks":   [],
        "notes":    ["Отвечает на отзывы только основного аккаунта."],
    },
]

PLUGINS_DIR = Path("plugins")


# ─── Проверка совместимости ────────────────────────────────────────────────────

def check_all_plugins(cardinal: "Cardinal | None" = None) -> list[PluginCompatInfo]:
    """
    Проверяет совместимость всех известных плагинов.

    :param cardinal: экземпляр Cardinal (опционально).
                     Если передан — дополнительно проверяет загруженные плагины.
    :return: список PluginCompatInfo для каждого известного плагина.
    """
    results: list[PluginCompatInfo] = []

    for plugin_def in KNOWN_PLUGINS:
        info = _check_single_plugin(plugin_def, cardinal)
        results.append(info)

        if info.is_present:
            if info.is_compatible:
                logger.info(
                    "[Compat] Плагин '{}' — ✅ совместим{}",
                    info.name,
                    f" ({', '.join(info.notes)})" if info.notes else "",
                )
            else:
                logger.warning(
                    "[Compat] Плагин '{}' — ⚠️ возможны проблемы: {}",
                    info.name,
                    info.warning,
                )
        else:
            logger.debug("[Compat] Плагин '{}' — не установлен (пропуск).", info.name)

    return results


def _check_single_plugin(
    plugin_def: dict,
    cardinal: "Cardinal | None",
) -> PluginCompatInfo:
    """
    Проверяет один плагин.

    :param plugin_def: словарь с описанием плагина из KNOWN_PLUGINS.
    :param cardinal: экземпляр Cardinal (опционально).
    :return: PluginCompatInfo с результатами проверки.
    """
    filename = plugin_def["filename"]
    plugin_path = PLUGINS_DIR / filename

    info = PluginCompatInfo(
        name=plugin_def["name"],
        filename=filename,
        is_present=plugin_path.exists(),
        notes=plugin_def.get("notes", []),
    )

    if not info.is_present:
        return info

    # Дополнительные проверки через загруженные плагины Cardinal
    if cardinal is not None and hasattr(cardinal, "plugins"):
        info = _check_cardinal_loaded(info, cardinal)

    # Кастомные проверки из plugin_def
    for check_func in plugin_def.get("checks", []):
        try:
            result = check_func(cardinal, info)
            if result is not None:
                info = result
        except Exception as exc:
            logger.debug(
                "[Compat] Ошибка при проверке {}: {}", plugin_def["name"], exc
            )

    return info


def _check_cardinal_loaded(
    info: PluginCompatInfo,
    cardinal: "Cardinal",
) -> PluginCompatInfo:
    """
    Проверяет, загружен ли плагин в Cardinal, и анализирует его состояние.

    :param info: текущий PluginCompatInfo.
    :param cardinal: экземпляр Cardinal.
    :return: обновлённый PluginCompatInfo.
    """
    # Ищем плагин по имени файла в cardinal.plugins
    plugin_uuid = None
    for uuid, plugin_data in cardinal.plugins.items():
        if hasattr(plugin_data, "path") and plugin_data.path:
            if Path(plugin_data.path).name == info.filename:
                plugin_uuid = uuid
                break

    if plugin_uuid is None:
        info.notes.append("Плагин найден в папке, но не загружен Cardinal.")
        return info

    plugin_data = cardinal.plugins[plugin_uuid]

    # Проверяем enabled статус
    if hasattr(plugin_data, "enabled") and not plugin_data.enabled:
        info.notes.append("Плагин отключён в настройках Cardinal.")

    return info


def log_compatibility_report(results: list[PluginCompatInfo]) -> None:
    """
    Выводит итоговый отчёт о совместимости в лог.

    :param results: список результатов check_all_plugins().
    """
    installed = [r for r in results if r.is_present]
    if not installed:
        logger.info("[Compat] Известные плагины не установлены.")
        return

    logger.info("[Compat] Отчёт совместимости плагинов:")
    for info in installed:
        status = "✅" if info.is_compatible else "⚠️"
        msg = f"  {status} {info.name}"
        if info.warning:
            msg += f" — {info.warning}"
        if info.notes:
            msg += f"\n     Примечания: {'; '.join(info.notes)}"
        logger.info(msg)


def get_incompatible_plugins(results: list[PluginCompatInfo]) -> list[PluginCompatInfo]:
    """
    Возвращает список несовместимых плагинов.

    :param results: список результатов check_all_plugins().
    :return: только несовместимые плагины.
    """
    return [r for r in results if r.is_present and not r.is_compatible]