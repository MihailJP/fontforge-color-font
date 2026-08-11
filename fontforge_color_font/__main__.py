import fontforge

from . import hook, load, svg, export
from fontforge_plugin_helper import addSystemHook
from .translation import tr, setTranslation


def fontforge_plugin_init(**kw):
    setTranslation()

    addSystemHook('loadFontHook', hook.loadHook, enableIfScriptMode=False)
    addSystemHook('newFontHook', hook.newFontHook, enableIfScriptMode=False)

    fontforge.registerMenuItem(
        callback=load.loadColorFontMenu,
        enable=None,
        context="Font",
        name=tr.get("Open color font..."),
        submenu=tr.get('Color font'),
    )
    fontforge.registerMenuItem(
        callback=export.exportColorFontMenu,
        enable=None,
        context="Font",
        name=tr.get("Export color font..."),
        submenu=tr.get('Color font'),
    )

    fontforge.registerMenuItem(
        divider=True,
        context="Font",
        submenu=tr.get('Color font'),
    )

    fontforge.registerMenuItem(
        callback=svg.importSvgMenu,
        enable=None,
        context=("Font", "Glyph"),
        name=tr.get("Import SVG as color font glyph..."),
        submenu=tr.get('Color font'),
    )
    fontforge.registerMenuItem(
        callback=svg.exportSvgMenu,
        enable=svg.svgIsRegisteredMenu,
        context=("Font", "Glyph"),
        name=tr.get("Export SVG color font glyph..."),
        submenu=tr.get('Color font'),
    )
    fontforge.registerMenuItem(
        callback=svg.deleteSvgMenu,
        enable=svg.svgIsRegisteredMenu,
        context=("Font", "Glyph"),
        name=tr.get("Delete SVG color font glyph"),
        submenu=tr.get('Color font'),
    )
