from tempfile import TemporaryDirectory

import fontforge

from fontforge_plugin_helper import generationHookSetter
from .load import hasColrTable, loadColrColorFontMetadata, hasSvgTable, loadSvgColorFontMetadata
from .export import _exportColorFontMetadata


def _generatePreHook(font: fontforge.font, target: str):
    pass


def _generatePostHook(font: fontforge.font, target: str):
    if any(g for g in font.glyphs() if isinstance(g.persistent, dict) and 'SVG' in g.persistent):
        if str(target).endswith('.ttf'):
            with TemporaryDirectory() as tmpdir:
                if isinstance(font.persistent, dict) and 'VF' in font.persistent:
                    _exportColorFontMetadata(target, target, font, tmpdir, 1, -1)
                else:
                    _exportColorFontMetadata(target, target, font, tmpdir, 1, 0)


_addGenerateHook = generationHookSetter(_generatePreHook, _generatePostHook, enableIfScriptMode=False)


def _loadHook_ttf(font: fontforge.font):
    if hasColrTable(font):
        loadColrColorFontMetadata(font)
    elif hasSvgTable(font):
        # if fontforge.ask(
        #     'SVG color font',
        #     "This font has 'SVG ' table.\n"
        #         "This means this is a color font.\n"
        #         "Import the SVG documents included in the font?\n"
        #         "This may take some minutes.",
        #     ('_Yes', '_No'),
        #     0,
        #     1,
        # ) == 0:
        #     loadSvgColorFont(font)
        try:
            loadSvgColorFontMetadata(font)
        except NotImplementedError as e:
            fontforge.logWarning(str(e))


def loadHook(font: fontforge.font):
    if not font.path:  # may occur in CID fonts
        _addGenerateHook(font)
    elif font.path.endswith('.ttf'):
        _loadHook_ttf(font)
        _addGenerateHook(font)
    elif font.path.endswith('.sfd'):
        _addGenerateHook(font)


def newFontHook(font: fontforge.font):
    _addGenerateHook(font)
