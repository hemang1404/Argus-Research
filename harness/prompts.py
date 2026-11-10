"""Frozen prompt for the bare one-shot arm (no tests shown, no hints_text, no gold information)."""
import hashlib

SYSTEM = (
    "You are an expert Python engineer. You will be given a bug report or feature request for a software "
    "repository and the content of one source file (possibly with parts omitted). Produce the minimal code change "
    "that resolves the issue.\n\n"
    "Output format: one or more SEARCH/REPLACE blocks, nothing else except optional brief reasoning before them. "
    "Each block must look exactly like this:\n\n"
    "### File: <path>\n"
    "<<<<<<< SEARCH\n"
    "<exact lines copied from the file, enough to identify one location>\n"
    "=======\n"
    "<the replacement lines>\n"
    ">>>>>>> REPLACE\n\n"
    "Rules: copy SEARCH lines exactly as they appear in the file, including indentation; do not include line numbers; "
    "SEARCH text must come from the code shown; keep the change as small as possible."
)

USER_TMPL = (
    "Repository: {repo}\n"
    "File to modify: {path}\n\n"
    "## Issue\n{issue}\n\n"
    "## Current content of {path}\n```python\n{code}\n```\n\n"
    "Write the SEARCH/REPLACE block(s) that fix the issue."
)

PROMPT_VERSION = "p1"


def build_messages(task, path, code, issue_max_chars=6000):
    issue = task["problem_statement"]
    if len(issue) > issue_max_chars:
        issue = issue[:issue_max_chars] + "\n[... issue truncated ...]"
    user = USER_TMPL.format(repo=task["repo"], path=path, issue=issue, code=code)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def prompt_hash():
    return hashlib.sha256((SYSTEM + USER_TMPL + PROMPT_VERSION).encode()).hexdigest()[:12]
