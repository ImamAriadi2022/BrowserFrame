from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, BOTTOM, LEFT, RIGHT, X, Y, Canvas, Frame, StringVar, Tk, Toplevel, filedialog, messagebox, ttk
from typing import Literal

from PIL import Image, ImageTk

from .config import load_config, load_settings, save_settings, validate_template_path
from .image_utils import load_image, validate_region
from .generator import BatchGenerator
from .models import BatchItem, Region, Settings
from .preview import create_preview

logger = logging.getLogger(__name__)

RegionKind = Literal["viewport", "address_bar"]


@dataclass(slots=True)
class CanvasTransform:
    zoom: float = 1.0


class RegionEditorApp:
    def __init__(self, root: Tk, template_path: Path | None = None) -> None:
        self.root = root
        self.root.title("BrowserFrame Region Editor")
        self.root.geometry("1400x900")

        self.template_path = template_path
        self.template_image: Image.Image | None = None
        self.template_photo: ImageTk.PhotoImage | None = None
        self.transform = CanvasTransform()
        self.active_region: RegionKind = "viewport"
        self.drag_mode: str | None = None
        self.drag_origin_image: tuple[int, int] | None = None
        self.drag_origin_region: Region | None = None
        self.drag_handle: str | None = None
        self.settings = load_settings()

        self.x_var = StringVar(value="0")
        self.y_var = StringVar(value="0")
        self.w_var = StringVar(value="0")
        self.h_var = StringVar(value="0")
        self.zoom_var = StringVar(value="100%")
        self.template_info_var = StringVar(value="Template: none | Resolution: -")
        self.status_var = StringVar(value="Open a template to begin.")

        self._build_ui()
        self._load_persisted_template_path()
        self.root.bind("<KeyPress>", self.on_key_press)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        root_frame = Frame(self.root)
        root_frame.pack(fill=BOTH, expand=True)
        root_frame.rowconfigure(1, weight=1)
        root_frame.columnconfigure(0, weight=1)

        header = ttk.Frame(root_frame)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        ttk.Label(header, text="BrowserFrame Region Editor", font=("Segoe UI", 14, "bold")).pack(side=LEFT)
        ttk.Label(header, textvariable=self.template_info_var).pack(side=RIGHT)

        center = ttk.Frame(root_frame)
        center.grid(row=1, column=0, sticky="nsew")
        center.columnconfigure(0, weight=1)
        center.columnconfigure(1, weight=0)
        center.rowconfigure(0, weight=1)

        canvas_holder = ttk.Frame(center)
        canvas_holder.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=6)
        canvas_holder.rowconfigure(0, weight=1)
        canvas_holder.columnconfigure(0, weight=1)

        self.canvas = Canvas(canvas_holder, background="#262626", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.h_scroll = ttk.Scrollbar(canvas_holder, orient="horizontal", command=self.canvas.xview)
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        self.v_scroll = ttk.Scrollbar(canvas_holder, orient="vertical", command=self.canvas.yview)
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)

        sidebar = ttk.Frame(center, width=360)
        sidebar.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=6)
        sidebar.grid_propagate(False)

        region_box = ttk.LabelFrame(sidebar, text="Region Selection")
        region_box.pack(fill=X, padx=2, pady=6)
        ttk.Button(region_box, text="Select Viewport", command=lambda: self.set_active_region("viewport")).pack(fill=X, padx=8, pady=(8, 4))
        ttk.Button(region_box, text="Select Address Bar", command=lambda: self.set_active_region("address_bar")).pack(fill=X, padx=8, pady=(0, 8))

        coord_box = ttk.LabelFrame(sidebar, text="Fine Adjustment")
        coord_box.pack(fill=X, padx=2, pady=6)
        self._add_coord_row(coord_box, "X", self.x_var)
        self._add_coord_row(coord_box, "Y", self.y_var)
        self._add_coord_row(coord_box, "Width", self.w_var)
        self._add_coord_row(coord_box, "Height", self.h_var)
        button_row = ttk.Frame(coord_box)
        button_row.pack(fill=X, padx=8, pady=8)
        ttk.Button(button_row, text="Apply", command=self.apply_coordinates).pack(side=LEFT, expand=True, fill=X, padx=2)
        ttk.Button(button_row, text="Reset", command=self.reset_region).pack(side=LEFT, expand=True, fill=X, padx=2)
        ttk.Button(button_row, text="Clear Selection", command=self.clear_region).pack(side=LEFT, expand=True, fill=X, padx=2)

        zoom_box = ttk.LabelFrame(sidebar, text="Zoom")
        zoom_box.pack(fill=X, padx=2, pady=6)
        ttk.Label(zoom_box, textvariable=self.zoom_var).pack(padx=8, pady=(8, 4))
        zoom_row = ttk.Frame(zoom_box)
        zoom_row.pack(fill=X, padx=8, pady=(0, 8))
        ttk.Button(zoom_row, text="Zoom In", command=lambda: self.change_zoom(1.25)).pack(side=LEFT, expand=True, fill=X, padx=2)
        ttk.Button(zoom_row, text="Zoom Out", command=lambda: self.change_zoom(0.8)).pack(side=LEFT, expand=True, fill=X, padx=2)
        ttk.Button(zoom_row, text="Reset Zoom", command=self.reset_zoom).pack(side=LEFT, expand=True, fill=X, padx=2)
        ttk.Button(zoom_box, text="Fit to Window", command=self.fit_to_window).pack(fill=X, padx=8, pady=(0, 8))

        actions = ttk.LabelFrame(sidebar, text="Actions")
        actions.pack(fill=X, padx=2, pady=6)
        ttk.Button(actions, text="Open Template", command=self.open_template_dialog).pack(fill=X, padx=8, pady=(8, 4))
        ttk.Button(actions, text="Preview Result", command=self.preview_result).pack(fill=X, padx=8, pady=4)
        ttk.Button(actions, text="Confirm Regions", command=self.confirm_regions).pack(fill=X, padx=8, pady=4)
        ttk.Button(actions, text="Save Only", command=self.save_only).pack(fill=X, padx=8, pady=4)
        ttk.Button(actions, text="Save & Generate", command=self.save_and_generate).pack(fill=X, padx=8, pady=(4, 8))

        ttk.Label(root_frame, textvariable=self.status_var, anchor="w").grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

    def _add_coord_row(self, parent: ttk.LabelFrame, label: str, variable: StringVar) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=X, padx=8, pady=2)
        ttk.Label(row, text=f"{label}:", width=10).pack(side=LEFT)
        ttk.Entry(row, textvariable=variable, width=14).pack(side=LEFT, fill=X, expand=True)

    def _load_persisted_template_path(self) -> None:
        if self.settings.template_path and Path(self.settings.template_path).exists():
            self.load_template(Path(self.settings.template_path))
        elif self.template_path and self.template_path.exists():
            self.load_template(self.template_path)

    def open_template_dialog(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PNG images", "*.png"), ("Image files", "*.png;*.jpg;*.jpeg;*.webp"), ("All files", "*.*")])
        if path:
            self.load_template(Path(path))

    def load_template(self, path: Path) -> None:
        validate_template_path(path)
        self.template_path = path
        self.template_image = load_image(path)
        self.settings.template_path = str(path)
        self._persist_settings()
        self.reset_zoom()
        if self.settings.viewport is None:
            self.settings.viewport = Region(0, 0, min(800, self.template_image.width), min(400, self.template_image.height))
        if self.settings.address_bar is None:
            self.settings.address_bar = Region(100, 40, min(1200, self.template_image.width - 100), 60)
        self._load_current_region_into_inputs()
        self._refresh_template_info()
        self.redraw()
        self.status_var.set(f"Loaded template: {path}")

    def _refresh_template_info(self) -> None:
        if self.template_image is None or self.template_path is None:
            self.template_info_var.set("Template: none | Resolution: -")
            return
        self.template_info_var.set(
            f"Template: {self.template_path.name} | Resolution: {self.template_image.width} × {self.template_image.height}"
        )

    def set_active_region(self, region: RegionKind) -> None:
        self.active_region = region
        self._load_current_region_into_inputs()
        self.status_var.set(f"Editing {region.replace('_', ' ').upper()}")
        self.redraw()

    def _current_region(self) -> Region | None:
        return self.settings.viewport if self.active_region == "viewport" else self.settings.address_bar

    def _set_current_region(self, region: Region | None) -> None:
        if self.active_region == "viewport":
            self.settings.viewport = region
        else:
            self.settings.address_bar = region
        self.settings.regions_confirmed = False
        self._persist_settings()
        self._load_current_region_into_inputs()
        self.redraw()

    def _load_current_region_into_inputs(self) -> None:
        region = self._current_region()
        if region is None:
            self.x_var.set("0")
            self.y_var.set("0")
            self.w_var.set("0")
            self.h_var.set("0")
            return
        self.x_var.set(str(region.x))
        self.y_var.set(str(region.y))
        self.w_var.set(str(region.width))
        self.h_var.set(str(region.height))

    def _inputs_to_region(self) -> Region:
        return Region(
            x=int(self.x_var.get()),
            y=int(self.y_var.get()),
            width=int(self.w_var.get()),
            height=int(self.h_var.get()),
        )

    def apply_coordinates(self) -> None:
        if self.template_image is None:
            messagebox.showerror("BrowserFrame", "Load a template first.")
            return
        try:
            region = self._inputs_to_region()
            validate_region(region, self.template_image.size, self.active_region.replace("_", " ").title())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("BrowserFrame", str(exc))
            return
        self._set_current_region(region)
        self.status_var.set(f"Applied {self.active_region.replace('_', ' ').upper()}")

    def reset_region(self) -> None:
        self._load_current_region_into_inputs()
        self.status_var.set("Region reset")

    def clear_region(self) -> None:
        self._set_current_region(None)
        self.status_var.set(f"Cleared {self.active_region.replace('_', ' ').upper()}")

    def change_zoom(self, factor: float) -> None:
        self.transform.zoom = max(0.25, min(4.0, self.transform.zoom * factor))
        self.redraw()

    def reset_zoom(self) -> None:
        self.transform.zoom = 1.0
        self.redraw()

    def fit_to_window(self) -> None:
        if self.template_image is None:
            return
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        scale_x = canvas_width / self.template_image.width
        scale_y = canvas_height / self.template_image.height
        self.transform.zoom = max(0.25, min(4.0, min(scale_x, scale_y)))
        self.redraw()

    def on_mouse_wheel(self, event) -> None:
        if getattr(event, "delta", 0) > 0 or getattr(event, "num", None) == 4:
            self.change_zoom(1.1)
        elif getattr(event, "delta", 0) < 0 or getattr(event, "num", None) == 5:
            self.change_zoom(0.9)

    def canvas_to_image(self, canvas_x: int, canvas_y: int) -> tuple[int, int]:
        if self.template_image is None:
            return 0, 0
        canvas_x = self.canvas.canvasx(canvas_x)
        canvas_y = self.canvas.canvasy(canvas_y)
        image_x = round(canvas_x / self.transform.zoom)
        image_y = round(canvas_y / self.transform.zoom)
        return max(0, min(self.template_image.width, image_x)), max(0, min(self.template_image.height, image_y))

    def image_to_canvas(self, x: int, y: int) -> tuple[float, float]:
        return x * self.transform.zoom, y * self.transform.zoom

    def image_to_canvas_region(self, region: Region) -> tuple[float, float, float, float]:
        x1, y1 = self.image_to_canvas(region.x, region.y)
        x2, y2 = self.image_to_canvas(region.x + region.width, region.y + region.height)
        return x1, y1, x2, y2

    def on_canvas_press(self, event) -> None:
        if self.template_image is None:
            return
        image_x, image_y = self.canvas_to_image(event.x, event.y)
        current = self._current_region()
        if current is not None:
            handle = self._detect_handle(event.x, event.y, current)
            if handle == "inside":
                self.drag_mode = "move"
                self.drag_handle = None
                self.drag_origin_image = (image_x, image_y)
                self.drag_origin_region = current
                return
            if handle != "outside":
                self.drag_mode = "resize"
                self.drag_handle = handle
                self.drag_origin_image = (image_x, image_y)
                self.drag_origin_region = current
                return
        self.drag_mode = "draw"
        self.drag_origin_image = (image_x, image_y)
        self.drag_origin_region = Region(image_x, image_y, 1, 1)
        self._set_current_region(self.drag_origin_region)

    def on_canvas_drag(self, event) -> None:
        if self.template_image is None or self.drag_mode is None or self.drag_origin_image is None:
            return
        image_x, image_y = self.canvas_to_image(event.x, event.y)
        current = self._current_region()
        if current is None:
            return
        origin_x, origin_y = self.drag_origin_image
        if self.drag_mode == "draw":
            x0 = min(origin_x, image_x)
            y0 = min(origin_y, image_y)
            x1 = max(origin_x, image_x)
            y1 = max(origin_y, image_y)
            self._set_current_region(Region(x0, y0, max(1, x1 - x0), max(1, y1 - y0)))
        elif self.drag_mode == "move":
            assert self.drag_origin_region is not None
            dx = image_x - origin_x
            dy = image_y - origin_y
            moved = Region(
                self.drag_origin_region.x + dx,
                self.drag_origin_region.y + dy,
                self.drag_origin_region.width,
                self.drag_origin_region.height,
            ).clamp_within(self.template_image.width, self.template_image.height)
            self._set_current_region(moved)
        elif self.drag_mode == "resize":
            assert self.drag_handle is not None
            resized = self._resize_region_from_handle(current, self.drag_handle, image_x, image_y)
            self._set_current_region(resized)

    def on_canvas_release(self, event) -> None:
        self.drag_mode = None
        self.drag_origin_image = None
        self.drag_origin_region = None
        self.drag_handle = None

    def _detect_handle(self, canvas_x: int, canvas_y: int, region: Region) -> str:
        x1, y1, x2, y2 = self.image_to_canvas_region(region)
        margin = 8
        handles = {
            "nw": (x1, y1),
            "n": ((x1 + x2) / 2, y1),
            "ne": (x2, y1),
            "w": (x1, (y1 + y2) / 2),
            "e": (x2, (y1 + y2) / 2),
            "sw": (x1, y2),
            "s": ((x1 + x2) / 2, y2),
            "se": (x2, y2),
        }
        for name, (hx, hy) in handles.items():
            if abs(canvas_x - hx) <= margin and abs(canvas_y - hy) <= margin:
                return name
        if x1 <= canvas_x <= x2 and y1 <= canvas_y <= y2:
            return "inside"
        return "outside"

    def _resize_region_from_handle(self, region: Region, handle: str, x: int, y: int) -> Region:
        left = region.x
        top = region.y
        right = region.x + region.width
        bottom = region.y + region.height
        if handle in {"nw", "w", "sw"}:
            left = min(x, right - 1)
        if handle in {"ne", "e", "se"}:
            right = max(x, left + 1)
        if handle in {"nw", "n", "ne"}:
            top = min(y, bottom - 1)
        if handle in {"sw", "s", "se"}:
            bottom = max(y, top + 1)
        resized = Region(left, top, max(1, right - left), max(1, bottom - top))
        assert self.template_image is not None
        return resized.clamp_within(self.template_image.width, self.template_image.height)

    def on_key_press(self, event) -> None:
        if self.template_image is None:
            return
        region = self._current_region()
        if region is None:
            return
        if event.keysym not in {"Left", "Right", "Up", "Down"}:
            return
        step = 10 if event.state & 0x0001 else 1
        delta_x = -step if event.keysym == "Left" else step if event.keysym == "Right" else 0
        delta_y = -step if event.keysym == "Up" else step if event.keysym == "Down" else 0
        if event.state & 0x0004:
            resized = Region(region.x, region.y, max(1, region.width + delta_x), max(1, region.height + delta_y))
            resized = resized.clamp_within(self.template_image.width, self.template_image.height)
            self._set_current_region(resized)
        else:
            moved = Region(region.x + delta_x, region.y + delta_y, region.width, region.height)
            moved = moved.clamp_within(self.template_image.width, self.template_image.height)
            self._set_current_region(moved)
        self.status_var.set(f"Adjusted {self.active_region.replace('_', ' ').upper()} with keyboard")

    def redraw(self) -> None:
        self.canvas.delete("all")
        if self.template_image is None:
            self.zoom_var.set(f"{round(self.transform.zoom * 100)}%")
            return
        display = self.template_image.resize(
            (
                max(1, round(self.template_image.width * self.transform.zoom)),
                max(1, round(self.template_image.height * self.transform.zoom)),
            ),
            Image.Resampling.LANCZOS,
        )
        self.template_photo = ImageTk.PhotoImage(display)
        self.canvas.create_image(0, 0, anchor="nw", image=self.template_photo)
        self.canvas.configure(scrollregion=(0, 0, display.width, display.height))
        self._draw_region(self.settings.viewport, outline="#1e88e5", label="VIEWPORT", fill="#1e88e520", dashed=False)
        self._draw_region(self.settings.address_bar, outline="#e53935", label="ADDRESS BAR", fill="#e5393520", dashed=True)
        self.zoom_var.set(f"{round(self.transform.zoom * 100)}%")
        self._load_current_region_into_inputs()

    def _draw_region(self, region: Region | None, outline: str, label: str, fill: str, dashed: bool) -> None:
        if region is None:
            return
        x1, y1, x2, y2 = self.image_to_canvas_region(region)
        dash = (6, 4) if dashed else None
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=3, dash=dash)
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
        self.canvas.create_text(x1 + 8, y1 + 8, text=label, anchor="nw", fill=outline, font=("Segoe UI", 11, "bold"))
        self.canvas.create_text(
            x1 + 8,
            y2 + 8,
            text=f"X: {region.x}  Y: {region.y}  Width: {region.width}  Height: {region.height}",
            anchor="nw",
            fill=outline,
            font=("Segoe UI", 9),
        )
        for px, py in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):
            self.canvas.create_rectangle(px - 4, py - 4, px + 4, py + 4, fill=outline, outline="#ffffff")

    def preview_result(self) -> None:
        if self.template_path is None:
            messagebox.showerror("BrowserFrame", "Load a template first.")
            return
        if self.settings.viewport is None or self.settings.address_bar is None:
            messagebox.showerror("BrowserFrame", "Viewport and address bar must be selected first.")
            return
        batch_item = self._choose_preview_item()
        if batch_item is None:
            return
        try:
            preview = create_preview(self.template_path, batch_item.screenshot, batch_item.url, batch_item.fit)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("BrowserFrame", str(exc))
            return
        dialog = Toplevel(self.root)
        dialog.title("BrowserFrame Preview")
        dialog.geometry("1200x840")
        dialog.transient(self.root)
        dialog.grab_set()

        photo = ImageTk.PhotoImage(preview)
        image_label = ttk.Label(dialog, image=photo)
        image_label.image = photo  # type: ignore[attr-defined]
        image_label.pack(fill=BOTH, expand=True, padx=8, pady=8)

        action_row = ttk.Frame(dialog)
        action_row.pack(fill=X, padx=8, pady=(0, 8))

        def back_to_edit() -> None:
            dialog.destroy()

        def confirm_regions() -> None:
            dialog.destroy()
            self.confirm_regions()

        ttk.Button(action_row, text="Back to Edit", command=back_to_edit).pack(side=LEFT, expand=True, fill=X, padx=4)
        ttk.Button(action_row, text="Confirm Regions", command=confirm_regions).pack(side=LEFT, expand=True, fill=X, padx=4)

    def _choose_preview_item(self) -> BatchItem | None:
        preview_path = filedialog.askopenfilename(
            title="Select screenshot for preview",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.webp"), ("All files", "*.*")],
        )
        if not preview_path:
            return None
        url = simple_input_dialog(self.root, "Preview URL", "Enter a sample URL for preview:", "https://example.com")
        if url is None:
            return None
        fit_mode = "cover"
        return BatchItem(screenshot=Path(preview_path), url=url, output="preview.png", fit=fit_mode)

    def confirm_regions(self) -> None:
        if self.template_image is None:
            messagebox.showerror("BrowserFrame", "Load a template first.")
            return
        if self.settings.viewport is None:
            messagebox.showerror("BrowserFrame", "Viewport has not been selected.")
            return
        if self.settings.address_bar is None:
            messagebox.showerror("BrowserFrame", "Address bar has not been selected.")
            return
        try:
            validate_region(self.settings.viewport, self.template_image.size, "Viewport")
            validate_region(self.settings.address_bar, self.template_image.size, "Address bar")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("BrowserFrame", str(exc))
            return
        self.settings.regions_confirmed = True
        self._persist_settings()
        summary = (
            "Viewport:\n"
            f"X: {self.settings.viewport.x}\n"
            f"Y: {self.settings.viewport.y}\n"
            f"Width: {self.settings.viewport.width}\n"
            f"Height: {self.settings.viewport.height}\n\n"
            "Address Bar:\n"
            f"X: {self.settings.address_bar.x}\n"
            f"Y: {self.settings.address_bar.y}\n"
            f"Width: {self.settings.address_bar.width}\n"
            f"Height: {self.settings.address_bar.height}"
        )
        result = choice_dialog(self.root, "Confirm Regions", f"{summary}\n\nUse these regions for batch generation?", ["Edit Again", "Save Only", "Save & Generate"])
        if result == "Edit Again":
            self.settings.regions_confirmed = False
            self._persist_settings()
            self.status_var.set("Returned to editor")
            return
        if result == "Save Only":
            self.settings.regions_confirmed = True
            self._persist_settings()
            messagebox.showinfo("BrowserFrame", "Settings saved.")
            return
        if result == "Save & Generate":
            self.settings.regions_confirmed = True
            self._persist_settings()
            try:
                generator = BatchGenerator(
                    template_path=self.template_path,
                    config_path=Path("config.json"),
                    settings_path=Path("settings.json"),
                    output_dir=Path("output"),
                )
                result_summary = generator.generate()
                messagebox.showinfo(
                    "BrowserFrame",
                    f"Generation complete. Success: {result_summary.success}\nFailed: {result_summary.failed}",
                )
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("BrowserFrame", str(exc))

    def save_only(self) -> None:
        self._persist_settings()
        messagebox.showinfo("BrowserFrame", "Settings saved.")

    def save_and_generate(self) -> None:
        self.confirm_regions()

    def _persist_settings(self) -> None:
        save_settings(self.settings)


