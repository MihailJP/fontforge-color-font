from functools import partial, Placeholder
from os import PathLike
from pathlib import Path
import re
from subprocess import run
from tempfile import TemporaryDirectory
from typing import Literal

import fontforge
from fontTools.ttLib import ttFont
from fontTools.ttLib.tables.S_V_G_ import SVGDocument

from .svg import svgIsRegistered, exportSvg


def _getGlyphNameFromPaint(paint) -> str | None:
    if hasattr(paint, 'Glyph'):
        return paint.Glyph
    elif not hasattr(paint, 'Paint'):
        return None
    elif hasattr(paint.Paint, 'Glyph'):
        return paint.Paint.Glyph
    else:
        return None


def _setSvgGlyphID(svg: str, glyphid: int) -> str:
    svg2 = svg[(svg.find('<svg')):]
    head = svg2[:(svg2.find('>') + 1)]
    body = svg2[(svg2.find('>') + 1):]
    head = re.sub(r'\bid="[^"]*"', '', head)
    body = body.replace('glyph', '_glyph')
    head = head.replace('<svg', '<svg id="glyph{}"'.format(glyphid))
    return head + body


def _exportSVGGlyphs(font: fontforge.font, ttf: ttFont.TTFont, tmpdir: str) -> tuple[dict[str, str], list[Path]]:
    colorGlyphs = [g for g in font.glyphs() if svgIsRegistered(g)]
    glyphNameConversion = {}
    svgFiles = []
    for i, glyph in enumerate(colorGlyphs):
        tmpGlyphName = 'u{:05X}'.format(i + 0xf0000)
        glyphNameConversion[tmpGlyphName] = glyph.glyphname
        svgFile = Path(tmpdir, tmpGlyphName + '.svg')
        if glyph.glyphname in ttf.getGlyphOrder():
            fltrFunc = partial(_setSvgGlyphID, Placeholder, ttf.getGlyphOrder().index(glyph.glyphname))
        else:
            fltrFunc = None
        exportSvg(glyph, svgFile, fltrFunc)
        svgFiles.append(svgFile)
    return (glyphNameConversion, svgFiles)


def _searchBase(ttf: ttFont.TTFont, glyph: str) -> str | None:
    for base in ttf['COLR'].table.BaseGlyphList.BaseGlyphPaintRecord:
        if hasattr(base, 'Paint'):
            if (g := _getGlyphNameFromPaint(base.Paint)) and g == glyph:
                return base.BaseGlyph
            if hasattr(base.Paint, 'NumLayers') and hasattr(base.Paint, 'FirstLayerIndex'):
                layerRange = slice(
                    base.Paint.FirstLayerIndex,
                    base.Paint.FirstLayerIndex + base.Paint.NumLayers,
                )
                for p in ttf['COLR'].table.LayerList.Paint[layerRange]:
                    if (g := _getGlyphNameFromPaint(p)) and g == glyph:
                        return base.BaseGlyph
    return None


def _setMetrics(ttf: ttFont.TTFont, colrttf: ttFont.TTFont, glyph: str, glyphNameConversion: dict[str, str]):
    if base := _searchBase(colrttf, glyph):
        targetWidth = ttf['hmtx'].metrics[glyphNameConversion[base]][0]
        sourceWidth, sourceLsb = colrttf['hmtx'].metrics[glyph]
        ttf['hmtx'].metrics[glyph] = (
            targetWidth,
            int(sourceLsb - (sourceWidth - targetWidth) / 2),
        )
        if 'vmtx' in ttf:
            ttf['vmtx'].metrics[glyph] = (
                ttf['vmtx'].metrics[glyphNameConversion[base]][0],
                ttf['hhea'].ascender - colrttf['glyf'][glyph].yMax,
            )
    else:
        ttf['hmtx'].metrics[glyph] = colrttf['hmtx'].metrics[glyph]
        if 'vmtx' in ttf:
            ttf['vmtx'].metrics[glyph] = (
                ttf['hhea'].ascender + ttf['OS/2'].sTypoDescender,
                ttf['hhea'].ascender - colrttf['glyf'][glyph].yMax,
            )


def _copyColrGlyphs(ttf: ttFont.TTFont, colrttf: ttFont.TTFont, glyphNameConversion: dict[str, str]):
    colrLayers = sorted(set(
        _getGlyphNameFromPaint(p) for p in
        colrttf['COLR'].table.LayerList.Paint if
        _getGlyphNameFromPaint(p)
    ) | set(
        _getGlyphNameFromPaint(b.Paint) for b in
        colrttf['COLR'].table.BaseGlyphList.BaseGlyphPaintRecord if
        hasattr(b, 'Paint') and _getGlyphNameFromPaint(b.Paint)
    ))

    glyphs = list(ttf.getGlyphOrder())
    glyphs += colrLayers
    ttf.setGlyphOrder(glyphs)
    for glyph in colrLayers:
        ttf['glyf'][glyph] = colrttf['glyf'][glyph]
        _setMetrics(ttf, colrttf, glyph, glyphNameConversion)


def _copyColrCpal(ttf: ttFont.TTFont, colrttf: ttFont.TTFont, glyphNameConversion: dict[str, str]):
    ttf['COLR'] = colrttf['COLR']
    ttf['CPAL'] = colrttf['CPAL']

    for b in ttf['COLR'].table.BaseGlyphList.BaseGlyphPaintRecord:
        b.BaseGlyph = glyphNameConversion[b.BaseGlyph]

    ttf['COLR'].table.ClipList.clips = dict(
        (glyphNameConversion[k], v) for k, v in colrttf['COLR'].table.ClipList.clips.items()
    )


