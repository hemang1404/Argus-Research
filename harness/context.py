"""Build the code context shown to the model, and measure whether it covers the gold edit.

Regime 'file': the developer names the file (gold file); we show it whole if it fits,
otherwise the module header plus the AST chunks (functions, methods, class headers) that
score highest under BM25 against the issue text, in file order, until the token budget is used.
No line numbers are shown (models copy them into SEARCH blocks).
Coverage is computed from the gold patch and is NEVER shown to the model.
"""
import ast, math, os, re, urllib.request, urllib.error, collections
import tiktoken

ENC = tiktoken.get_encoding("o200k_base")  # approximation of gpt-oss tokenizer
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "src_cache")


def ntok(s):
    return len(ENC.encode(s))


def fetch_source(repo, commit, path):
    dst = os.path.join(CACHE, repo.replace("/", "__"), commit, *path.split("/"))
    if not os.path.exists(dst):
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(data)
    return open(dst, "rb").read().decode("utf-8", errors="replace").replace("\r\n", "\n")


def words(s):
    out = []
    for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s):
        out.append(w.lower())
        for p in re.sub(r"([a-z])([A-Z])", r"\1 \2", w).replace("_", " ").split():
            if len(p) > 2:
                out.append(p.lower())
    return out


def chunks_of(src):
    """Return list of (start_line, end_line) 1-based inclusive: module header + function/method chunks + class headers."""
    lines = src.split("\n")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # fall back to fixed windows
        return [(i + 1, min(i + 40, len(lines))) for i in range(0, len(lines), 40)]
    spans = []

    def visit(node, depth):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([ch.lineno] + [d.lineno for d in ch.decorator_list])
                spans.append((start, ch.end_lineno))
            elif isinstance(ch, ast.ClassDef):
                start = min([ch.lineno] + [d.lineno for d in ch.decorator_list])
                first_body = ch.body[0].lineno if ch.body else ch.end_lineno
                # class header: from class line to just before the first method
                first_def = min([c.lineno for c in ch.body if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))] or [ch.end_lineno + 1])
                spans.append((start, max(start, min(first_def - 1, ch.end_lineno))))
                visit(ch, depth + 1)
    visit(tree, 0)
    # module header: first lines up to first def/class
    first = min([s for s, _ in spans] or [len(lines) + 1])
    header = (1, min(first - 1, 60)) if first > 1 else None
    out = ([header] if header else []) + sorted(set(spans))
    return out


def bm25_select(src, query, budget_tokens):
    lines = src.split("\n")
    cs = chunks_of(src)
    docs = [words("\n".join(lines[s - 1:e])) for s, e in cs]
    q = collections.Counter(words(query))
    N = len(docs)
    df = collections.Counter()
    for d in docs:
        for t in set(d):
            df[t] += 1
    avg = sum(len(d) for d in docs) / max(1, N)
    scores = []
    for i, d in enumerate(docs):
        tf = collections.Counter(d)
        sc = 0.0
        for t, qf in q.items():
            if t in tf:
                idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
                sc += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(d) / max(1, avg)))
        scores.append(sc)
    order = sorted(range(N), key=lambda i: -scores[i])
    chosen, used = [], 0
    header_idx = 0 if cs and cs[0][0] == 1 and not any(s == 1 for s, _ in cs[1:]) else None
    if header_idx is not None:
        t = ntok("\n".join(lines[cs[0][0] - 1:cs[0][1]]))
        chosen.append(0); used += t
    for i in order:
        if i in chosen:
            continue
        s, e = cs[i]
        t = ntok("\n".join(lines[s - 1:e]))
        if used + t <= budget_tokens:
            chosen.append(i); used += t
    chosen.sort(key=lambda i: cs[i][0])
    return [cs[i] for i in chosen], used


def render(src, spans):
    lines = src.split("\n")
    out, prev_end = [], 0
    for s, e in spans:
        if s > prev_end + 1 and prev_end:
            out.append("# ... (lines omitted) ...")
        elif s > 1 and not prev_end:
            pass
        out.append("\n".join(lines[s - 1:e]))
        prev_end = e
    if prev_end < len(lines) and spans:
        out.append("# ... (lines omitted) ...")
    return "\n".join(out)


def gold_old_lines(gold_patch):
    """Set of old-file line numbers the gold patch changes (removed lines, plus the two neighbours of pure insertions)."""
    changed, old = set(), 0
    for ln in gold_patch.split("\n"):
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", ln)
        if m:
            old = int(m.group(1)) - 1
            pending_ins = False
            continue
        if ln.startswith("+++") or ln.startswith("---") or ln.startswith("diff ") or ln.startswith("index "):
            continue
        if ln.startswith("-"):
            old += 1; changed.add(old)
        elif ln.startswith("+"):
            changed.add(old); changed.add(old + 1)  # insertion point: anchor lines around it
        elif ln.startswith(" "):
            old += 1
    return {x for x in changed if x >= 1}


def build_file_context(task, src, budget_tokens):
    """Return (rendered_text, spans, info). Whole file if it fits, else BM25 chunks."""
    whole = ntok(src)
    if whole <= budget_tokens:
        spans = [(1, len(src.split("\n")))]
        text = src
        used = whole
        mode = "whole_file"
    else:
        spans, used = bm25_select(src, task["problem_statement"], budget_tokens)
        text = render(src, spans)
        mode = "bm25_chunks"
    gold = gold_old_lines(task["gold_patch"])
    shown = set()
    for s, e in spans:
        shown.update(range(s, e + 1))
    cov = (len(gold & shown) / len(gold)) if gold else 1.0
    info = dict(mode=mode, file_tokens=whole, context_tokens=used, n_spans=len(spans), gold_lines=len(gold),
                gold_lines_shown=len(gold & shown), coverage=round(cov, 3), covered_fully=(gold <= shown))
    return text, spans, info
