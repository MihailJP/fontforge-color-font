Fontforge plugin template
=========================

Description here

Install
-------

```shell
pip3 install fontforge_hello
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

Explanation here
