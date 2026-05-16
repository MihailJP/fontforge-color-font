import fontforge
from typing import Literal, Callable
from fontTools.ttLib import ttFont
from tempfile import TemporaryDirectory
from subprocess import run
from os import PathLike
from pathlib import Path
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
from sys import stderr


SVG_Magic_Comment = '<!-- FONTFORGE_COLOR_FONT_SVG_READER -->'


def hasSvgTable(font: fontforge.font) -> bool:
    if font.path.endswith('.ttf'):
        with ttFont.TTFont(font.path) as ttf:
            return 'SVG ' in ttf
    else:
        return False


def hasColrTable(font: fontforge.font) -> bool:
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


def _glyphSvgToPng(glyph: fontforge.glyph, svgPath: str | PathLike | None, tmpdir: str):
    pngPath = Path(tmpdir, glyph.glyphname + '.png')
    drawing = svg2rlg(svgPath)
    renderPM.drawToFile(drawing, pngPath, fmt='PNG')
    glyph.importOutlines(str(pngPath))


def glyphSvgToPng(glyph: fontforge.glyph, svgPath: str | PathLike | None = None, tmpdir: str | None = None):
    def writeSvgIfNeeded(svgPath: str | PathLike | None) -> Path:
        if svgPath is None:
            svgfile = Path(tmpdir, glyph.glyphname + '.svg')
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

    :param glyph: a Fontforge glyph object
    :param path: path of SVG file to import
    """
    initGlyphPersistentDict(glyph)
    with Path(svgPath).open() as svg:
        glyph.persistent['SVG'] = svg.read()


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
    head = svg[:(svg.find('>') + 1)]
    body = svg[(svg.find('>') + 1):]
    glyphname = ttf.getGlyphOrder()[glyphid]
    if 'viewBox="' not in head:
        head = head[:-1] + ' viewBox="{} {} {} {}">'.format(
            0,
            -ttf['hhea'].ascender,
            ttf['hmtx'][glyphname][0],
            ttf['hhea'].ascender - ttf['hhea'].descender,
        )
        return head + body
    else:
        return svg


def _separateSVG(ttf: ttFont.TTFont, svg: str, glyphid: int, tmpdir: str):
    glyphname = ttf.getGlyphOrder()[glyphid]
    svgfile = Path(tmpdir, glyphname + '.svg')
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


def loadSvgColorFont(font: fontforge.font):
    if not hasSvgTable(font):
        return
    with TemporaryDirectory() as tmpdir:
        ttf = ttFont.TTFont(font.path)
        print('Dumping into SVG files; this may take some minutes. Please be patient.')
        for doc in ttf['SVG '].docList:
            _separateSVG_thousands(ttf, doc.data, doc.startGlyphID, doc.endGlyphID, tmpdir)
        fontforge.logWarning('Reading SVG files. Please be patient.')
        for glyph in font.glyphs():
            svgPath = Path(tmpdir, glyph.glyphname + '.svg')
            if svgPath.exists():
                loadSvg(glyph, svgPath)
            elif (svgPath := Path(tmpdir, 'glyph' + str(glyph.originalgid).zfill(5) + '.svg')).exists():
                loadSvg(glyph, svgPath)


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
    if hasSvgTable(font):
        if fontforge.ask(
            'SVG color font',
            "This font has 'SVG ' table.\n"
                "This means this is a color font.\n"
                "Import the SVG documents included in the font?\n"
                "This may take some minutes.",
            ('_Yes', '_No'),
            0,
            1,
        ) == 0:
            loadSvgColorFont(font)


def loadHook(font: fontforge.font):
    if font.path.endswith('.ttf'):
        _loadHook_ttf(font)
        _addGenerateHook(font)
    elif font.path.endswith('.sfd'):
        _addGenerateHook(font)


def newFontHook(font: fontforge.font):
    _addGenerateHook(font)