def simple_input_dialog(root: Tk, title: str, prompt: str, initial_value: str = "") -> str | None:
    dialog = Toplevel(root)
    dialog.title(title)
    dialog.geometry("460x160")
    dialog.transient(root)
    dialog.grab_set()
    value = StringVar(value=initial_value)
    ttk.Label(dialog, text=prompt, wraplength=420).pack(padx=12, pady=(12, 8))
    entry = ttk.Entry(dialog, textvariable=value)
    entry.pack(fill=X, padx=12)
    entry.focus_set()
    result: dict[str, str | None] = {"value": None}

    def accept() -> None:
        result["value"] = value.get().strip()
        dialog.destroy()

    def cancel() -> None:
        result["value"] = None
        dialog.destroy()

    buttons = ttk.Frame(dialog)
    buttons.pack(fill=X, padx=12, pady=12)
    ttk.Button(buttons, text="OK", command=accept).pack(side=LEFT, expand=True, fill=X, padx=4)
    ttk.Button(buttons, text="Cancel", command=cancel).pack(side=LEFT, expand=True, fill=X, padx=4)
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    root.wait_window(dialog)
    return result["value"]


def choice_dialog(root: Tk, title: str, message: str, choices: list[str]) -> str | None:
    dialog = Toplevel(root)
    dialog.title(title)
    dialog.geometry("520x260")
    dialog.transient(root)
    dialog.grab_set()
    result: dict[str, str | None] = {"value": None}

    ttk.Label(dialog, text=message, wraplength=480, justify="left").pack(fill=BOTH, expand=True, padx=12, pady=12)
    buttons = ttk.Frame(dialog)
    buttons.pack(fill=X, padx=12, pady=12)

    def choose(value: str) -> None:
        result["value"] = value
        dialog.destroy()

    for choice in choices:
        ttk.Button(buttons, text=choice, command=lambda value=choice: choose(value)).pack(side=LEFT, expand=True, fill=X, padx=4)
    dialog.protocol("WM_DELETE_WINDOW", lambda: choose(choices[0] if choices else None))
    root.wait_window(dialog)
    return result["value"]


def run_editor(template_path: Path | None = None) -> None:
    root = Tk()
    app = RegionEditorApp(root, template_path=template_path)
    root.mainloop()
