"""Configure Sphinx for the Synthia documentation."""

from datetime import datetime

from synthia import __version__

project = "Synthia"
copyright = f"{datetime.now().year}, Will Roper"
author = "Will Roper"
release = __version__

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
]

autosummary_generate = True
autodoc_inherit_docstrings = True
set_type_checking_flag = True

# Without this the autosummary stubs render a summary table and nothing
# else: no signatures, no Args, no Returns, and napoleon never runs.
autodoc_default_options = {"members": True}

master_doc = "index"

html_theme = "furo"
html_title = "Synthia"
html_show_sourcelink = False
