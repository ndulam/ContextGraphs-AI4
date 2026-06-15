"""
Pre-written RAG responses for the 2-minute demo.
These display instantly (simulated stream) so there's no API wait during the
critical failure moments — keeping the audience focused on the story, not the spinner.
"""

RAG_REMOVE_B = """\
Got it — I've noted that you'd like to remove House B from your shortlist. \
The long commute (2/5) and high HOA fees are completely valid reasons to pass.

That leaves you with **House A** ($425,000) and **House C** ($399,000) as your active candidates. \
Both offer better commute scores and more manageable HOA. \
Would you like a side-by-side comparison of the two?"""

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

RAG_WHY_REJECTED = """\
Looking at House B's listing data, here's what stands out:

**House B** — $475,000
- **Schools: 5/5** — Top-rated district, a real strength
- **Commute: 2/5** — Below average; this is the lowest commute score of the three
- **Taxes: 4/5** — Favorable property tax situation
- **Crime Rate: 4/5** — Safe neighborhood
- **Resale Value: 2/5** — Lower long-term appreciation potential
- **HOA: 2/5** — Higher monthly fees compared to the other options

The commute score of 2/5 and HOA rating of 2/5 are the weakest attributes. \
Would you like to compare these against House A and House C to help make a final call?"""

CACHE = {
    "rag_remove_b":    RAG_REMOVE_B,
    "rag_which_houses": RAG_WHICH_HOUSES,
    "rag_why_rejected": RAG_WHY_REJECTED,
}
