# Security Policy

HumanArchive stores sensitive memories of real people. Security here is
about **privacy + integrity**, not just code vulnerabilities.

## If you find…

### A PII leak (most important)
A memory in the archive that reveals identifying information a
contributor didn't intend to share (name, phone, address, specific
location that narrows to one household, etc.).

**Don't open a public issue.** Public issues index in search engines
and can amplify the leak.

Instead:
1. Note the `memory_id` (NOT the content)
2. Email `security@humanarchive.org` (placeholder — set up by instance
   operator) or DM a maintainer listed in `trust/reviewers.json`
3. Include: memory_id, which fields contain the leak, a short
   description (not the PII itself)
4. We respond within 72 hours, coordinate scrub via annotation +
   contributor notification if possible.

### A memory_id tamper / integrity break
A file in `archive/events/` whose `memory_id` doesn't match
`sha256(content)[:16]`.

Run `humanarchive audit`. If the report flags integrity issues:
- If you caused it accidentally (e.g., linter auto-formatted JSON):
  revert the file, verify `humanarchive audit` is clean.
- If you didn't cause it: open an issue with tag `integrity` — this
  is a protocol violation that everyone should see.

### A signature verification failure in federation
When `humanarchive import-bundle` reports signature mismatch:
- Don't import.
- Open an issue with tag `federation` including the merkle_root + the
  pubkey claimed by the bundle.
- Contact the publisher to confirm their key wasn't compromised.

### A code vulnerability
Traditional security bug (code injection, path traversal, deps with
CVEs, etc.) in our Python / web code.

1. Email privately first.
2. We publish a CVE + fix within 30 days, or sooner for active
   exploits.
3. You get credit in the release notes (unless you prefer anonymity).

### An ethical vulnerability
Discovery that a code path allows violating one of the 5 principles
(e.g., a bug where `withdrawn=true` memories are served by mistake).
This is **more serious than a normal bug**.

1. Email privately.
2. We patch immediately, rebuild index, cut a release, and post a
   transparent post-mortem.
3. All affected contributors (via their anonymous contributor_id) are
   notified through their node operator if possible.

## Threat model

HumanArchive's threat model is unusual. Not all of these are solved —
being explicit about what is and isn't:

| Threat | Mitigation | Limit |
|---|---|---|
| Casual doxxing of contributor | PII scrubber before LLM + output | Regex detector; LLM-aided helps but not perfect |
| Targeted doxxing via content | contributor_id unguessable (ed25519-derived) | If contributor accidentally includes identifying details, we rely on community review |
| Identity-probe via RAG query | Query PII scrub before embed | Attacker can still probe via wording variations |
| Archive tamper | memory_id = content hash; CI verify | Doesn't prevent deletion, only modification |
| Bundle tamper in federation | MANIFEST merkle root + optional ed25519 | Unsigned bundles must be trusted out-of-band |
| Bias amplification via RAG | Role-balanced retrieval | Doesn't fix biased training of upstream embedder |
| Model extraction attacks | Not addressed (v0.7) | Future: differential privacy layer |
| Legal seizure of instance | Federation — other nodes continue | Doesn't protect the seized node's operator |
| Coordinated fake contributors | Staging review + web-of-trust | No full sybil resistance |

## What we don't promise

- We don't promise perfect anonymity. Memory content itself can be
  identifying regardless of technical scrub.
- We don't promise the archive will always be available. It's
  content-addressed and federable — availability depends on operators.
- We don't promise all LLM output is free of bias. We enforce
  principle 1 structurally, but generative output quality depends on
  the underlying model.

## Responsible disclosure window

90 days for non-critical issues.
30 days for critical PII leaks.
Immediate public patch for ethical vulnerabilities (after temporary
mitigation) — transparency is itself a principle.
