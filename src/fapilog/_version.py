"""
Fallback version module populated by hatch-vcs during builds.

When building from a Git tag (vX.Y.Z), hatch-vcs writes __version__ here.
For editable or source checkouts without tags, this default keeps imports working.
"""

__version__ = "0.0.0+local"
