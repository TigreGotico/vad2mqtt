VERSION_MAJOR = 0
VERSION_MINOR = 1
VERSION_BUILD = 0
VERSION_ALPHA = 1

# Auto-calculate __version__
_ver = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_BUILD}"
if VERSION_ALPHA:
    _ver += f"a{VERSION_ALPHA}"
__version__ = _ver
