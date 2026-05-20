"""Fontforge plugin for color fonts"""

from .load import hasSvgTable, hasColrTable, loadSvg, loadColrColorFontMetadata, loadSvgColorFontMetadata
from .svg import NoColorGlyphError, svgIsRegistered, deleteSvg, exportSvg

__all__ = [
    # load
    'hasSvgTable',
    'hasColrTable',
    'loadSvg',
    'loadColrColorFontMetadata',
    'loadSvgColorFontMetadata',

    # svg
    'NoColorGlyphError',
    'svgIsRegistered',
    'deleteSvg',
    'exportSvg',
]
