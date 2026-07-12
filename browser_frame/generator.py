from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from PIL import Image

from .config import ensure_output_dir, load_config, load_settings, validate_template_path
from .image_utils import composite_template, load_image, validate_region
from .models import BatchItem, DeviceKind, Region, Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BatchResult:
    success: int
    failed: int
    errors: list[str]


class BatchGenerator:
    def __init__(self, template_path: Path, config_path: Path, settings_path: Path, output_dir: Path) -> None:
        self.template_path = template_path
        self.config_path = config_path
        self.settings_path = settings_path
        self.output_dir = output_dir

    def _load_template(self) -> Image.Image:
        validate_template_path(self.template_path)
        return load_image(self.template_path)

    def _load_regions(self, settings: Settings, template_size: tuple[int, int]) -> tuple[Region, Region]:
        if settings.viewport is None:
            raise ValueError("Viewport has not been selected")
        if settings.address_bar is None:
            raise ValueError("Address bar has not been selected")
        validate_region(settings.viewport, template_size, "Viewport")
        validate_region(settings.address_bar, template_size, "Address bar")
        return settings.viewport, settings.address_bar

    def generate(self) -> BatchResult:
        logger.info("Loading template: %s", self.template_path)
        template = self._load_template()
        settings = load_settings(self.settings_path)
        device_profile = settings.profile(settings.active_device)
        if not device_profile.regions_confirmed:
            raise ValueError("Regions have not been confirmed. Run: python main.py --edit")
        viewport, address_bar = self._load_regions(settings, template.size)
        items = load_config(self.config_path, cast(DeviceKind, settings.active_device))
        output_dir = ensure_output_dir(self.output_dir)
        success = 0
        failed = 0
        errors: list[str] = []
        for index, item in enumerate(items, start=1):
            logger.info("Processing %s/%s: %s", index, len(items), item.output)
            try:
                result = self._process_item(template, viewport, address_bar, settings, item, output_dir)
                output_path = output_dir / item.output
                output_path.parent.mkdir(parents=True, exist_ok=True)
                result.save(output_path, format="PNG")
                logger.info("Saved: %s", output_path)
                success += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                message = f"{item.output}: {exc}"
                errors.append(message)
                logger.error("%s", message)
        logger.info("Completed.")
        logger.info("Success: %s", success)
        logger.info("Failed: %s", failed)
        return BatchResult(success=success, failed=failed, errors=errors)

    def _process_item(
        self,
        template: Image.Image,
        viewport: Region,
        address_bar: Region,
        settings: Settings,
        item: BatchItem,
        output_dir: Path,
    ) -> Image.Image:
        if not item.screenshot.exists():
            raise FileNotFoundError(f"Screenshot not found: {item.screenshot}")
        screenshot = load_image(item.screenshot)
        if item.fit not in {"cover", "contain"}:
            raise ValueError(f"Format fit is not valid: {item.fit}")
        website_title = item.title if item.title is not None else settings.website_title
        return composite_template(
            template=template,
            viewport=viewport,
            address_bar=address_bar,
            screenshot=screenshot,
            url=item.url,
            website_title=website_title,
            text_settings=settings.url_text,
            contain_background=settings.contain_background,
            fit_mode=item.fit,
        )
