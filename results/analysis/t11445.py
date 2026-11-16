from docutils.statemachine import StringList
from sphinx.util.rst import prepend_prolog
def run(lines):
    c = StringList(lines, "x.rst"); prepend_prolog(c, "PROLOG")
    return list(c)
print("orphan:", run([":orphan:", "", "Title", "====="]))
print("author:", run([":author: Me", "", "Title", "====="]))
print("role  :", run([":mod:`mypackage2`", "=" * 16, "", "Content"]))
