import fontforge
from fontTools.ttLib import ttFont
from os import PathLike
from pathlib import Path
from tempfile import TemporaryDirectory
from subprocess import run
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


def _exportSVGGlyphs(font: fontforge.font, tmpdir: str) -> tuple[dict[str, str], list[Path]]:
    colorGlyphs = [g for g in font.glyphs() if svgIsRegistered(g)]
    glyphNameConversion = {}
    svgFiles = []
    for i, glyph in enumerate(colorGlyphs):
        tmpGlyphName = 'u{:05X}'.format(i + 0xf0000)
        glyphNameConversion[tmpGlyphName] = glyph.glyphname
        svgFile = Path(tmpdir, tmpGlyphName + '.svg')
        exportSvg(glyph, svgFile)
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


def colorFontProcess(font: fontforge.font, target: str | PathLike):
    if not str(target).endswith('.ttf'):
        return

    font.generate(str(target))
    ttf = ttFont.TTFont(target)
    ascent = ttf['hhea'].ascent
    descent = ttf['hhea'].descent
    assert descent <= 0

    with TemporaryDirectory() as tmpdir:
        glyphNameConversion, svgFiles = _exportSVGGlyphs(font, tmpdir)
        run([
            'nanoemoji',
            '--color_format', 'glyf_colr_1',
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

        ttf.save(target)


def testSvgMenu(u, font: fontforge.font):
    colorFontProcess(font, 'test.ttf')
