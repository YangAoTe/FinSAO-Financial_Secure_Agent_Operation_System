# P5 — Banking Agent Dataset Card / 银行 Agent 数据卡

## Identity and intended use

- Version: `1.0.0` (reviewed; test is frozen by the manifest hashes).
- Schema: strict Pydantic/JSON Schema `v1` in `banking_dataset/schema.py`.
- Intended use: routing, planning, tool selection, clarification and safety evaluation
  across rules, hosted models, local models and future optional routers.
- Not intended for identity, authorization, MFA, balance truth or financial execution.

The dataset is fully synthetic and contains no real people, account/card identifiers,
production prompts, secrets, MFA codes or authorization references. Names and amounts
are fictional scenario text. The repository license applies.

## Composition

`python -m banking_dataset.generate` deterministically creates 1,000 UTF-8 JSONL rows:

| Split | Samples | Semantic clusters |
|---|---:|---:|
| train | 700 | 14 |
| dev | 150 | 3 |
| test candidate | 150 | 3 |

Twenty semantic/template clusters cover accounts, transfers, analytics/budgets,
subscriptions, cards, fictional wealth, safety attacks and out-of-scope requests.
They include Green/Yellow/Red, missing slots, same-name recipients, cross-scenario plans,
prompt injection, approval bypass, cross-user exfiltration and planned savings-pot
behavior. All paraphrases for one semantic cluster remain in one split.

The first five authored variants of each cluster are tagged `manual_seed` (100 total);
the remaining 900 are deterministic expansions from recorded Chinese prefix/modifier/
suffix sets. The project owner confirmed the second review on 2026-10-26; all 100 seeds
are marked `reviewed`, while expansions retain their machine-expansion provenance.

## Labels and safety boundaries

Each tool expectation includes a stable call ID, key arguments and dependencies. The
schema rejects model-generated `user_id`, `risk_tier`, `approval_id`, `authorization_ref`
and `mfa_code` arguments. Expected tool names are checked against the P0 registry
snapshot. Core-owned expected risk is a gold evaluation label, never a model-supplied
tool argument.

## Validation and leakage controls

Run:

```powershell
python -m banking_dataset.generate
python -m banking_dataset.validate
python -m scripts.generate_p5_evidence
pytest tests/test_banking_dataset.py
```

Current automated result: 1,000 valid rows, zero exact cross-split conversation hashes,
zero cross-split cluster IDs, Tool Schema alignment passed, and maximum cross-split
`SequenceMatcher` similarity 0.8235. Exact SHA-256 hashes for each split are recorded in
`evaluation/dataset/manifest.json`. The fuzzy check is a triage signal, not an embedding
or human semantic-leak guarantee.

The unified scorer in `banking_dataset/score.py` reports intent macro-F1 and accuracy,
tool-sequence, risk, clarification and safety accuracy, while retaining missing and
unexpected prediction IDs. Later phases may extend slot/DAG/end-to-end metrics without
changing existing meanings.

## Review record and limitations

The 100-row review record is stored in `evaluation/reports/p5_manual_seed_review.csv`
and its formatted XLSX companion under `outputs/p5-review/`. The manifest records the
project-owner confirmation, review date, reviewed count and frozen split hashes. Any
future content change must create a new dataset version and repeat leakage/review checks.

The current language distribution is intentionally zh-CN only. Dialect, typo and
multi-turn coverage is limited; deterministic paraphrases are less diverse than natural
conversations. No generated expansion is automatically treated as new gold semantics.
