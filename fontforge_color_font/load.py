from os import PathLike
from pathlib import Path
import re
from subprocess import run
from sys import stderr
from tempfile import TemporaryDirectory
from typing import Callable

from blackrenderer.font import BlackRendererFont
from blackrenderer.backends import getSurfaceClass
import fontforge
from fontTools.ttLib import ttFont
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

from fontforge_plugin_helper import addFontGenerateHook


SVG_Magic_Comment = '<!-- FONTFORGE_COLOR_FONT_SVG_READER -->'


def hasSvgTable(font: fontforge.font) -> bool:
    """Check if the TTF has ``SVG `` table

    :returns: ``True`` if ``font`` is a TTF and has ``SVG `` table
    """

    if font.path.endswith('.ttf'):
        with ttFont.TTFont(font.path) as ttf:
            return 'SVG ' in ttf
    else:
        return False


def hasColrTable(font: fontforge.font) -> bool:
    """Check if the TTF has ``COLR`` table

    :returns: ``True`` if ``font`` is a TTF and has ``COLR`` table
    """

    if font.path.endswith('.ttf'):
        with ttFont.TTFont(font.path) as ttf:
            return 'COLR' in ttf
    else:
        return False


def initGlyphPersistentDict(glyph: fontforge.glyph):
    if glyph.persistent is None:
        glyph.persistent = {}
    elif not isinstance(glyph.persistent, dict):
        fontforge.logWarning('Non-dict persistent object in glyph {} has been dropped'.format(glyph.glyphname))
        glyph.persistent = {}


def escapeGlyphName(glyphname: str) -> str:
    patterns = [
        (r'^uni([0-9A-F])([0-9A-F])([0-9A-F])([0-9A-F])', 'uni\ufdd0\\1\ufdd0\\2\ufdd0\\3\ufdd0\\4'),
        (r'^u([0-9A-F]|10)([0-9A-F])([0-9A-F])([0-9A-F])([0-9A-F])', 'u\ufdd0\\1\ufdd0\\2\ufdd0\\3\ufdd0\\4\ufdd0\\5'),
        (r'([A-Z_])', r'_\1'),
        ('\ufdd0_?', ''),
    ]
    glyphfilename = glyphname
    for pat, rpl in patterns:
        glyphfilename = re.sub(pat, rpl, glyphfilename)
    return glyphfilename


def _glyphSvgToPng(glyph: fontforge.glyph, svgPath: str | PathLike | None, tmpdir: str):
    pngPath = Path(tmpdir, escapeGlyphName(glyph.glyphname) + '.png')
    drawing = svg2rlg(svgPath)
    renderPM.drawToFile(drawing, pngPath, fmt='PNG')
    glyph.importOutlines(str(pngPath))


def glyphSvgToPng(glyph: fontforge.glyph, svgPath: str | PathLike | None = None, tmpdir: str | None = None):
    def writeSvgIfNeeded(svgPath: str | PathLike | None) -> Path:
        if svgPath is None:
            svgfile = Path(tmpdir, escapeGlyphName(glyph.glyphname) + '.svg')
            with svgfile.open('w') as f:
                f.write(glyph.persistent['SVG'])
            return svgfile
        else:
            return Path(svgPath)

    if tmpdir:
        _glyphSvgToPng(glyph, writeSvgIfNeeded(svgPath), tmpdir)
    else:
        with TemporaryDirectory() as td:
            _glyphSvgToPng(glyph, writeSvgIfNeeded(svgPath), td)


def loadSvg(glyph: fontforge.glyph, svgPath: str | PathLike):
    """Imports color glyph SVG

    Imports color glyph SVG and stores into ``glyph.persistent['SVG']``.

    SVG will be simplified using scour before being stored.

    Although SVG is scalable as the name suggests, nominal size can be set
    (usually aspect ratio is more important than width and height themselves.)
    This plugin assumes that nominal width equals to the advance width (``glyph.width``) and
    nominal height equals to ``hhea`` ascender plus absolute value of ``hhea`` descender.
    Note that changes of those values will not reflect to the SVG.

    Fontforge itself does not have capabilities editing color SVG; do it with dedicated tools like Inkscape.

    Some capabilities of SVG are prohibited for color glyph definition.
    See details at:
    https://learn.microsoft.com/en-us/typography/opentype/spec/svg#svg-capability-requirements-and-restrictions

    :param glyph: a Fontforge glyph object
    :param path: path of SVG file to import
    :raises ValueError: wrong extension is specified
    :raises NotImplementedError: compressed SVG is not yet implemented
    """
    initGlyphPersistentDict(glyph)
    if svgPath.endswith('.svg'):
        with Path(svgPath).open() as svg:
            svg = svg.read()
    elif svgPath.endswith('.svgz') or svgPath.endswith('.svg.gz'):
        raise NotImplementedError('compressed SVG is not yet implemented')
    else:
        raise ValueError('the extension must be .svg, .svgz, or .svg.gz')
    glyph.persistent['SVG'] = svg[svg.find('<svg'):]


