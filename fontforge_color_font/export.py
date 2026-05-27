from functools import partial
from os import PathLike
from pathlib import Path
import re
from subprocess import run
from tempfile import TemporaryDirectory

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
            fltrFunc = partial(_setSvgGlyphID, glyphid=ttf.getGlyphOrder().index(glyph.glyphname))
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
            ttf['vmtx'].metrics[glyph] = (  # type: ignore
                ttf['vmtx'].metrics[glyphNameConversion[base]][0],  # type: ignore
                ttf['hhea'].ascender - colrttf['glyf'][glyph].yMax,
            )
    else:
        ttf['hmtx'].metrics[glyph] = colrttf['hmtx'].metrics[glyph]
        if 'vmtx' in ttf:
            ttf['vmtx'].metrics[glyph] = (  # type: ignore
                ttf['hhea'].ascender + ttf['OS/2'].sTypoDescender,  # type: ignore
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
    ))  # type: ignore

    glyphs = list(ttf.getGlyphOrder())
    glyphs += colrLayers
    ttf.setGlyphOrder(glyphs)
    for glyph in colrLayers:
        ttf['glyf'][glyph] = colrttf['glyf'][glyph]
        _setMetrics(ttf, colrttf, glyph, glyphNameConversion)


def _copyColrCpal(ttf: ttFont.TTFont, colrttf: ttFont.TTFont, glyphNameConversion: dict[str, str]):
    ttf['COLR'] = colrttf['COLR']
    ttf['CPAL'] = colrttf['CPAL']

    assert ttf['COLR'].version == 0 or ttf['COLR'].version == 1
    if ttf['COLR'].version == 1:
        for b in ttf['COLR'].table.BaseGlyphList.BaseGlyphPaintRecord:
            b.BaseGlyph = glyphNameConversion[b.BaseGlyph]

        ttf['COLR'].table.ClipList.clips = dict(
            (glyphNameConversion[k], v) for k, v in colrttf['COLR'].table.ClipList.clips.items()
        )
    else:
        ttf['COLR'].ColorLayers = dict(
            (glyphNameConversion[k], v) for k, v in colrttf['COLR'].ColorLayers.items()
        )


def _setSVGTable(ttf: ttFont.TTFont, tmpdir: str, glyphNameConversion: dict[str, str], compression: bool):
    assert 'SVG ' not in ttf
    ttf['SVG '] = ttFont.newTable('SVG ')
    ttf['SVG '].__dict__['docList'] = []
    glyphNameInverseConversion = dict((v, k) for k, v in glyphNameConversion.items())
    for gid, glyph in (g for g in enumerate(ttf.getGlyphOrder()) if g[1] in glyphNameInverseConversion):
        with Path(tmpdir, glyphNameInverseConversion[glyph] + '.svg').open() as svg:
            ttf['SVG '].docList.append(
                SVGDocument(svg.read(), gid, gid, compression)
            )


def _checkColrParam(colr) -> bool:
    if not isinstance(colr, int):
        raise TypeError('colr must be an int')
    elif colr == -1:
        return False
    elif colr == 0 or colr == 1:
        return True
    else:
        raise ValueError('invalid version of COLR')


def _checkSvgParam(svg) -> bool:
    if not isinstance(svg, int):
        raise TypeError('svg must be an int')
    elif svg == -1:
        return False
    elif 0 <= svg <= 1:
        return True
    else:
        raise ValueError('invalid parameter of SVG')


def exportColorFont(
    font: fontforge.font,
    target: str | PathLike,
    *,
    colr: int = -1,
    svg: int = -1,
    **options,
):
    """Export color font

    Export the color TTF with ``COLR`` and/or ``SVG `` tables.

    ``COLR`` table is so complicated that this plugin requires "nanoemoji" tool to add it.

    :param font: Fontforge font object
    :param target: TTF file to export
    :param colr: version of ``COLR`` table, or -1 to exclude
    :param svg: compression level of gzipped SVG; 0 for uncompressed, 1 for compressed. \
      -1 to exclude ``SVG `` table
    :param options: other options passed to ``fontforge.font.generate()``
    :raises ValueError: wrong extention is specified
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
            _setSVGTable(ttf, tmpdir, glyphNameConversion, svg == 1)

        ttf.save(str(target))


def exportColorFontMenu(u, font: fontforge.font):
    ans = fontforge.askMulti(
        'Export color font',
        [
            {
                'type': 'savepath',
                'question': 'E_xport as:',
                'tag': 'filename',
                'filter': '*.ttf',
            },
            {
                'type': 'choice',
                'question': "'COLR' table:",
                'tag': 'colr',
                'checks': True,
                'answers': [
                    {'name': '_None', 'tag': -1},
                    {'name': 'Version _0', 'tag': 0},
                    {'name': 'Version _1', 'tag': 1, 'default': True},
                ],
            },
            {
                'type': 'choice',
                'question': "'SVG ' table:",
                'tag': 'svg',
                'checks': True,
                'answers': [
                    {'name': 'Non_e', 'tag': -1},
                    {'name': '_Uncompressed', 'tag': 0, 'default': True},
                    {'name': '_Compressed', 'tag': 1},
                ],
            },
        ]
    )

    if ans:
        assert isinstance(ans['filename'], str)
        assert isinstance(ans['colr'], int)
        assert isinstance(ans['svg'], int)
        exportColorFont(font, ans['filename'], colr=ans['colr'], svg=ans['svg'])
