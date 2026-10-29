"""Builds the final 1,000-line dataset.   python build_final.py

 100  seeds                         seeds.py                (new, name-free, one situation each)
 100  repaired draft lines          draft_repaired.py       (the draft's 100 distinct lines, fixed)
 ...  repaired draft frames         draft_frames.py         (the draft's 36 repeated frames, fixed)
 ...  variations of the seeds       seed_variants.py        (incl. Chinese)

Outputs: finsao_dataset_1000.jsonl         full format (scenario, tier, tools ...)
         finsao_dataset_1000_simple.jsonl  only user_input and agent_response, as the team lead asked
"""
import json
import random
from collections import Counter
from pathlib import Path

import draft_frames
import draft_repaired
import seed_variants
from seeds import KEYS, rows as seed_rows

OUT = Path(__file__).parent
rng = random.Random(20261026)

# how many generated lines each scenario gets (the 100 seeds are added on top); sums to 900
QUOTA = {"smart_transfer": 131, "bill_analysis": 130, "wealth": 132, "card_management": 117,
         "subscriptions": 100, "orchestration": 90, "security": 100, "vague_or_interrupt": 100}


def line(t, source):
    scn, sit, tier, lang, ui, ar, tools, sup = t
    return dict(scenario=scn, situation=sit, risk_tier=tier, lang=lang, user_input=ui, agent_response=ar,
                expected_tools=list(tools), repo_support=sup, source=source)


def main():
    seeds = list(seed_rows())
    seen = {s["user_input"].strip().lower() for s in seeds}

    draft = [line((d[0], d[1], d[2], "en", d[3], d[4], d[5], d[6]), "draft_repaired") for d in draft_repaired.DRAFT]
    frames = [line(t, "draft_frame_repaired") for t in draft_frames.make(rng, 6)]
    variants = [line(t, "seed_variation") for t in seed_variants.make(rng)]
    zh = [v for v in variants if v["lang"] == "zh"]
    variants = [v for v in variants if v["lang"] != "zh"]

    chosen = []
    for scn, quota in QUOTA.items():
        picked = []
        # priority: repaired draft lines, Chinese lines, then a random mix of variations and frames
        for group in (draft, zh):
            for r in group:
                if r["scenario"] == scn and len(picked) < quota and r["user_input"].strip().lower() not in seen:
                    seen.add(r["user_input"].strip().lower())
                    picked.append(r)
        rest = [r for r in variants + frames if r["scenario"] == scn]
        rng.shuffle(rest)
        for r in rest:
            if len(picked) >= quota:
                break
            k = r["user_input"].strip().lower()
            if k in seen:
                continue
            seen.add(k)
            picked.append(r)
        if len(picked) < quota:
            print(f"warning: {scn} has only {len(picked)} of {quota}")
        chosen += picked

    for i, r in enumerate(chosen, 1):
        r["id"] = f"G-{i:04d}"
    allrows = seeds + chosen
    rng.shuffle(allrows)

    with open(OUT / "finsao_dataset_1000.jsonl", "w", encoding="utf-8") as f:
        for r in allrows:
            f.write(json.dumps({k: r[k] for k in KEYS}, ensure_ascii=False) + "\n")
    with open(OUT / "finsao_dataset_1000_simple.jsonl", "w", encoding="utf-8") as f:
        for r in allrows:
            f.write(json.dumps({"user_input": r["user_input"], "agent_response": r["agent_response"]}, ensure_ascii=False) + "\n")

    print(f"total {len(allrows)} | by source {dict(Counter(r['source'] for r in allrows))}")
    print("by scenario", dict(Counter(r["scenario"] for r in allrows)))
    print("distinct agent_response:", len({r['agent_response'] for r in allrows}), "| distinct situations:", len({r['situation'] for r in allrows}))


if __name__ == "__main__":
    main()
