"""Create a deterministic, leakage-free visible/held-out PASS_TO_PASS split for Experiment 3.

Experiment 3 feeds regression-test failures back into Attempts 2-3. To avoid test leakage
(grading on the exact regression tests already shown to the model), each task's PASS_TO_PASS
node list is split 50/50 before any model call:
  - visible_p2p: shown in-loop as the regression gate signal
  - heldout_p2p: NEVER shown to the model; used only for final non-regressive grading

Output: manifests/exp3_p2p_split.json (+ .sha256)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_SEED = 20261126


def parse_node_list(value: Any) -> List[str]:
    """Normalize PASS_TO_PASS / FAIL_TO_PASS fields from list or JSON string."""
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            pass
    return []


def split_p2p_nodes(nodes: Iterable[str], seed: int, iid: str) -> Tuple[List[str], List[str]]:
    """Split sorted unique regression nodes deterministically into (visible_p2p, heldout_p2p)."""
    uniq = sorted({str(n) for n in nodes if str(n).strip()})
    if len(uniq) <= 1:
        return [], uniq
    rng = random.Random(f"{seed}:{iid}")
    shuffled = list(uniq)
    rng.shuffle(shuffled)
    n_vis = math.ceil(len(shuffled) / 2)
    # Keep at least 1 test held out whenever there are >=2 tests.
    if n_vis >= len(shuffled):
        n_vis = len(shuffled) - 1
    visible = sorted(shuffled[:n_vis])
    heldout = sorted(shuffled[n_vis:])
    return visible, heldout


def build_split_manifest(
    manifest_rows: List[Dict[str, Any]],
    tasks_by_id: Dict[str, Dict[str, Any]],
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Build the full Experiment 3 regression-split manifest."""
    entries: Dict[str, Dict[str, Any]] = {}
    for row in manifest_rows:
        iid = row["instance_id"]
        task = tasks_by_id.get(iid)
        if not task:
            continue
        p2p = parse_node_list(task.get("PASS_TO_PASS") or task.get("pass_to_pass"))
        vis, held = split_p2p_nodes(p2p, seed=seed, iid=iid)
        entries[iid] = {
            "repo": row.get("repo") or task.get("repo"),
            "p2p_total": len(p2p),
            "visible_p2p": vis,
            "heldout_p2p": held,
        }
    return {
        "name": "exp3_p2p_split",
        "seed": seed,
        "n_tasks": len(entries),
        "rule": "50/50 deterministic split of PASS_TO_PASS per task; visible_p2p for in-loop feedback, heldout_p2p strictly hidden for final grading.",
        "tasks": entries,
    }


def _load_source_tasks(source: str) -> Dict[str, Dict[str, Any]]:
    p = Path(source)
    if p.is_file():
        out: Dict[str, Dict[str, Any]] = {}
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    d = json.loads(line)
                    out[d["instance_id"]] = d
        return out
    from datasets import load_dataset

    ds = load_dataset(source, split="test")
    return {d["instance_id"]: dict(d) for d in ds}


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="Build Experiment 3 leakage-free PASS_TO_PASS split.")
    ap.add_argument("--manifest", default=str(root / "manifests" / "pilot100_manifest.json"))
    ap.add_argument("--source", default="princeton-nlp/SWE-bench_Verified", help="Local JSONL path or HF dataset ID.")
    ap.add_argument("--out", default=str(root / "manifests" / "exp3_p2p_split.json"))
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()

    man = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    rows = list(man.get("primary", [])) + list(man.get("reserve", []))
    tasks_by_id = _load_source_tasks(args.source)
    split_doc = build_split_manifest(rows, tasks_by_id, seed=args.seed)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(split_doc, indent=2) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    out_path.with_suffix(".sha256").write_text(f"{digest}  {out_path.name}\n", encoding="utf-8")
    print(f"Wrote {split_doc['n_tasks']} tasks to {out_path} (sha256={digest[:12]})")


if __name__ == "__main__":
    main()
