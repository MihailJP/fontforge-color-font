Fontforge color font plugin
===========================

FontForge_plugin for color fonts

OpenType color font is the technology used for emoji chiefly, and less
frequently some fun fonts. There are several protocols and their support
varies browser to browser.

Fontforge supports none but with other open-source tools color fonts can
be created. This plugin provides frontend to such tools.

This plugin uses these programs as backend:

- [fonttools](https://github.com/fonttools/fonttools)
- [scour](https://github.com/scour-project/scour) SVG optimizer
- [blackrenderer](https://github.com/fontra/black-renderer) converts `COLR` to SVG
- [nanoemoji](https://github.com/googlefonts/nanoemoji) converts SVGs to `COLR`

This module requires Python 3.10 or later.

Install
-------

```shell
pip3 install fontforge_color_font
```

### Make sure Fontforge Python module is usable

In interactive mode of Python, run:

```python
import fontforge
```

If it raises ``ModuleNotFoundError`` exception, install Fontforge first. If
installed, make sure the build option set that the Python module gets also
installed. If already so, Python interpreter does not recognize the module
path where the required module.

```shell
export PYTHONPATH=/path/to/fontforge/python/module:$PYTHONPATH
```

Usage
-----

### Interactive usage

As a Fontforge plugin, fontforge_color_font adds 'Color Font' submenu to
'Tools' menu which is dedicated for plugins.

- Color Font
  - Open color font...
  - Export color font...
  - Import SVG as color font glyph...
  - Export SVG color font glyph...
  - Delete SVG color font glyph

> [!IMPORTANT]
> Since the plugin feature has been hardly (maybe never) used (hence it can
> be tested not well,) Fontforge may crash especially after a dialog is shown.
> You are advised to back up your font project before use.

#### Open color font

Shows a dialog to open a color font.
`COLR` (both COLRv0 and COLRv1) and `SVG ` tables are supported.

If the font has both `COLR` and `SVG ` tables, which one to read will be asked.

> [!NOTE]
> Reading `SVG ` table may take some minutes in order to split multi-glyph
> SVG documents.

#### Export color font

Shows a dialog where you can set output file name and other options.

- Tables to include, `COLR`, `SVG `, or both
- 'COLR' version: 0 or 1
  - Version 0 is not yet supported.
  - Version 1 supports gradients while version 0 does not.
- SVG compression: Plain or other radio buttons (compression rate)
  - Compressed SVG is not yet supported. Select ‘Plain’ for now.
  - Select ‘Plain’ for uncompressed SVG documents.
  - Aside ‘Plain,’ there is 9 radio buttons.
    Select righter one for more compression,
    lefter one for faster compression.

> [!NOTE]
> Converting SVG glyphs into `COLR` table is so complicated that ‘nanoemoji’
> tool must be used. Compiling a font including `COLR` may take some minutes.
> Also, that tool can generate a TTF anew, but does not support appending
> into an existing TTF. So it is needed to merge the main TTF and the
> `COLR`-only one using fonttools.

#### Import SVG as color font glyph

Reads an SVG document and stores into glyph metadata.

This menu is available both in font view and in (spline) glyph view.
In glyph view, select an SVG document.
Nominal width should match with glyph advance width, nominal height with
`hhea` ascender plus absolute value of `hhea` descender.
In font view and if single glyph is selected, does the same thing
as in glyph view.
If multiple glyphs are selected, select a directory.
SVG documents must be named same as glyph name except:

- uppercase letters other than code points (uniXXXX, uXXXXX, or u10XXXX):
  to work with case-insensitive file systems, an underscore must precede
- underscore itself: another underscore must precede for disambiguation
- same name as DOS/Windows reserved file names

For color glyph definitions, some SVG capability is prohibited.
[See Microsoft Typography site for details.][1]

SVG data is stored in `glyph.persistent['SVG']`.
If there is already non-`dict` `glyph.persistent`,
it is **deleted without warning.**

Compressed SVG is not yet supported.

> [!IMPORTANT]
> Due to Fontforge limitation, there is no way to show color glyphs
> in font view. In glyph view, background object can have color bitmap
> pictures, but through scripts cannot place at specified coordinates.
> Another problem in this case is that SVG must be rasterized into PNG
> with some tool (like ImageMagick.)

[1]: https://learn.microsoft.com/en-us/typography/opentype/spec/svg#svg-capability-requirements-and-restrictions

#### Export SVG color font glyph

Exports SVG stored in `glyph.persistent['SVG']`.

This menu is available both in font view and in (spline) glyph view.
Behaves similarly to “Import SVG as color font glyph” menu.

#### Delete SVG color font glyph

Deletes color glyph SVG.

This menu is available both in font view and in (spline) glyph view.
Behaves similarly to “Import SVG as color font glyph” menu.

> [!WARNING]
> You will see **no warning** before deletion.

### Hooks

This plugin installs new/open font hooks which does:

- sets font generation hooks to output color glyphs if exist
  - Not yet implemented
- loads color glyph data if available
  - If you load a color font from the ordinary ‘load’ menu, `COLR` table is
    preferred over `SVG `.

> [!NOTE]
> These hooks work in interactive mode only.

### Script usage

As a Python module, in addition to `fontforge` module, scripting to export
variable fonts from SFD projects will be possible.

```python
import fontforge
import fontforge_color_font

# Open color font
font = fontforge_color_font.loadColorFont('MyColorFont.sfd')
font = fontforge_color_font.loadColorFont('MyColorFont.sfd', colrPreferred=False)

# Import SVG
fontforge_color_font.loadSvg(glyph, 'glyph.svg')

# Export SVG
fontforge_color_font.exportSvg(glyph, 'glyph.svg')
fontforge_color_font.exportSvg(glyph, 'glyph.svg', lambda x: x.replace('glyph', '_glyph'))

try:
    fontforge_color_font.exportSvg(glyph, 'glyph.svg')
except NoColorGlyphError:
    pass

# Delete SVG
fontforge_color_font.deleteSvg(glyph)

# Check if color glyph table exists
result = fontforge_color_font.hasColrTable(font)
result = fontforge_color_font.hasSvgTable(font)

# Check if color glyph SVG is stored
result = fontforge_color_font.svgIsRegistered(glyph)

# Export color font
fontforge_color_font.exportColorFont(font, 'MyColorFont.ttf', colr=1, svg=0)
fontforge_color_font.exportColorFont(font, 'MyColorFont.ttf', colr=1, svg=0, flags=('no-mac-names', 'opentype'))
```
