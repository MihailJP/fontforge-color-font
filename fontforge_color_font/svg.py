import fontforge
from os import PathLike
from pathlib import Path
from .load import loadSvg


class NoColorGlyphError(RuntimeError):
    """Attempted to read SVG from non-color glyph"""


def svgIsRegistered(glyph: fontforge.glyph) -> bool:
    """Check if color glyph SVG data is defined for a glyph

    :param glyph: a Fontforge glyph object
    :return: ``True`` if color glyph data exists
    """
    return bool(
        glyph.persistent and
        isinstance(glyph.persistent, dict) and
        'SVG' in glyph.persistent
    )


def deleteSvg(glyph: fontforge.glyph):
    """Removes color glyph SVG from glyph

    :param glyph: a Fontforge glyph object which has color glyph SVG in ``persistent`` ``dict``
    """
    if svgIsRegistered(glyph):
        del glyph.persistent['SVG']
        if glyph.persistent:
            glyph.persistent = None


def exportSvg(glyph: fontforge.glyph, path: str | PathLike):
    """Exports color glyph SVG

    :param glyph: a Fontforge glyph object which has color glyph SVG in ``persistent`` ``dict``
    :param path: destination path of exported SVG file
    :raises ``NoColorGlyphError``: if there is not SVG color glyph definition in the glyph.
    """
    if svgIsRegistered(glyph):
        with Path(path).open('w') as svg:
            svg.write(glyph.persistent['SVG'])
    else:
        raise NoColorGlyphError("glyph '{}' does not have color font definition".format(glyph.glyphname))


def svgIsRegisteredMenu(u, fontOrGlyph: fontforge.font | fontforge.glyph) -> bool:
    if isinstance(fontOrGlyph, fontforge.font):
        return any(svgIsRegistered(g) for g in fontOrGlyph.selection.byGlyphs)
    else:
        return svgIsRegistered(fontOrGlyph)


def _selectedGlyphs(fontOrGlyph: fontforge.font | fontforge.glyph) -> list[fontforge.glyph]:
    if isinstance(fontOrGlyph, fontforge.font):
        return [g for g in fontOrGlyph.selection.byGlyphs]
    else:
        return [fontOrGlyph]


def _svgPath(filename: str) -> tuple[Path, str]:
    filepath = Path(filename)
    suffix = '.svg'
    if not filepath.is_dir():
        suffix = '.svg.gz' if filepath.suffix == '.gz' else filepath.suffix
        filepath = filepath.parent
    return filepath, suffix


def exportSvgMenu(u, fontOrGlyph: fontforge.font | fontforge.glyph):
    glyphs = _selectedGlyphs(fontOrGlyph)
    if len(glyphs) == 1:
        glyph = glyphs[0]
        if filename := fontforge.saveFilename('Export SVG document', glyph.glyphname + '.svg', "*.{svg,svgz,svg.gz}"):
            exportSvg(glyph, filename)
    elif len(glyphs) > 1:
        if filename := fontforge.saveFilename('Export SVG documents', '*.svg', "*.{svg,svgz,svg.gz}"):
            filepath, suffix = _svgPath(filename)
            for glyph in glyphs:
                try:
                    exportSvg(glyph, filepath.joinpath(Path(glyph.glyphname + suffix)))
                except NoColorGlyphError as e:
                    fontforge.logWarning(str(e))


def importSvgMenu(u, fontOrGlyph: fontforge.font | fontforge.glyph):
    glyphs = _selectedGlyphs(fontOrGlyph)
    if len(glyphs) == 1:
        glyph = glyphs[0]
        if filename := fontforge.openFilename('Import SVG document', glyph.glyphname + '.svg', "*.{svg,svgz,svg.gz}"):
            loadSvg(glyph, filename)
    elif len(glyphs) > 1:
        if filename := fontforge.openFilename('Import SVG documents', '*.svg', "*.{svg,svgz,svg.gz}"):
            filepath, suffix = _svgPath(filename)
            for glyph in glyphs:
                loadSvg(glyph, filepath.joinpath(Path(glyph.glyphname + suffix)))


def deleteSvgMenu(u, fontOrGlyph: fontforge.font | fontforge.glyph):
    for glyph in _selectedGlyphs(fontOrGlyph):
        deleteSvg(glyph)
