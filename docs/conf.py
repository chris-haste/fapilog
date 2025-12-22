# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
import importlib.util
import sys
import warnings
from pathlib import Path

# Add the project root to the Python path for autodoc
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# -- Project information -----------------------------------------------------

project = "fapilog"
copyright = "2024, Chris Haste"
author = "Chris Haste"

# The master toctree document.
master_doc = "index"

# The full version, including alpha/beta/rc tags


def get_version() -> str:
    """Resolve version for docs (env > package > fallback)."""
    import os

    env_version = os.getenv("FAPILOG_DOC_VERSION")
    if env_version:
        return env_version

    try:
        import fapilog

        return getattr(fapilog, "__version__", "0.0.0")
    except Exception:
        return "0.0.0"


release = get_version()
version = get_version()

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "myst_parser",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
]

# Optional extensions
if importlib.util.find_spec("sphinxcontrib.mermaid"):
    extensions.append("sphinxcontrib.mermaid")
else:
    warnings.warn(
        "sphinxcontrib.mermaid not installed; mermaid diagrams will be rendered as code blocks.",
        stacklevel=2,
    )

# MyST Parser configuration
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "html_admonition",
    "html_image",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]

# Napoleon settings for Google/NumPy style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_use_keyword = True
napoleon_custom_sections = None

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
    "show-signature": True,
    "autosummary": True,
}

# Additional autodoc settings for comprehensive API docs
autodoc_member_order = "bysource"
autodoc_preserve_defaults = True
autodoc_inherit_docstrings = True
autodoc_class_signature = "separated"
autodoc_warningiserror = False

# Type hints configuration
autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_typehints_description_target = "documented"

# Intersphinx mapping for external references
intersphinx_mapping = {}

# Todo configuration
todo_include_todos = True

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "sphinx_rtd_theme"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    "navigation_depth": 2,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": True,
    "style_nav_header_background": "#2980B9",
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Custom CSS for additional styling
html_css_files = [
    "custom.css",
]

# Custom JavaScript for additional functionality
html_js_files = [
    "custom.js",
]

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = None

# The name of an image file (relative to this directory) to use as a favicon of
# the docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = None

# Exclude large sets of drafts/roadmap docs from builds to reduce warnings
exclude_patterns = [
    "**/*.md.md",
    "architecture/**",
    "prd/**",
    "stories/**",
    "style-guide.md",
    "INFRASTRUCTURE_SETUP.md",
    "README.md",
    "ci-configuration.md",
    "milestones.md",
    "v3-migration-plan.md",
    "v2-excellence-preservation.md",
    "architecture.md",
    "architecture-diagrams.md",
    "contributing.md",
    "documentation-guide-for-contributors.md",
    "documentation-structure.md",
    "glossary.md",
    "install-and-update.md",
    "license-credits.md",
    "prd.md",
    "roadmap.md",
    "FUTURE-CLI.md",
]

# If not None, a 'Last updated on:' timestamp is inserted at every page
# bottom, using the given strftime format.
html_last_updated_fmt = "%B %d, %Y"

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
html_sidebars = {
    "**": [
        "globaltoc.html",
        "relations.html",
        "sourcelink.html",
        "searchbox.html",
    ]
}

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "fapilogdoc"

# -- Options for LaTeX output ------------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    "papersize": "a4paper",
    # The font size ('10pt', '11pt' or '12pt').
    "pointsize": "11pt",
    # Additional stuff for the LaTeX preamble.
    "preamble": "",
    # Latex figure (float) alignment
    "figure_align": "htbp",
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, "fapilog.tex", "fapilog Documentation", "Chris Haste", "manual"),
]

# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, "fapilog", "fapilog Documentation", [author], 1),
]

# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "fapilog",
        "fapilog Documentation",
        author,
        "fapilog",
        "Revolutionary async-first logging library for Python applications",
        "Miscellaneous",
    ),
]

# -- Options for Epub output -------------------------------------------------

epub_title = project
epub_author = author
epub_publisher = author
epub_copyright = copyright

# The basename for the epub file. It defaults to the project name.
epub_basename = project

# -- Extension configuration -------------------------------------------------

# Copy button configuration
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True

# -- Source file configuration -----------------------------------------------

# The suffix of source filenames. Restrict to Markdown only.
source_suffix = {
    ".md": "markdown",
}

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
# Merge default ignore patterns with custom ones
exclude_patterns = exclude_patterns + [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "*.pyc",
    "__pycache__",
    ".venv",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
    "coverage.xml",
]

# The reST default role (used for this markup: `text`) to use for all
# documents.
default_role = "any"

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ["fapilog."]

# If true, keep warnings as "system message" paragraphs in the built documents.
keep_warnings = False

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# -- Custom configuration ----------------------------------------------------


# Add any custom configuration here
def setup(app):
    """Custom setup for Sphinx app."""
    # Add custom autodoc extension
    import os
    import sys

    sys.path.insert(0, os.path.dirname(__file__))

    try:
        from custom_autodoc import setup as custom_setup

        custom_setup(app)
    except ImportError as e:
        app.warn(f"Could not load custom_autodoc extension: {e}")
