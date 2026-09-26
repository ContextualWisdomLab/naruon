# E1 thread judgment card: first evidence slice

**Status:** In progress under #1000 Story 1.2, stacked on #1786. The full cross-source and complete-history acceptance criteria remain open.

The mail view can request a structured judgment card for its owner-scoped conversation. Claims cite stored content segments; conflicting messages retain separate citations. Linked tasks and typed project-graph objects remain connected to their source messages. Unknown segment, task, or object identifiers fail closed. The response marks limited evidence when an input segment exceeds 2,000 characters, the thread exceeds 40 selected segments, or more than 40 graph objects qualify; the UI asks the reader to check the whole conversation. A matching citation identifier establishes provenance, not semantic support, so the card is labeled as an AI draft requiring source review.

Research: Wolhandler, R., Cattan, A., Ernst, O., & Dagan, I. (2022). *How "multi" is multi-document summarization?* Proceedings of EMNLP 2022. https://arxiv.org/abs/2210.12688 — motivates checking whether an output actually combines multiple sources. Huang, K.-H., Laban, P., Fabbri, A. R., Choubey, P. K., Joty, S., Xiong, C., & Wu, C.-S. (2024). *Embrace divergence for richer insights: A multi-document summarization benchmark and a case study on summarizing diverse information from news articles.* Proceedings of NAACL 2024. https://arxiv.org/abs/2309.09369 — supports showing divergent source claims instead of flattening them. PDFs are linked rather than redistributed because redistribution permission has not been established.

Next slice: connect external issue/code records and evaluate claim-level support against the cited text; batch long threads so the card can cover their full history.
