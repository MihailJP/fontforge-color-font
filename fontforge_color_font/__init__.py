"""Fontforge plugin for color fonts"""

from .export import exportColorFont
from .load import hasSvgTable, hasColrTable, loadSvg, loadColrColorFontMetadata, loadSvgColorFontMetadata, loadColorFont
from .svg import NoColorGlyphError, svgIsRegistered, deleteSvg, exportSvg

__all__ = [
    # export
    'exportColorFont',

    # load
    'hasSvgTable',
    'hasColrTable',
    'loadSvg',
    'loadColrColorFontMetadata',
    'loadSvgColorFontMetadata',
    'loadColorFont',

    # svg
    'NoColorGlyphError',
    'svgIsRegistered',
    'deleteSvg',
    'exportSvg',
]
