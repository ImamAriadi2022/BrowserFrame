# BrowserFrame

BrowserFrame is a Python tool for generating consistent website documentation images from a browser template screenshot. It preserves the browser frame, toolbar, address bar, and taskbar while replacing only the selected viewport area and the address bar URL.

## Purpose

The project is designed for a strict workflow:

SELECT → ADJUST → PREVIEW → CONFIRM → GENERATE

The template is never modified in place. All compositing happens on a copy in memory and the final PNG files are written to `output/`.

## Requirements

- Python 3.10+
- Pillow
- Tkinter from the Python standard library

On some Linux installations, Tkinter may need to be installed separately through the OS package manager.

## Installation

```bash
pip install -r requirements.txt
```

## Run

Open the Region Editor:

```bash
python main.py
```

You can also explicitly open the editor:

```bash
python main.py --edit
```

Run preview using the current `settings.json` and the first item in `config.json`:

```bash
python main.py --preview
```

Run batch generation:

```bash
python main.py --generate
```

Use a custom config or template:

```bash
python main.py --generate --config config.json --template template.png
```

## Workflow

1. Open the editor with `python main.py`.
2. Load a browser template using `Open Template`.
3. Select `Viewport` or `Address Bar`.
4. Drag on the template to create a selection.
5. Use the coordinate inputs for fine adjustment.
6. Use zoom controls for precise placement.
7. Click `Preview Result` to inspect the composited output.
8. If the position is wrong, use `Back to Edit` and correct it.
9. Click `Confirm Regions` and choose `Edit Again`, `Save Only`, or `Save & Generate`.

## Region Editing

The editor supports:

- Click-and-drag selection
- Move existing selection
- Resize via corners and edges
- Arrow-key movement by 1 pixel
- Shift + Arrow movement by 10 pixels
- Ctrl + Arrow resize by 1 pixel
- Zoom range from 25% to 400%
- Scrollbars for navigation when the template exceeds the viewport

All coordinates are stored in the original template coordinate system, not canvas coordinates.

## Preview

Preview uses the same compositing engine as final generation. It lets you validate:

- Viewport placement
- Address bar placement
- URL rendering
- Screenshot fit mode

Preview is non-destructive. It does not write final output files or alter the template.

## Confirm Regions

The settings file stores a `regions_confirmed` flag.

If you change any region after confirmation, the flag is cleared automatically. You must preview and confirm again before batch generation.

## Batch Generation

Batch generation reads `config.json`, then processes each item:

- Loads the screenshot
- Fits it into the viewport using `cover` or `contain`
- Renders the URL into the address bar
- Saves a PNG in `output/`

If one item fails, the batch continues with the next item.

## `config.json`

`config.json` must be a JSON array. Each item supports:

```json
{
  "screenshot": "screenshots/dashboard.png",
  "url": "https://parkfinder.id/dashboard",
  "output": "dashboard.png",
  "fit": "cover"
}
```

Fields:

- `screenshot`: path to the website screenshot
- `url`: URL to render in the address bar
- `output`: filename under `output/`
- `fit`: `cover` or `contain`

## `settings.json`

`settings.json` stores the selected regions and rendering preferences.

```json
{
  "regions_confirmed": false,
  "viewport": {
    "x": 0,
    "y": 0,
    "width": 0,
    "height": 0
  },
  "address_bar": {
    "x": 0,
    "y": 0,
    "width": 0,
    "height": 0
  },
  "url_text": {
    "font_size": 16,
    "text_color": "#202124",
    "padding_left": 20,
    "background_color": "#FFFFFF"
  },
  "contain_background": "#FFFFFF",
  "template_path": "template.png"
}
```

## CLI Commands

- `python main.py` opens the Region Editor
- `python main.py --edit` opens the Region Editor
- `python main.py --preview` renders a preview image using the current settings
- `python main.py --generate` generates all output images from `config.json`
- `python main.py --config custom.json` uses a different config file
- `python main.py --template custom.png` uses a different template file

## Troubleshooting

- `Template not found`: check the path passed via `--template` or open a valid file in the editor.
- `Viewport has not been selected`: select and confirm the regions first.
- `Address bar has not been selected`: select the address bar region first.
- `Regions have not been confirmed. Run: python main.py --edit`: open the editor, preview, and confirm regions before generation.
- `Screenshot not found`: verify the `screenshot` path in `config.json`.
- `Invalid JSON`: check `config.json` or `settings.json` for syntax errors.
- `Tkinter unavailable`: install the Tkinter package for your Python distribution or operating system.
# BrowserFrame