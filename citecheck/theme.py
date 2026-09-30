"""The look of the window: the same colours, corners and fonts as the voice assistant.

The values live in ONE file, for humans: assets/theme.json. Each colour there has a
clickable square in VS Code (thanks to assets/theme.schema.json) and a sentence saying where
it shows. This module is the wiring only: which colour and which corner radius go on which
part of each customtkinter widget. Change a value in theme.json, never here.

apply() must run BEFORE the first widget is built: customtkinter widgets read the theme when
they are constructed.

Icons are the voice assistant's white Lucide PNGs (48 px), shrunk by Tk itself. Pillow is not
needed, and this program, which opens files received from outside, does without an image
library.
"""
import copy
import json
import tkinter as tk
import warnings
from pathlib import Path

import customtkinter as ctk

ASSETS = Path(__file__).parent / "assets"

COLORS: dict = {}
FONT_SIZES: dict = {}
SPACING: dict = {}
PADDINGS: dict = {}
ICON_SIZE = 16

# Widget -> parameter -> colour name in theme.json. A value that is not a colour name (a
# number, "transparent") is passed as it is.
_CTK_WIRING = {
    "CTk":         {"fg_color": "bg"},
    "CTkToplevel": {"fg_color": "bg"},
    "CTkFrame": {"border_width": 0, "fg_color": "surface",
                 "top_fg_color": "surface", "border_color": "border"},
    "CTkButton": {"border_width": 0, "fg_color": "accent",
                  "hover_color": "accent_hover", "border_color": "border",
                  "text_color": "text_on_accent", "text_color_disabled": "text_disabled"},
    "CTkLabel": {"fg_color": "transparent", "text_color": "text"},
    "CTkEntry": {"border_width": 1, "fg_color": "input",
                 "border_color": "border", "text_color": "text",
                 "placeholder_text_color": "text_disabled"},
    "CTkCheckBox": {"border_width": 2, "fg_color": "accent",
                    "border_color": "border_strong", "hover_color": "accent_hover",
                    "checkmark_color": "text_on_accent", "text_color": "text",
                    "text_color_disabled": "text_disabled"},
    "CTkScrollbar": {"border_spacing": 4, "fg_color": "transparent",
                     "button_color": "border", "button_hover_color": "border_strong"},
    "CTkSegmentedButton": {"border_width": 2, "fg_color": "surface_2",
                           "selected_color": "accent", "selected_hover_color": "accent_hover",
                           "unselected_color": "surface_2", "unselected_hover_color": "border",
                           "text_color": "text", "text_color_disabled": "text_disabled"},
    "CTkTextbox": {"border_width": 0, "fg_color": "input",
                   "border_color": "border", "text_color": "text",
                   "scrollbar_button_color": "border",
                   "scrollbar_button_hover_color": "border_strong"},
}

# Widget -> corner parameter -> radius name in theme.json ("arrondis").
_RADIUS_WIRING = {
    "CTkFrame":           {"corner_radius": "panneaux"},
    "CTkTextbox":         {"corner_radius": "panneaux"},
    "CTkButton":          {"corner_radius": "boutons"},
    "CTkSegmentedButton": {"corner_radius": "boutons"},
    "CTkEntry":           {"corner_radius": "champs"},
    "CTkCheckBox":        {"corner_radius": "cases"},
    "CTkScrollbar":       {"corner_radius": "interrupteurs_curseurs"},
}


def apply():
    """Load theme.json and install it as customtkinter's default theme."""
    global ICON_SIZE
    raw = json.loads((ASSETS / "theme.json").read_text(encoding="utf-8"))
    # theme.json groups the colours for readers ("Fonds", "Texte"...): only names count.
    for group in raw["couleurs"].values():
        for name, entry in group.items():
            COLORS[name] = entry["couleur"]
    fonts = raw["polices"]
    FONT_SIZES.update({k: fonts[k] for k in ("small", "body", "title")})
    SPACING.update(raw["espacements"])
    PADDINGS.update({name: entry["px"] for name, entry in raw["marges_interieures"].items()})
    ICON_SIZE = raw.get("taille_icones", ICON_SIZE)

    ctk.set_appearance_mode("dark")
    # Start from the stock "blue" theme: a key the wiring leaves out keeps its default
    # instead of breaking the widget.
    ctk.set_default_color_theme("blue")
    theme = copy.deepcopy(ctk.ThemeManager.theme)
    for widget, params in _CTK_WIRING.items():
        theme[widget].update({
            p: COLORS.get(v, v) if isinstance(v, str) else v for p, v in params.items()})
    radii = {name: entry["px"] for name, entry in raw["arrondis"].items()}
    for widget, params in _RADIUS_WIRING.items():
        theme[widget].update({p: radii[name] for p, name in params.items()})
    theme["CTkFont"] = {"family": fonts.get("famille", "Roboto"),
                        "size": fonts["body"], "weight": "normal"}
    ctk.ThemeManager.theme = theme
    # A tk.PhotoImage on a button makes customtkinter warn that it cannot rescale it:
    # icon() already picks the size for the screen's scaling.
    warnings.filterwarnings("ignore", message=r".*is not CTkImage.*")


def font(size="body", weight="normal", **kw):
    """Theme font. size is "small", "body" or "title"."""
    return ctk.CTkFont(size=FONT_SIZES[size], weight=weight, **kw)


_icons: dict = {}


def icon(root, name):
    """assets/icons/<name>.png, white, shrunk to about ICON_SIZE on this screen. Kept in a
    cache: Tk forgets an image nobody holds."""
    scale = ctk.ScalingTracker.get_window_scaling(root)
    if (name, scale) not in _icons:
        full = tk.PhotoImage(master=root, file=str(ASSETS / "icons" / f"{name}.png"))
        step = max(1, round(full.width() / (ICON_SIZE * scale)))
        _icons[(name, scale)] = full.subsample(step)
    return _icons[(name, scale)]
