from . import load
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


# def hello(u, glyph):
#     fontforge.postNotice("FontForge Plugin Template", "Hello, world!")


# def helloEnable(u, glyph):
#     return True


def fontforge_plugin_init(**kw):
    if fontforge.hasUserInterface:
        _addHook('loadFontHook', load.loadHook)
        _addHook('newFontHook', load.newFontHook)
    # fontforge.registerMenuItem(
    #     callback=hello,
    #     enable=helloEnable,
    #     context=("Font", "Glyph"),
    #     name="Hello"
    # )