def _setSVGTable(ttf: ttFont.TTFont, tmpdir: str, glyphNameConversion: dict[str, str]):
    assert 'SVG ' not in ttf
    ttf['SVG '] = ttFont.newTable('SVG ')
    ttf['SVG '].__dict__['docList'] = []
    glyphNameInverseConversion = dict((v, k) for k, v in glyphNameConversion.items())
    for gid, glyph in (g for g in enumerate(ttf.getGlyphOrder()) if g[1] in glyphNameInverseConversion):
        with Path(tmpdir, glyphNameInverseConversion[glyph] + '.svg').open() as svg:
            ttf['SVG '].docList.append(
                SVGDocument(svg.read(), gid, gid)
            )


def _checkColrParam(colr) -> bool:
    if colr is None:
        return False
    if not isinstance(colr, int):
        raise TypeError('colr must be an int or None')
    elif colr == 0:
        raise NotImplementedError('COLR v0 is not supported yet')
    elif colr == 1:
        return True
    else:
        raise ValueError('invalid version of COLR')


def _checkSvgParam(svg) -> bool:
    if svg is None:
        return False
    if not isinstance(svg, int):
        raise TypeError('svg must be an int or None')
    elif svg == 0:
        return True
    elif 1 <= svg <= 9:
        raise NotImplementedError('compressed SVG is not supported yet')
    else:
        raise ValueError('invalid parameter of SVG')


def exportColorFont(
    font: fontforge.font,
    target: str | PathLike,
    *,
    colr: Literal[0, 1] | None = None,
    svg: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | None = None,
    **options,
):
    """Export color font

    Export the color TTF with ``COLR`` and/or ``SVG `` tables.

    ``COLR`` table is so complicated that this plugin requires "nanoemoji" tool to add it.

    :param font: Fontforge font object
    :param target: TTF file to export
    :param colr: version of ``COLR`` table, or ``None`` to exclude
    :param svg: compression level of gzipped SVG; 0 for uncompressed, 1 for fast but least compressed, \
        9 for most compressed but slow. ``None`` to exclude ``SVG `` table
    :param options: other options passed to ``fontforge.font.generate()``
    :raises ValueError: wrong extention is specified
    :raises NotImplementedError: COLR v0 and compressed SVG are not yet supported
    """

    if not str(target).endswith('.ttf'):
        raise ValueError('wrong extention')

    with TemporaryDirectory() as tmpdir:
        tmpTtfPath = Path(tmpdir, 'tmp.ttf')
        font.generate(str(tmpTtfPath), **options)
        ttf = ttFont.TTFont(str(tmpTtfPath))
        ascent = ttf['hhea'].ascent
        descent = ttf['hhea'].descent
        assert descent <= 0

        glyphNameConversion, svgFiles = _exportSVGGlyphs(font, ttf, tmpdir)

        if _checkColrParam(colr):
            run([
                'nanoemoji',
                '--color_format', 'glyf_colr_' + str(colr),
                '--build_dir', str(Path(tmpdir, 'build')),
                '--noclip_to_viewbox',
                '--ascender', str(ascent),
                '--descender', str(descent),
                '--upem', str(ascent - descent),
            ] + [str(p) for p in svgFiles], check=True)
            # Path(tmpdir, 'build', 'Font.ttf').copy(Path('testxp.ttf'))  # debug

            colrttf = ttFont.TTFont(Path(tmpdir, 'build', 'Font.ttf'))
            _copyColrGlyphs(ttf, colrttf, glyphNameConversion)
            _copyColrCpal(ttf, colrttf, glyphNameConversion)

        if _checkSvgParam(svg):
            _setSVGTable(ttf, tmpdir, glyphNameConversion)

        ttf.save(str(target))


def testSvgMenu(u, font: fontforge.font):
    exportColorFont(font, 'test.ttf')


def exportColorFontMenu(u, font: fontforge.font):
    def valOrNone(enabled: bool, x: int) -> int | None:
        return x if enabled else None

    ans = fontforge.askMulti(
        'Export color font',
        [
            {
                'type': 'savepath',
                'question': 'Export as:',
                'tag': 'filename',
                'filter': '*.ttf',
            },
            {
                'type': 'choice',
                'tag': 'tags',
                'checks': True,
                'answers': [
                    {'name': "'COLR'", 'tag': 'COLR', 'default': True},
                    {'name': "'SVG '", 'tag': 'SVG', 'default': True},
                ],
                'multiple': True,
            },
            {
                'type': 'choice',
                'question': "'COLR' version:",
                'tag': 'colr',
                'checks': True,
                'answers': [
                    {'name': '0', 'tag': 0},
                    {'name': '1', 'tag': 1, 'default': True},
                ],
            },
            {
                'type': 'choice',
                'question': "SVG compression:",
                'tag': '_svg',
                'checks': True,
                'answers': [],
            },
            {
                'type': 'choice',
                'tag': 'svg',
                'checks': True,
                'answers': [
                    {'name': 'Plain', 'tag': 0, 'default': True},
                    {'name': '', 'tag': 1},
                    {'name': '', 'tag': 2},
                    {'name': '', 'tag': 3},
                    {'name': '', 'tag': 4},
                    {'name': '', 'tag': 5},
                    {'name': '', 'tag': 6},
                    {'name': '', 'tag': 7},
                    {'name': '', 'tag': 8},
                    {'name': 'Max', 'tag': 9},
                ],
            },
        ]
    )

    if ans:
        exportColorFont(
            font,
            ans['filename'],
            colr=valOrNone('COLR' in ans['tags'], ans['colr']),
            svg=valOrNone('SVG' in ans['tags'], ans['svg'])
        )
