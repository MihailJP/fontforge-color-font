"""Fontforge plugin for color fonts"""

from .export import exportColorFont
from .load import hasSvgTable, hasColrTable, loadSvg, loadColrColorFontMetadata, loadSvgColorFontMetadata
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

    # svg
    'NoColorGlyphError',
    'svgIsRegistered',
    'deleteSvg',
    'exportSvg',
]
