"""The ~900 lines after the first 100 in the draft were 36 request frames repeated with different amounts,
periods, names and tacked-on endings ("but ask if anything is unclear", "then summarize the outcome").
Here each frame is kept (same wording, no names) but every line gets an agent_response written for its own
amount, period and recipient, with tools, risk tier and honest limits. Impossible combinations from the draft
("recurring charges in next month", "the saved beneficiary for the saved beneficiary") are not generated.
"""
import random

RB, CTD, CT = "resolve_beneficiary", "create_transfer_draft", "commit_transfer"
TR, TS, GB, GA = "get_transactions", "get_transfer_status", "get_balance", "get_accounts"
LS, DR, CS, GH = "list_subscriptions", "detect_recurring_payments", "cancel_subscription", "get_holdings"
LWP, CWP, GBS = "list_wealth_products", "compare_wealth_products", "get_budget_status"

HIST = ["this month", "last month", "this quarter", "the past three months", "September", "the last 30 days", "last week"]
FWD = ["this month", "next month", "this quarter", "November"]
RECIP = ["my sister", "my landlord", "my roommate", "my brother", "my mom", "a friend", "my cousin"]
NOTES = ["textbooks", "utilities", "dinner", "October rent", "electricity", "birthday gift", "train tickets", "shared groceries"]
AMTS = [80, 150, 250, 350, 480, 600, 750, 900, 999, 1000, 1001, 1250, 1800, 2500, 3200]
PREFIX = ["", "Please ", "Can you ", "Could you ", "I'd like you to ", "Help me "]


def m(n):
    return f"{n:,}"


def tier_tr(a):
    return "RED" if a > 1000 else "YELLOW"


def gate(a):
    return ("Red tier, so MFA is required" if a > 1000 else "Yellow tier, so the user's confirmation is required")


