# Argus Pilot-100

Research folder for: why small models (gpt-oss-20b) fail at single-file repo repair, what Argus recovers, and what Argus should change.
Kept separate from the product repo (`C:\coding\Argus`) on purpose.

Start with `PILOT50_PROTOCOL.md` (see "Revision 2" at the top).

## Layout

| Path | Contents |
|---|---|
| `PILOT50_PROTOCOL.md` | Design, arms, failure taxonomy, rules |
| `manifests/` | Frozen task manifest and its SHA-256 |
| `scripts/` | Manifest builder (and later the harness) |
| `data/` | Prompts, raw model outputs (later) |
| `results/` | Grading outputs, labels (later) |
| `notes/` | Decision log |

## Status

- [x] Eligibility and sample drawn (`scripts/make_manifest.py`), manifest written. **Not yet committed or tagged.**
- [ ] Price table frozen from the Groq console
- [ ] Harness: key pool, prompt builder with token budget, one-shot generation
- [ ] 3-task smoke test
- [ ] Phase 1 generation (20B and 120B, plain one-shot), Docker grading, failure labels
- [ ] Phase 2 Argus ladder
- [ ] Phase 3 evidence-based change list

## Secrets

API keys stay in `C:\coding\Argus\.env`. The harness will read them from there by path and log only a short hash per key. Never copy keys into this folder; `.gitignore` excludes `.env*`.

## Regenerate the manifest

```bash
python scripts/make_manifest.py
```
