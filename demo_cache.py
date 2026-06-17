"""
Pre-written RAG responses for the demo.
These display instantly (simulated stream) so there's no API wait during the
critical failure moments — keeping the audience focused on the story, not the spinner.
"""

RAG_COMPARE = """\
Here's a side-by-side look at the three properties:

**House A** — $425,000
Schools: 4/5 · Commute: 4/5 · Taxes: 2/5 · Crime Rate: 4/5 · Resale Value: 4/5 · HOA: 3/5

**House B** — $475,000
Schools: 5/5 · Commute: 2/5 · Taxes: 4/5 · Crime Rate: 4/5 · Resale Value: 2/5 · HOA: 2/5

**House C** — $399,000
Schools: 3/5 · Commute: 5/5 · Taxes: 4/5 · Crime Rate: 4/5 · Resale Value: 4/5 · HOA: 5/5

**Quick read:** House B leads on schools (5/5) but has the worst commute (2/5) and highest HOA fees. \
House C is the best value at $399k with an excellent commute score. \
House A sits in the middle — solid across the board. What matters most to you?"""

RAG_REMOVE_B = """\
Got it — I've noted that you'd like to remove House B from your shortlist. \
The long commute (2/5) and high HOA fees are completely valid reasons to pass.

That leaves you with **House A** ($425,000) and **House C** ($399,000) as your active candidates. \
Both offer better commute scores and more manageable HOA. \
Would you like a side-by-side comparison of the two?"""

RAG_COMPARE_A_C = """\
Here's how House A and House C compare:

| | **House A** | **House C** |
|---|---|---|
| Price | $425,000 | $399,000 ✓ |
| Schools | 4/5 ✓ | 3/5 |
| Commute | 4/5 | 5/5 ✓ |
| Taxes | 2/5 | 4/5 ✓ |
| Crime Rate | 4/5 | 4/5 |
| Resale Value | 4/5 | 4/5 |
| HOA | 3/5 | 5/5 ✓ |

**House C** wins on price, commute, taxes, and HOA. **House A** has the edge on schools. \
If the school district is a priority, House A is worth the premium — otherwise House C looks like \
the stronger overall pick. Want to sleep on it and revisit?"""

RAG_WHICH_HOUSES = """\
Based on the listings currently in the database, here are all the properties available for your search:

**House A** — $425,000
Schools: 4/5 · Commute: 4/5 · Taxes: 2/5 · Crime Rate: 4/5 · Resale Value: 4/5 · HOA: 3/5

**House B** — $475,000
Schools: 5/5 · Commute: 2/5 · Taxes: 4/5 · Crime Rate: 4/5 · Resale Value: 2/5 · HOA: 2/5

**House C** — $399,000
Schools: 3/5 · Commute: 5/5 · Taxes: 4/5 · Crime Rate: 4/5 · Resale Value: 4/5 · HOA: 5/5

All three homes are currently in your search. House B stands out for its top-rated school district (5/5), \
while House C leads on commute convenience. Would you like help narrowing down further?"""

CACHE = {
    "rag_compare":      RAG_COMPARE,
    "rag_remove_b":     RAG_REMOVE_B,
    "rag_compare_a_c":  RAG_COMPARE_A_C,
    "rag_which_houses": RAG_WHICH_HOUSES,
}
