# Current-head review evidence and stale aggregate state

Naruon's protected merge gate evaluates evidence for one immutable pull-request
head. GitHub's aggregate `reviewDecision` can remain `CHANGES_REQUESTED` after
the review was submitted on an older commit. The gate therefore reads the
review-level `commit_id`: a current-head request blocks, while only stale
requests may be superseded by passing exact-head robot evidence.

This preserves the operational action for the customer: fix the request when it
targets the current code; otherwise continue the protected merge loop after the
new head's Checks and robot evidence pass. The gate does not dismiss reviews or
use an administrative bypass.

## APA 7 reference

GitHub. (2026). *REST API endpoints for pull request reviews*. GitHub Docs.
https://docs.github.com/en/rest/pulls/reviews?apiVersion=2022-11-28
