# Tiebreaker Ranking (BRD-Derived)

This requirement is taken verbatim from a real Business Requirements Document
(*Vamos Argentina*, v2.0, Nov 2025), section III.8 *Tiebreakers*:

> If two or more fans have identical scores for an activation or leaderboard
> rank, the tie is broken by, in order:
>
>   1. Higher total Gameplay points.
>   2. More unique platforms shared (Channel Bonus).
>   3. Earlier submission timestamp.

Implement a comparator over fan records. Input: a list of fan records, each
of which is a tuple `(total_score, gameplay_points, unique_platforms,
submission_timestamp)`. Output: the same list re-sorted with the highest-rank
fan first, applying the tiebreaker order above when totals are equal.

* All four fields are integers.
* `submission_timestamp` is a Unix epoch in seconds; earlier is better.
* Stability: ties that remain after all three tiebreakers may be in any order.
