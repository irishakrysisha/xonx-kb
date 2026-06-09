"""End-to-end demo: an AI agent uses the KB exactly like a human would.

Run after build_kb.py. Exercises the full contract and prints what happens,
so the prototype's automation is visible without opening the sheet.
"""
from kb_api import KB


def main():
    kb = KB()

    print("== 1. agent SEARCHES before creating (avoid duplicates) ==")
    for h in kb.search("warranty cap"):
        print(f"   {h['ID']}  {h['Title']}")

    print("\n== 2. agent PROPOSES a new template (lands in Inbox as pending) ==")
    tmp = kb.propose(
        "Templates",
        {"Title": "Tax indemnity clause set (DE share deals)",
         "Practice": "Corporate", "Doc_type": "Memo template", "Language": "EN",
         "Jurisdiction": "DE", "Version": "v0.1", "Tags": "reusable, cross-border",
         "Summary": "Reusable tax-indemnity clauses distilled from the TechCorp deal "
                    "and the warranty-cap research. Pairs with the SPA template.",
         "Related": "PRE-0001, RES-0001"},
        proposed_by="agent:drafting-bot")
    print(f"   proposed -> {tmp} (Review_status=pending)")

    print("\n== 3. reviewer PROMOTES it (real ID assigned, links made bidirectional) ==")
    new_id = kb.promote(tmp, reviewer="Iryna")
    print(f"   promoted -> {new_id}")

    print("\n== 4. agent LINKS the new template to a provider ==")
    print("  ", kb.link(new_id, "PRV-0001"))

    print(f"\n== 5. GET {new_id} with resolved related records ==")
    rec = kb.get(new_id)
    print(f"   {rec['ID']}  {rec['Title']}  [{rec['Status']}]  src={rec['Source']}")
    for r in rec["_related"]:
        print(f"     -> {r['ID']:10} ({r['table']}) {r['Title']}")

    print("\n== 6. confirm the back-link landed on PRE-0001 ==")
    print("   PRE-0001 Related:", kb.get("PRE-0001", resolve=False)["Related"])

    print("\nDemo complete.")


if __name__ == "__main__":
    main()
