from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

FitMode = Literal["cover", "contain"]
RegionKind = Literal["viewport", "address_bar"]
DeviceKind = Literal["desktop", "mobile"]


@dataclass(slots=True)
class Point:
    x: int
    y: int


@dataclass(slots=True)
class Region:
    x: int
    y: int
    width: int
    height: int

    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.width, self.height

    def clamp_within(self, max_width: int, max_height: int) -> "Region":
        width = min(self.width, max_width)
        height = min(self.height, max_height)
        x = min(max(self.x, 0), max_width - width)
        y = min(max(self.y, 0), max_height - height)
        return Region(x=x, y=y, width=width, height=height)

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Region":
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            width=int(data["width"]),
            height=int(data["height"]),
        )


@dataclass(slots=True)
class TextSettings:
    font_size: int = 16
    text_color: str = "#202124"
    padding_left: int = 20
    background_color: str = "#FFFFFF"

    def to_dict(self) -> dict[str, Any]:
        return {
            "font_size": self.font_size,
            "text_color": self.text_color,
            "padding_left": self.padding_left,
            "background_color": self.background_color,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TextSettings":
        data = data or {}
        return cls(
            font_size=int(data.get("font_size", 16)),
            text_color=str(data.get("text_color", "#202124")),
            padding_left=int(data.get("padding_left", 20)),
            background_color=str(data.get("background_color", "#FFFFFF")),
        )


@dataclass(slots=True)
class DeviceProfile:
    template_path: str | None = None
    viewport: Region | None = None
    address_bar: Region | None = None
    regions_confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_path": self.template_path,
            "viewport": None if self.viewport is None else self.viewport.to_dict(),
            "address_bar": None if self.address_bar is None else self.address_bar.to_dict(),
            "regions_confirmed": self.regions_confirmed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DeviceProfile":
        data = data or {}
        viewport = data.get("viewport")
        address_bar = data.get("address_bar")
        return cls(
            template_path=data.get("template_path"),
            viewport=Region.from_dict(viewport) if viewport else None,
            address_bar=Region.from_dict(address_bar) if address_bar else None,
            regions_confirmed=bool(data.get("regions_confirmed", False)),
        )


@dataclass(slots=True)
class Settings:
    active_device: DeviceKind = "desktop"
    regions_confirmed: bool = False
    profiles: dict[str, DeviceProfile] = field(
        default_factory=lambda: {
            "desktop": DeviceProfile(),
            "mobile": DeviceProfile(),
        }
    )
    url_text: TextSettings = field(default_factory=TextSettings)
    contain_background: str = "#FFFFFF"

    def profile(self, device: DeviceKind | None = None) -> DeviceProfile:
        device = device or self.active_device
        return self.profiles.setdefault(device, DeviceProfile())

    @property
    def viewport(self) -> Region | None:
        return self.profile().viewport

    @viewport.setter
    def viewport(self, value: Region | None) -> None:
        self.profile().viewport = value

    @property
    def address_bar(self) -> Region | None:
        return self.profile().address_bar

    @address_bar.setter
    def address_bar(self, value: Region | None) -> None:
        self.profile().address_bar = value

    @property
    def template_path(self) -> str | None:
        return self.profile().template_path

    @template_path.setter
    def template_path(self, value: str | None) -> None:
        self.profile().template_path = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_device": self.active_device,
            "regions_confirmed": self.regions_confirmed,
            "profiles": {device: profile.to_dict() for device, profile in self.profiles.items()},
            "url_text": self.url_text.to_dict(),
            "contain_background": self.contain_background,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        profiles_data = data.get("profiles") or {}
        active_device = str(data.get("active_device", "desktop"))
        if active_device not in {"desktop", "mobile"}:
            active_device = "desktop"
        profiles = {
            "desktop": DeviceProfile.from_dict(profiles_data.get("desktop")),
            "mobile": DeviceProfile.from_dict(profiles_data.get("mobile")),
        }
        return cls(
            active_device=cast(DeviceKind, active_device),
            regions_confirmed=bool(data.get("regions_confirmed", False)),
            profiles=profiles,
            url_text=TextSettings.from_dict(data.get("url_text")),
            contain_background=str(data.get("contain_background", "#FFFFFF")),
        )


@dataclass(slots=True)
class TemplateInfo:
    path: Path
    width: int
    height: int


@dataclass(slots=True)
class BatchItem:
    screenshot: Path
    url: str
    output: str
    fit: FitMode = "cover"

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_dir: Path) -> "BatchItem":
        fit = str(data.get("fit", "cover"))
        if fit not in {"cover", "contain"}:
            raise ValueError(f"Invalid fit mode: {fit}")
        return cls(
            screenshot=(base_dir / str(data["screenshot"])).resolve(),
            url=str(data["url"]),
            output=str(data["output"]),
            fit=cast(FitMode, fit),
        )