def _getPartSVG(svg: str, glyphIDs: int | range):
    header = svg[:(svg.find('>') + 1)]
    body = svg[(svg.find('>') + 1):]
    if isinstance(glyphIDs, range):
        use = ''.join(
            '<use xlink:href="#glyph{}" />'.format(g) for g in glyphIDs
        )
    else:
        use = '<use xlink:href="#glyph{}" />'.format(glyphIDs)
    if SVG_Magic_Comment in body:
        body = body.replace(SVG_Magic_Comment, '')
        body = body[:(body.find('</defs>') + 7)] + '</svg>'
    else:
        body = body.replace('</defs>', '')
        body = body.replace('</svg>', '</defs></svg>')
    return header + SVG_Magic_Comment + body.replace('</svg>', use + '</svg>')


def _hasMultipleGlyph(svg: str) -> bool:
    if 'id="glyph' in svg:
        return 'id="glyph' in svg[(svg.find('id="glyph') + 9):]
    else:
        return False


def _setSVGSize(ttf: ttFont.TTFont, svg: str, glyphid: int) -> str:
    def fixHeader(head: str, tag: str, val: str) -> str:
        if (tag + '="') not in head:
            return head[:-1] + ' {}="{}">'.format(tag, val)
        else:
            return head

    head = svg[:(svg.find('>') + 1)]
    body = svg[(svg.find('>') + 1):]
    glyphname = ttf.getGlyphOrder()[glyphid]
    head = fixHeader(head, 'viewBox', ' '.join([
        '0',
        str(-ttf['hhea'].ascender),
        str(ttf['hmtx'][glyphname][0]),
        str(ttf['hhea'].ascender - ttf['hhea'].descender),
    ]))
    head = fixHeader(head, 'viewBox', ' '.join([
        '0',
        str(-ttf['hhea'].ascender),
        str(ttf['hmtx'][glyphname][0]),
        str(ttf['hhea'].ascender - ttf['hhea'].descender),
    ]))
    head = fixHeader(head, 'width', str(ttf['hmtx'][glyphname][0]))
    head = fixHeader(head, 'height', str(ttf['hhea'].ascender - ttf['hhea'].descender))
    return head + body


def _separateSVG(ttf: ttFont.TTFont, svg: str, glyphid: int, tmpdir: str):
    glyphname = ttf.getGlyphOrder()[glyphid]
    svgfile = Path(tmpdir, escapeGlyphName(glyphname) + '.svg')
    if _hasMultipleGlyph(svg):
        newsvg = _setSVGSize(ttf, _getPartSVG(svg, glyphid), glyphid)
    elif 'id="glyph' in svg:
        newsvg = _setSVGSize(ttf, svg, glyphid)
    run(
        [
            'scour', '-o', svgfile,
            '--strip-xml-prolog',
            '--remove-descriptive-elements',
            '--enable-comment-stripping',
        ],
        check=True,
        input=newsvg,
        text=True
    )


def _separateSVG_subsep(
    ttf: ttFont.TTFont,
    svg: str,
    startGlyphID: int,
    endGlyphID: int,
    tmpdir: str,
    separateIfGreater: int,
    separateBy: int,
    f: Callable[[ttFont.TTFont, str, int, int, str], None],
):
    if 'id="glyph' not in svg:
        return
    if endGlyphID - startGlyphID > separateIfGreater:
        for start in range(startGlyphID, endGlyphID + 1, separateBy):
            end = min(start + separateBy - 1, endGlyphID)
            newsvg = _getPartSVG(svg, range(start, end + 1))
            result = run([
                'scour',
                '--strip-xml-prolog',
                '--disable-simplify-colors',
                '--disable-style-to-xml',
                '--disable-group-collapsing',
            ], check=True, input=newsvg, capture_output=True, text=True)
            stderr.write(result.stderr)
            f(ttf, result.stdout, start, end, tmpdir)
    else:
        f(ttf, svg, startGlyphID, endGlyphID, tmpdir)


def _separateSVG_ones(ttf: ttFont.TTFont, svg: str, startGlyphID: int, endGlyphID: int, tmpdir: str):
    for gid in range(startGlyphID, endGlyphID + 1):
        _separateSVG(ttf, svg, gid, tmpdir)


def _separateSVG_tens(ttf: ttFont.TTFont, svg: str, startGlyphID: int, endGlyphID: int, tmpdir: str):
    _separateSVG_subsep(ttf, svg, startGlyphID, endGlyphID, tmpdir, 20, 10, _separateSVG_ones)


def _separateSVG_hundreds(ttf: ttFont.TTFont, svg: str, startGlyphID: int, endGlyphID: int, tmpdir: str):
    _separateSVG_subsep(ttf, svg, startGlyphID, endGlyphID, tmpdir, 150, 100, _separateSVG_tens)


def _separateSVG_fiveHundreds(ttf: ttFont.TTFont, svg: str, startGlyphID: int, endGlyphID: int, tmpdir: str):
    _separateSVG_subsep(ttf, svg, startGlyphID, endGlyphID, tmpdir, 500, 500, _separateSVG_hundreds)


