import fontforge
from typing import Literal, Callable


def _generatePreHook(font: fontforge.font, target: str):
    pass


def _generatePostHook(font: fontforge.font, target: str):
    pass


def _addHook(
    font: fontforge.font,
    name: Literal['generateFontPreHook', 'generateFontPostHook'],
    hook: Callable[[fontforge.font, str], None]
):
    assert isinstance(font.temporary, dict)
    if name in font.temporary:
        currentHook = font.temporary[name]

        def chainHook(font: fontforge.font, target: str):
            currentHook(font, target)
            hook(font, target)

        font.temporary[name] = chainHook
    else:
        font.temporary[name] = hook


def _addGenerateHook(font: fontforge.font):
    if not isinstance(font.temporary, dict):
        font.temporary = {}
    _addHook(font, 'generateFontPreHook', _generatePreHook)
    _addHook(font, 'generateFontPostHook', _generatePostHook)


def _loadHook_ttf(font: fontforge.font):
    pass


def loadHook(font: fontforge.font):
    if font.path.endswith('.ttf') or font.path.endswith('.woff2'):
        _loadHook_ttf(font)
        _addGenerateHook(font)
    elif font.path.endswith('.sfd'):
        _addGenerateHook(font)


def newFontHook(font: fontforge.font):
    _addGenerateHook(font)