# frame = (scenario, situation, tier(a)->str, template, response(s)->str, tools, support, slots)
# slots used by the template: a (amount), p (period), r (recipient), n (note), w (weeks)
FRAMES = [
    ("card_management", "apply for a virtual card", lambda s: "YELLOW", "explain the steps to apply for a virtual card",
     lambda s: "Explains the general idea (choose a purpose, set a limit, confirm with the user) but says there is no card-issuing tool, so it cannot submit the application or promise approval.",
     [], "gap", ""),
    ("subscriptions", "find forgotten recurring charges", lambda s: "GREEN", "find recurring charges around RMB {a} and list their renewal dates",
     lambda s: f"Calls detect_recurring_payments and list_subscriptions, keeps the charges close to CNY {m(s['a'])}, and lists merchant and next renewal date. Dates are shown only where the data has them.",
     [DR, LS], "full", "a"),
    ("wealth", "redemption check", lambda s: "GREEN", "check whether redeeming RMB {a} is supported and explain the relevant terms",
     lambda s: f"Calls get_holdings and list_wealth_products to see whether the holding covers CNY {m(s['a'])} and whether the product supports redemption, and explains the terms in the data. Actually redeeming is Red tier and needs MFA.",
     [GH, LWP], "full", "a"),
    ("bill_analysis", "keep money free for savings", lambda s: "GREEN", "review my upcoming bills and help me keep RMB {a} available for savings",
     lambda s: f"Calls get_balance, list_subscriptions and detect_recurring_payments to total the upcoming charges, then says whether CNY {m(s['a'])} stays free after them. No money is moved.",
     [GB, LS, DR], "partial", "a"),
    ("card_management", "limit validity check", lambda s: "GREEN", "check the current limit on my card and whether RMB {a} is a valid new limit",
     lambda s: f"Calls get_card_status for the current limit and compares it with CNY {m(s['a'])}. If the user wants to change it, update_card_limit is Yellow tier (confirmation). If the system rejects the value, the agent reports the reason.",
     ["get_card_status", "update_card_limit"], "full", "a"),
    ("wealth", "product fees", lambda s: "GREEN", "show documented fees and returns for the available investment products",
     lambda s: "Calls list_wealth_products and shows fees and returns only where they are in the data. Returns are described as not guaranteed; missing data is reported as missing.",
     [LWP], "partial", ""),
    ("bill_analysis", "check bills before a savings transfer", lambda s: tier_tr(s["a"]), "check my upcoming bills before recommending a savings transfer of RMB {a}",
     lambda s: f"Calls get_balance, list_subscriptions and detect_recurring_payments, and recommends the CNY {m(s['a'])} savings transfer only if enough remains after bills. The transfer itself would be {gate(s['a'])}.",
     [GB, LS, DR, CTD], "partial", "a"),
    ("wealth", "return claim on a product page", lambda s: "GREEN", "explain whether a product's stated return is guaranteed before I invest RMB {a}",
     lambda s: f"Checks list_wealth_products. A stated or past return is not a guarantee unless the data says so, and the agent will not promise one. Investing CNY {m(s['a'])} would be Red tier (MFA) after a suitability check.",
     [LWP], "full", "a"),
    ("card_management", "unrecognised card payment", lambda s: "GREEN", "review an unfamiliar card charge of RMB {a}",
     lambda s: f"Finds the CNY {m(s['a'])} charge with get_transactions and shows merchant and date. Offers freeze_card (Yellow) if the user suspects fraud, and says disputes are not supported.",
     [TR], "partial", "a"),
    ("card_management", "freeze with a reason", lambda s: "YELLOW", "secure my card because I cannot find it",
     lambda s: "Offers freeze_card straight away (Yellow, with confirmation) and explains that report_card_lost is a separate Red-tier step if the card is gone for good.",
     ["list_cards", "freeze_card"], "full", ""),
    ("wealth", "compare two products", lambda s: "GREEN", "compare available wealth products for a goal of RMB {a} and explain the risks",
     lambda s: f"Calls list_wealth_products and compare_wealth_products, checks which products accept CNY {m(s['a'])} given their minimums, and explains risk tier and redemption terms. No promise of returns.",
     [LWP, CWP], "full", "a"),
    ("card_management", "freeze with a reason", lambda s: "YELLOW", "freeze my card and report the confirmed status",
     lambda s: "Calls freeze_card after the user confirms (Yellow), then get_card_status, and reports 'frozen' only if the tool returns it.",
     ["list_cards", "freeze_card", "get_card_status"], "full", ""),
    ("bill_analysis", "weekly saving target", lambda s: "GREEN", "estimate how much I need to save each week to reach RMB {a} in {w} weeks",
     lambda s: f"Plain calculation: {m(s['a'])} / {s['w']} = about CNY {round(s['a'] / s['w']):,} a week. May compare it with get_monthly_summary to say whether recent surplus could cover it.",
     ["get_monthly_summary"], "full", "aw"),
    ("bill_analysis", "possible duplicate charge", lambda s: "GREEN", "check a possibly duplicated payment and tell me the recorded status",
     lambda s: "Calls get_transactions to find payments with the same payee and amount close together and get_transfer_status for their recorded status. Reports what is recorded and does not promise a refund.",
     [TR, TS], "partial", ""),
    ("wealth", "view holdings", lambda s: "GREEN", "retrieve my holdings and available investment-return information",
     lambda s: "Calls get_holdings and lists each holding. Return figures are shown only if the tool returns them, otherwise the agent says they are not available.",
     [GH], "full", ""),
    ("smart_transfer", "two saved payees match the description", lambda s: tier_tr(s["a"]), "send RMB {a} to {r}; if the recipient is ambiguous, ask me first",
     lambda s: f"Resolves '{s['r']}' with resolve_beneficiary. If more than one saved payee matches, lists them and asks which; otherwise creates a CNY {m(s['a'])} draft ({gate(s['a'])}) and commits after approval.",
     [RB, CTD, CT], "full", "ar"),
    ("smart_transfer", "check a transfer against the rules", lambda s: tier_tr(s["a"]), "check whether a transfer of RMB {a} to {r} can proceed under the security rules",
     lambda s: f"Reads today's outgoing total with get_transactions and says the transfer of CNY {m(s['a'])} would be {gate(s['a'])}. Nothing is sent; this is only a check.",
     [RB, TR], "full", "ar"),
    ("smart_transfer", "find the right payee first", lambda s: tier_tr(s["a"]), "find the correct saved beneficiary for {r} before drafting a RMB {a} payment",
     lambda s: f"Calls resolve_beneficiary for '{s['r']}' and shows the matching payee (nickname, last digits) for the user to confirm. Only then creates the CNY {m(s['a'])} draft ({gate(s['a'])}).",
     [RB, CTD], "full", "ar"),
    ("smart_transfer", "status of a past transfer", lambda s: "GREEN", "look up my transfer to {r} for RMB {a} and report its status",
     lambda s: f"Resolves '{s['r']}', finds the CNY {m(s['a'])} transfer with get_transactions and reports its status from get_transfer_status. If none or several match, says so.",
     [RB, TR, TS], "full", "ar"),
    ("smart_transfer", "check against the cumulative limit", lambda s: tier_tr(s["a"]), "check whether sending RMB {a} to {r} would cross today's cumulative transfer threshold",
     lambda s: f"Adds up today's outgoing transfers with get_transactions, then adds CNY {m(s['a'])} and compares the total with CNY 1,000. Says which tier the new total falls in. Nothing is sent.",
     [TR], "full", "ar"),
    ("subscriptions", "cancel by description", lambda s: "YELLOW", "identify the subscription that charges me RMB {a} and show its details before cancelling it",
     lambda s: f"Calls list_subscriptions and finds the one near CNY {m(s['a'])}, shows merchant, amount and next billing date, and asks for confirmation (Yellow) before cancel_subscription. If several match, asks which.",
     [LS, CS], "full", "a"),
    ("bill_analysis", "find savings to cut", lambda s: "GREEN", "identify spending cuts that could free up RMB {a} {f}",
     lambda s: f"Calls analyze_spending and list_subscriptions, finds large flexible categories and unused-looking subscriptions, and proposes cuts that add up to CNY {m(s['a'])}. Nothing is changed without the user's say-so.",
     ["analyze_spending", LS], "full", "af"),
    ("bill_analysis", "period-over-period comparison", lambda s: "GREEN", "compare my spending in {p} with the previous period",
     lambda s: f"Calls get_monthly_summary for {s['p']} and the period before it and reports the difference in total and by category.",
     ["get_monthly_summary"], "full", "p"),
    ("bill_analysis", "category breakdown", lambda s: "GREEN", "summarize my spending by category for {p}",
     lambda s: f"Calls analyze_spending for {s['p']} and lists each category with amount and share.",
     ["analyze_spending"], "full", "p"),
    ("bill_analysis", "set aside money", lambda s: "GREEN", "check my available balance and see if I can set aside RMB {a} {f}",
     lambda s: f"Calls get_balance, get_budget_status and list_subscriptions, subtracts the known commitments, and says whether CNY {m(s['a'])} can be set aside {s['f']}. Moving it would be a separate step that needs confirmation.",
     [GB, GBS, LS], "partial", "af"),
    ("orchestration", "coordinate bills, savings and recurring payments", lambda s: "GREEN", "coordinate my bills, savings and recurring payments for {f}",
     lambda s: f"Runs get_balance, get_budget_status, list_subscriptions and detect_recurring_payments, and lays out what is due {s['f']}, what is left and what could go to savings. Read-only; any action it suggests needs its own confirmation.",
     [GB, GBS, LS, DR], "partial", "f"),
    ("bill_analysis", "review spending and save a target", lambda s: "GREEN", "review my spending for {p} and help me save RMB {a}",
     lambda s: f"Calls get_monthly_summary and analyze_spending for {s['p']}, finds categories to trim so CNY {m(s['a'])} can be saved, and offers to create budgets with create_budget.",
     ["get_monthly_summary", "analyze_spending"], "full", "ap"),
    ("subscriptions", "recurring charges with monthly total", lambda s: "GREEN", "identify recurring charges in {p} and estimate their monthly total",
     lambda s: f"Calls detect_recurring_payments for {s['p']} and adds up the repeating charges, stating how it handled charges that are not monthly.",
     [DR], "full", "p"),
    ("wealth", "liquidity and risk for short-term money", lambda s: "GREEN", "compare liquidity and risk for money I may need {f}",
     lambda s: f"Calls list_wealth_products and compare_wealth_products and compares redemption support and risk tier for money needed {s['f']}. Says that no product removes the risk of loss and that redemption is Red tier.",
     [LWP, CWP], "full", "f"),
    ("bill_analysis", "budget that creates savings", lambda s: "GREEN", "build a budget for {f} that targets RMB {a} in savings",
     lambda s: f"Calls analyze_spending and get_budget_status, proposes category limits that leave CNY {m(s['a'])} unspent for {s['f']}, and calls create_budget for each after the user agrees.",
     ["analyze_spending", GBS, "create_budget"], "full", "af"),
    ("subscriptions", "reduce subscription cost by a target", lambda s: "YELLOW", "find ways to reduce subscription spending by RMB {a} {f}",
     lambda s: f"Calls list_subscriptions and suggests combinations that save at least CNY {m(s['a'])}. Cancels only what the user picks, each with its own confirmation (Yellow).",
     [LS, CS], "full", "af"),
    ("bill_analysis", "unusual transaction detection", lambda s: "GREEN", "find unusual or duplicate-looking transactions in {p}",
     lambda s: f"Calls get_transactions and analyze_spending for {s['p']} and flags outliers and near-identical pairs. Labels them 'unusual', not 'fraud'.",
     [TR, "analyze_spending"], "partial", "p"),
    ("card_management", "card transactions list", lambda s: "GREEN", "show my card transactions above RMB {a} for {p}",
     lambda s: f"Calls get_transactions for {s['p']} and lists card payments above CNY {m(s['a'])}.",
     [TR], "full", "ap"),
    ("bill_analysis", "filter by amount and period", lambda s: "GREEN", "list transactions above RMB {a} for {p}",
     lambda s: f"Calls get_transactions for {s['p']} (all pages) and keeps items above CNY {m(s['a'])}.",
     [TR], "full", "ap"),
    ("bill_analysis", "biggest merchants", lambda s: "GREEN", "analyze merchant-level spending and show the biggest costs for {p}",
     lambda s: f"Calls get_transactions for {s['p']} and groups payments by merchant description, then ranks the biggest. There is no merchant tool, so the grouping is based on transaction descriptions and the agent says so.",
     [TR, "analyze_spending"], "partial", "p"),
    ("smart_transfer", "standard transfer with a note", lambda s: tier_tr(s["a"]), "prepare a transfer of RMB {a} to {r} with the note '{n}'",
     lambda s: f"Resolves '{s['r']}' and creates a CNY {m(s['a'])} draft with the note '{s['n']}'. Says that this is {gate(s['a'])} before commit_transfer. Nothing is sent until the user approves.",
     [RB, CTD], "full", "arn"),
]