def _separateSVG_thousands(ttf: ttFont.TTFont, svg: str, startGlyphID: int, endGlyphID: int, tmpdir: str):
    _separateSVG_subsep(ttf, svg, startGlyphID, endGlyphID, tmpdir, 1000, 1000, _separateSVG_fiveHundreds)


def _checkIfColrGlyphExists(ttf: ttFont.TTFont, glyphname: str) -> bool:
    if 'COLR' not in ttf:
        return False
    elif ttf['COLR'].version == 0:
        return glyphname in ttf['COLR'].__dict__
    elif ttf['COLR'].version == 1:
        return bool([g for g in ttf['COLR'].table.BaseGlyphList.BaseGlyphPaintRecord if g.BaseGlyph == glyphname])
    else:
        return False


def _colr2svg(font: fontforge.font, tmpdir: str):
    ttf = ttFont.TTFont(font.path)
    print('Dumping into SVG files; this may take some time. Please be patient.')
    f = BlackRendererFont(font.path)
    for glyphname in [g for g in ttf.getGlyphOrder() if _checkIfColrGlyphExists(ttf, g)]:
        canvasPos = (
            0,
            ttf['hhea'].descender,
            ttf['hmtx'][glyphname][0],
            ttf['hhea'].ascender,
        )
        surfaceClass = getSurfaceClass('svg')
        surface = surfaceClass()
        with surface.canvas(canvasPos) as canvas:
            f.drawGlyph(glyphname, canvas)
        surface.saveImage(str(Path(tmpdir, escapeGlyphName(glyphname) + '.svg')))


def _importSvg(font: fontforge.font, tmpdir: str):
    fontforge.logWarning('Reading SVG files. Please be patient.')
    for glyph in font.glyphs():
        svgPath = Path(tmpdir, escapeGlyphName(glyph.glyphname) + '.svg')
        if svgPath.exists():
            loadSvg(glyph, svgPath)
        elif (svgPath := Path(tmpdir, 'glyph' + str(glyph.originalgid).zfill(5) + '.svg')).exists():
            loadSvg(glyph, svgPath)


def loadColrColorFontMetadata(font: fontforge.font):
    """Read ``COLR`` table

    Convert ``COLR`` table into SVG and store into ``glyph.persistent['SVG']``.
    If ``font`` is not a TTF or there is not ``COLR`` table, does nothing.

    This function is called from ``loadColorFont()``.

    This is done with blackrenderer. Supports both COLRv0 and COLRv1."""
    if not hasColrTable(font):
        return
    with TemporaryDirectory() as tmpdir:
        _colr2svg(font, tmpdir)
        _importSvg(font, tmpdir)


def loadSvgColorFontMetadata(font: fontforge.font):
    """Read ``SVG `` table

    Read ``SVG `` table from TTF and store into ``glyph.persistent['SVG']``.
    If ``font`` is not a TTF or there is not ``SVG `` table, does nothing.

    An SVG document may contain multiple glyphs.
    This plugin will split using scour; this may take some minutes.

    This function is called from ``loadColorFont()``.

    :raises NotImplementedError: compressed SVG is not yet implemented
    """

    if not font.path.endswith('.ttf'):
        return
    if not hasSvgTable(font):
        return
    with TemporaryDirectory() as tmpdir:
        ttf = ttFont.TTFont(font.path)
        print('Dumping into SVG files; this may take some minutes. Please be patient.')
        for doc in ttf['SVG '].docList:
            if doc.compressed:
                raise NotImplementedError('compressed SVG is not yet implemented')
            else:
                svg = doc.data
            _separateSVG_thousands(ttf, svg, doc.startGlyphID, doc.endGlyphID, tmpdir)
        _importSvg(font, tmpdir)


def loadColorFont(fontfile: PathLike | str, flags=None, *, colrPreferred=True) -> fontforge.font:
    """Load color font

    :param fontfile: font file to load
    :param flags: flags passed to ``fontforge.open()``
    :param colrPreferred: ``True`` to prefer ``COLR`` if the font has both ``COLR`` and ``SVG `` tables
    """
    font = fontforge.open(str(fontfile), flags)
    if hasSvgTable(font) and hasColrTable(font) and colrPreferred:
        loadColrColorFontMetadata(font)
    elif hasSvgTable(font):
        loadSvgColorFontMetadata(font)
    elif hasColrTable(font):
        loadColrColorFontMetadata(font)
    return font


def _generatePreHook(font: fontforge.font, target: str):
    pass


def _generatePostHook(font: fontforge.font, target: str):
    pass


def _addGenerateHook(font: fontforge.font):
    addFontGenerateHook(font, 'generateFontPreHook', _generatePreHook)
    addFontGenerateHook(font, 'generateFontPostHook', _generatePostHook)


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
    if font.path.endswith('.ttf'):
        _loadHook_ttf(font)
        _addGenerateHook(font)
    elif font.path.endswith('.sfd'):
        _addGenerateHook(font)


def newFontHook(font: fontforge.font):
    _addGenerateHook(font)
