<div align="center">

<img src="assets/banner.svg" alt="HumanArchive" width="900"/>

# HumanArchive

**A decentralized archive for collective human memory — without judgment.**

[![Tests](https://img.shields.io/badge/tests-82%20passing-brightgreen)](tests/)
[![License: MIT](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![Content: CC BY-SA 4.0](https://img.shields.io/badge/content-CC--BY--SA--4.0-lightgrey)](LICENSE-CONTENT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

*[Tiếng Việt](README.md) · English*

</div>

> **History is written by the winners.** Until now.
>
> HumanArchive is a protocol and reference implementation for preserving
> **multi-perspective memory** of historical events — where a witness, a
> victim, an authority, and a bystander can all speak about the same
> event, and neither AI nor curator is allowed to rule on who is "right".

## Why this exists

Every historical narrative has a shape imposed by whoever could publish:
the winners, the literate, the loudest voice. Everyone else — victims
who couldn't risk retaliation, witnesses on the margins, participants
whose role was too small for biography — leaves almost no trace.

HumanArchive flips that. Anyone who lived through an event can
contribute an anonymous memory. AI cross-references multiple memories
to find convergence and divergence — **without concluding who is
correct**. Raw data is immutable; consent is enforced in code.

## Try it in 60 seconds

```bash
git clone https://github.com/Trustydev212/HumanArchive
cd HumanArchive
pip install -e .
humanarchive demo
humanarchive web        # open http://localhost:8000/web/
```

That's it. The demo builds a RAG index, exports an Obsidian vault,
generates a Mermaid graph of event relations, and runs an audit report —
all on fictional demo data you can explore before contributing yours.

## The 5 immutable principles

These are not guidelines. They are enforced by **code with tests
proving they hold**:

| Principle | Enforced by |
|---|---|
| **1. No verdicts.** AI never concludes who is right. | `FORBIDDEN_FIELDS` in LLM client rejects output with `verdict`, `guilty`, `is_lying`, etc. (`test_ethics.py`) |
| **2. Never identify anyone.** | PII scrubber runs **before** any LLM call; `contributor_id` is unguessable; query PII is scrubbed before embed |
| **3. Empathy before analysis.** | Trauma detection + content warnings; LLM system prompt enforces acknowledgement first |
| **4. Motivation > action.** | Schema requires `motivation.your_motivation`; AI engine raises `ValueError` if missing |
| **5. Raw data never deleted or edited.** | `memory_id = sha256(content)[:16]`; CI verifies; `withdrawn` / `embargo` filters without deletion |

See [`docs/ethics.md`](docs/ethics.md).

## What makes RAG different here

Plain RAG on sensitive memories has four failure modes that erase the
whole point of collective-memory archives. We prevent each:

| Failure | Our safeguard |
|---|---|
| PII leaks via embeddings | Scrub **before** embed, not after retrieve |
| Consent drift | `is_publicly_viewable` + `allows_ai_analysis` gate at index time |
| Bias amplification (10 witnesses drown out 1 victim) | **Role-balanced retrieval** — top-1 per role |
| Identity-probe queries | Query scrubbing before embed |

See [`docs/rag.md`](docs/rag.md).

## Architecture at a glance

```
Contribution layer    tools/submit.py, web/submit.html
         │
         ▼
Schema + validation   core/schema/memory.json  (v1)
         │
         ▼
Archive layer         archive/events/<id>/<memory_id>.json  (immutable)
         │
         ├─► core/privacy/pii_scrubber.py   (regex + optional LLM)
         ├─► core/integrity.py              (memory_id + consent filter)
         ├─► core/trauma.py                 (content warnings)
         └─► core/annotations.py            (append-only context)
         │
         ▼
Analysis layer        core/ai_engine.py, core/rag/
                      (Claude + adaptive thinking + prompt caching)
         │
         ▼
Views                 core/graph.py → Mermaid / Obsidian / JSON
                      Web UI at /web/  (client-side RAG search)

Federation            tools/export_bundle.py, tools/import_bundle.py
                      (merkle root + ed25519 signature)
```

## Quickstart by role

### As a **contributor** (keeper of memory)
Open `web/submit.html` in your browser — no signup. You choose: your
role (participant/witness/authority/organizer/victim/bystander), what
happened, your motivation, what you feared then, what you understand
now. Optional: embargo until a future date, or withdraw later.

### As a **curator**
```bash
humanarchive staging list                                       # inbox
humanarchive staging review <mid> --type approve --reviewer <handle>
humanarchive staging merge <mid>                               # when 2+ approvals
```
You never edit memories. You suggest via annotations; contributor decides.

### As a **researcher**
```bash
humanarchive rag "why did they release the dam early?"
# Returns role-balanced top-5 citations + LLM synthesis
```
Always cite `memory_id + role + archive@<git-tag>`.

### As a **node operator**
```bash
humanarchive export-bundle --output mirror.tar.gz --sign-key priv.pem
# Distribute via GitHub / IPFS / Arweave / USB

humanarchive import-bundle received.tar.gz --archive my_archive/
# Content-addressed dedup; tamper detected via merkle
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for all 5 personas.

## Comparison (see [`docs/COMPARISON.md`](docs/COMPARISON.md))

|  | Multi-perspective | Immutable | Anonymous | Federable | AI cross-ref |
|---|---|---|---|---|---|
| Wikipedia | ❌ (NPOV consensus) | partial | partial | ❌ | ❌ |
| Archive.org | random | ✅ | n/a | ❌ | ❌ |
| Obsidian | ❌ (personal) | ❌ | ❌ | ❌ | ❌ |
| Mastodon | partial | ❌ (edits) | partial | ✅ | ❌ |
| **HumanArchive** | **✅ structured** | **✅** | **✅ default** | **✅ bundles** | **✅ with safeguards** |

## Stack

- **Python 3.10+** — core modules, zero required runtime deps
- **Anthropic Claude** (Opus 4.6) for analysis, with adaptive thinking + prompt caching
- **Voyage AI** (multilingual embeddings) or local **sentence-transformers** for RAG
- **Mermaid** for relation graphs
- **Obsidian** vault as a primary view (`[[wikilinks]]`, YAML frontmatter)
- **ed25519** via `cryptography` for federation signing
- **Git + tar.gz** for federation (no blockchain)
- **Vanilla JS + HTML** for web UI (no build step)

## Documentation

- [`docs/ethics.md`](docs/ethics.md) — the 5 principles explained
- [`docs/workflows.md`](docs/workflows.md) — multi-user patterns (critical reading)
- [`docs/rag.md`](docs/rag.md) — RAG safeguards in detail
- [`docs/federation.md`](docs/federation.md) — bundle protocol v1
- [`docs/event_decomposition.md`](docs/event_decomposition.md) — why folders are flat + how to build hierarchies
- [`docs/FAQ.md`](docs/FAQ.md) — skeptical questions answered honestly
- [`docs/COMPARISON.md`](docs/COMPARISON.md) — vs Wikipedia, Obsidian, Mastodon, etc.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). There are **5 non-code paths**
to contribute (keeper, curator, researcher, translator, node operator)
— each as important as code.

Code of Conduct: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Derived
directly from the 5 principles — not generic.

Security: [`SECURITY.md`](SECURITY.md). PII leaks have a private channel;
ethical vulnerabilities are patched immediately.

## Cite

```bibtex
@software{humanarchive2024,
  title = {HumanArchive: Decentralized Collective Memory Archive},
  author = {{HumanArchive contributors}},
  year = {2024--},
  url = {https://github.com/Trustydev212/HumanArchive},
  license = {MIT (code), CC-BY-SA 4.0 (content)}
}
```

## Roadmap

- [x] v0.1–v0.4: schema, ethical guardrails, RAG, Obsidian export
- [x] v0.5: federation bundle protocol, Web UI
- [x] v0.6: staging + annotation + audit workflows
- [x] v0.7: installable package, community scaffolding, bilingual docs
- [ ] v0.8: i18n Web UI (EN/FR/ZH), timeline view, IPFS auto-pin
- [ ] v0.9: mobile submission app (PWA), WebAuthn for reviewer signing
- [ ] v1.0: production-grade federation, first external instance, academic publications

## License

- **Code**: [MIT](LICENSE)
- **Memory content**: [CC-BY-SA 4.0](LICENSE-CONTENT) with additional
  ethical terms (no deanonymization, no judgment-grading AI training,
  no harassment).

---

> *"History is not a single river. It is a constellation of countless
> viewpoints — and only when we read it from many sides does truth
> become hard to hide."*
