from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from .models import BatchItem, DeviceKind, Settings


class ConfigError(ValueError):
    pass


DEFAULT_CONFIG_PATH = Path("config.json")
DEFAULT_SETTINGS_PATH = Path("settings.json")
DEFAULT_TEMPLATE_PATH = Path("template.png")


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON: {path}") from exc


def load_settings(path: Path = DEFAULT_SETTINGS_PATH) -> Settings:
    if not path.exists():
        return Settings()
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ConfigError("settings.json must contain a JSON object")
    return Settings.from_dict(data)


def save_settings(settings: Settings, path: Path = DEFAULT_SETTINGS_PATH) -> None:
    path.write_text(json.dumps(settings.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_config(path: Path = DEFAULT_CONFIG_PATH, device: DeviceKind | None = None) -> list[BatchItem]:
    data = _read_json(path)
    if isinstance(data, list):
        base_dir = path.parent.resolve()
        return [BatchItem.from_dict(item, base_dir=base_dir) for item in data]
    if not isinstance(data, dict):
        raise ConfigError("config.json must contain a JSON array or an object with device keys")
    if device is None:
        active_device = str(data.get("active_device", "desktop"))
        if active_device not in {"desktop", "mobile"}:
            active_device = "desktop"
        device = cast(DeviceKind, active_device)
    device_items = data.get(device)
    if not isinstance(device_items, list):
        raise ConfigError(f"config.json must contain a '{device}' array")
    base_dir = path.parent.resolve()
    return [BatchItem.from_dict(item, base_dir=base_dir) for item in device_items]


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_template_path(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path