def make(rng, per_frame=6):
    """Return rows (scenario, situation, tier, lang, ui, ar, tools, support)."""
    out = []
    for scn, sit, tier, tmpl, resp, tools, sup, slots in FRAMES:
        seen = set()
        tries = 0
        quota = per_frame if slots else 3
        while len(seen) < quota and tries < 80:
            tries += 1
            s = {}
            if "a" in slots:
                s["a"] = rng.choice(AMTS)
            if "p" in slots:
                s["p"] = rng.choice(HIST)
            if "f" in slots:
                s["f"] = rng.choice(FWD)
            if "r" in slots:
                s["r"] = rng.choice(RECIP)
            if "n" in slots:
                s["n"] = rng.choice(NOTES)
            if "w" in slots:
                s["w"] = rng.choice([4, 8, 12, 26, 52])
            fmt = {k: (m(v) if k == "a" else v) for k, v in s.items()}
            body = tmpl.format(**fmt)
            pre = rng.choice(PREFIX)
            if pre == "":
                ui = body[0].upper() + body[1:] + "."
            else:
                ui = pre + body[0].lower() + body[1:] + ("?" if pre in ("Can you ", "Could you ") else ".")
            if ui in seen:
                continue
            seen.add(ui)
            out.append((scn, sit, tier(s), "en", ui, resp(s), tools, sup))
    return out
