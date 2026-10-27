"""The product's name, in one place. Renaming the product is a change to BRAND here.

Pages get it through the {{BRAND}} placeholder (metalesionlab/web/site.py fills it in when a page is
served), the browser through window.TOT.BRAND (common.js reads it from the page), and Python code
(PDF reports, exports, the Ask the Lab agent, the guard's messages) by importing it.
"""

BRAND = "Tippa Lingua"
# One line under the name in the site header, and the default share text.
TAGLINE = "What would Plato ask an AI?"
