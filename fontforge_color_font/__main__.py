from . import load, svg, export
import fontforge
from typing import Literal, Callable


def _addHook(
    name: Literal['newFontHook', 'loadFontHook'],
    hook: Callable[[fontforge.font], None]
):
    assert isinstance(fontforge.hooks, dict)
    if name in fontforge.hooks:
        currentHook = fontforge.hooks[name]

        def chainHook(font: fontforge.font):
            currentHook(font)
            hook(font)

        fontforge.hooks[name] = chainHook
    else:
        fontforge.hooks[name] = hook


def fontforge_plugin_init(**kw):
    if fontforge.hasUserInterface:
        _addHook('loadFontHook', load.loadHook)
        _addHook('newFontHook', load.newFontHook)
    fontforge.registerMenuItem(
        callback=svg.importSvgMenu,
        enable=None,
        context=("Font", "Glyph"),
        name="Import SVG as color font glyph...",
        submenu='Color font',
    )
    fontforge.registerMenuItem(
        callback=svg.exportSvgMenu,
        enable=svg.svgIsRegisteredMenu,
        context=("Font", "Glyph"),
        name="Export SVG color font glyph...",
        submenu='Color font',
    )
    fontforge.registerMenuItem(
        callback=svg.deleteSvgMenu,
        enable=svg.svgIsRegisteredMenu,
        context=("Font", "Glyph"),
        name="Delete SVG color font glyph",
        submenu='Color font',
    )
    fontforge.registerMenuItem(
        callback=export.testSvgMenu,
        enable=None,
        context="Font",
        name="Export test",
        submenu='Color font',
    )
