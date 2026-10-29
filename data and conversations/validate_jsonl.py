"""Checks a FinSAO dataset file.  Usage: python validate_jsonl.py seeds_100.jsonl

ERRORS (exit code 1): invalid JSON, wrong keys, bad values, unknown tool names, empty text,
duplicate user_input, transfer amount that does not match the Yellow/Red tier.
WARNINGS: capitalised words in user_input that might be a personal or brand name
(the dataset should not contain names).
"""
import json
import re
import sys
from collections import Counter

TOOLS = {
    "get_accounts", "get_balance", "get_transactions", "resolve_beneficiary", "create_transfer_draft",
    "get_transfer_status", "commit_transfer", "get_monthly_summary", "analyze_spending", "categorize_transaction",
    "get_budget_status", "create_budget", "update_budget", "list_subscriptions", "detect_recurring_payments",
    "cancel_subscription", "list_cards", "get_card_status", "update_card_limit", "freeze_card", "unfreeze_card",
    "report_card_lost", "list_wealth_products", "compare_wealth_products", "get_wealth_recommendations",
    "assess_risk_profile", "get_holdings", "create_wealth_subscription_draft", "commit_wealth_subscription",
    "create_wealth_redemption_draft", "commit_wealth_redemption", "get_wealth_order_status",
}
SCENARIOS = {"smart_transfer", "bill_analysis", "wealth", "card_management", "subscriptions",
             "orchestration", "security", "vague_or_interrupt"}
TIERS = {"GREEN", "YELLOW", "RED", "N/A"}
SUPPORT = {"full", "partial", "gap"}
KEYS = {"id", "scenario", "situation", "risk_tier", "lang", "user_input", "agent_response",
        "expected_tools", "repo_support", "source"}

# capitalised words that are fine in user_input
ALLOWED_CAPS = {"I", "I'm", "I've", "I'd", "I'll", "RMB", "CNY", "MFA", "SMS", "OTP", "PIN", "CVV", "ATM", "SYSTEM",
                "Python", "WeChat", "Alipay", "January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December", "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday", "Saturday", "Sunday", "AM", "PM", "QR", "IM", "OK", "ID", "VIP", "NOTE"}


def main(path):
    errors, warnings, seen = [], [], {}
    scn, sup, lang, tier, sit = Counter(), Counter(), Counter(), Counter(), Counter()
    n = 0
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"line {ln}: invalid JSON ({e})")
                continue
            if set(r) != KEYS:
                errors.append(f"line {ln}: keys differ: missing={sorted(KEYS - set(r))} extra={sorted(set(r) - KEYS)}")
                continue
            for field, allowed in [("scenario", SCENARIOS), ("risk_tier", TIERS), ("repo_support", SUPPORT), ("lang", {"en", "zh"})]:
                if r[field] not in allowed:
                    errors.append(f"line {ln}: bad {field} '{r[field]}'")
            if not isinstance(r["expected_tools"], list):
                errors.append(f"line {ln}: expected_tools must be a list")
                continue
            for t in r["expected_tools"]:
                if t not in TOOLS:
                    errors.append(f"line {ln}: unknown tool '{t}'")
            if not r["user_input"].strip() or not r["agent_response"].strip():
                errors.append(f"line {ln}: empty text")
            k = r["user_input"].strip().lower()
            if k in seen:
                errors.append(f"line {ln}: duplicate user_input (first at line {seen[k]})")
            seen[k] = ln

            # tier check for simple transfers: amount in digits (or 'k') vs CNY 1,000 daily limit
            if r["scenario"] == "smart_transfer" and "commit_transfer" in r["expected_tools"]:
                text = r["user_input"]
                if not re.search(r"already|earlier|today", text, re.I):
                    m = re.search(r"(\d+(?:\.\d+)?)\s*k\b", text, re.I)
                    amt = float(m.group(1)) * 1000 if m else None
                    if amt is None:
                        m = re.search(r"\d[\d,]*", text)
                        amt = float(m.group(0).replace(",", "")) if m else None
                    if amt is not None:
                        want = "RED" if amt > 1000 else "YELLOW"
                        if r["risk_tier"] != want:
                            errors.append(f"line {ln}: amount {amt:g} should be {want}, got {r['risk_tier']}")

            # possible names / brands: capitalised word that does not start a sentence
            if r["lang"] == "en":
                text = r["user_input"]
                starts = {m.start(1) for m in re.finditer(r"(?:^|[.!?:]\s+|['\"]\s*)([A-Za-z])", text)}
                for m in re.finditer(r"[A-Za-z][A-Za-z']*", text):
                    w = m.group(0)
                    if w[0].isupper() and w not in ALLOWED_CAPS and m.start() not in starts:
                        warnings.append(f"line {ln}: '{w}' in user_input - is this a name or brand?")
            scn[r["scenario"]] += 1
            sup[r["repo_support"]] += 1
            lang[r["lang"]] += 1
            tier[r["risk_tier"]] += 1
            sit[r["situation"]] += 1
    print(f"{n} rows | scenarios {dict(scn)}")
    print(f"tiers {dict(tier)} | repo_support {dict(sup)} | lang {dict(lang)} | distinct situations {len(sit)}")
    if warnings:
        print(f"{len(warnings)} warning(s):")
        print("\n".join(warnings[:30]))
    if errors:
        print(f"{len(errors)} error(s):")
        print("\n".join(errors[:40]))
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "seeds_100.jsonl")
