import fontforge

from . import load, svg, export
from fontforge_plugin_helper import addSystemHook


def fontforge_plugin_init(**kw):
    addSystemHook('loadFontHook', load.loadHook, enableIfScriptMode=False)
    addSystemHook('newFontHook', load.newFontHook, enableIfScriptMode=False)

    fontforge.registerMenuItem(
        callback=load.loadColorFontMenu,
        enable=None,
        context="Font",
        name="Open color font...",
        submenu='Color font',
    )
    fontforge.registerMenuItem(
        callback=export.exportColorFontMenu,
        enable=None,
        context="Font",
        name="Export color font...",
        submenu='Color font',
    )

    fontforge.registerMenuItem(
        divider=True,
        context="Font",
        submenu='Color font',
    )

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
