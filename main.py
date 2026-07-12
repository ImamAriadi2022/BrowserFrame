from __future__ import annotations

import argparse
import logging
from pathlib import Path

from browser_frame.config import DEFAULT_CONFIG_PATH, DEFAULT_SETTINGS_PATH, DEFAULT_TEMPLATE_PATH, load_config, load_settings, save_settings
from browser_frame.generator import BatchGenerator
from browser_frame.preview import create_preview
from browser_frame.region_editor import run_editor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="BrowserFrame")
    parser.add_argument("--edit", action="store_true", help="Open the Region Editor")
    parser.add_argument("--preview", action="store_true", help="Preview the current settings")
    parser.add_argument("--generate", action="store_true", help="Run batch generation")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Batch config JSON")
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS_PATH, help="Settings JSON")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE_PATH, help="Template PNG")
    parser.add_argument("--device", choices=["desktop", "mobile"], help="Select the active device profile")
    parser.add_argument("--output", type=Path, default=Path("output"), help="Output folder")
    return parser


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def resolve_template_path(args: argparse.Namespace) -> Path | None:
    if args.template != DEFAULT_TEMPLATE_PATH:
        return args.template
    if args.device is not None:
        device_template = Path(f"template.{args.device}.png")
        if device_template.exists():
            return device_template
    settings = load_settings(args.settings)
    template_path = settings.profile(settings.active_device).template_path
    if template_path:
        candidate = Path(template_path)
        if candidate.exists():
            return candidate
    if args.template.exists():
        return args.template
    return None


def main() -> None:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    resolved_template = resolve_template_path(args)
    editor_template = None if args.device is None and args.template == DEFAULT_TEMPLATE_PATH else resolved_template
    if not (args.edit or args.preview or args.generate):
        run_editor(template_path=editor_template, device=args.device)
        return
    if args.edit:
        run_editor(template_path=editor_template, device=args.device)
        return
    if args.preview:
        settings = load_settings(args.settings)
        device = args.device or settings.active_device
        settings.active_device = device
        if settings.viewport is None or settings.address_bar is None:
            raise SystemExit("Viewport and address bar must be configured first.")
        template_path = resolved_template
        if template_path is None or not template_path.exists():
            raise SystemExit("Template not found for the selected device.")
        batch_items = load_config(args.config, device)
        if not batch_items:
            raise SystemExit("config.json does not contain any batch items")
        first_item = batch_items[0]
        if not first_item.screenshot.exists():
            raise SystemExit(f"Screenshot not found: {first_item.screenshot}")
        preview = create_preview(template_path, first_item.screenshot, first_item.url, first_item.fit)
        args.output.mkdir(parents=True, exist_ok=True)
        preview.save(args.output / "preview.png")
        logging.info("Preview saved: %s", args.output / "preview.png")
        return
    if args.generate:
        try:
            if args.device is not None:
                settings = load_settings(args.settings)
                settings.active_device = args.device
                save_settings(settings, args.settings)
            if resolved_template is None or not resolved_template.exists():
                raise SystemExit("Template not found for the selected device.")
            generator = BatchGenerator(resolved_template, args.config, args.settings, args.output)
            generator.generate()
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        return


if __name__ == "__main__":
    main()
