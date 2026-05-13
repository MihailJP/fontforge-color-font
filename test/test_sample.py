import pytest
import fontforge


@pytest.mark.parametrize(('data', 'glyphname'), [
    (None, "A"),
    (1, "B"),
    (3, "C"),
    (5, "D"),
    (11, "E"),
])
def test_helloEnable(data, glyphname):
    from fontforge_hello.__main__ import hello, helloEnable
    try:
        font = fontforge.font()
        font.createMappedChar(glyphname)
        assert helloEnable(data, font[glyphname])
        hello(data, font[glyphname])
    finally:
        font.close()
