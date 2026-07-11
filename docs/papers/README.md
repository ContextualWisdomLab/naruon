# Papers

Background reading referenced by the codebase.

## LLM cost, routing, and load balancing

Background for routing batch-tolerant embedding work through
**contextual-orchestrator** (the routing / cost hub) instead of calling a batch
engine directly. The orchestrator owns provider selection, load balancing, and
cost accounting; naruon submits a batch and records the reported cost. See
[`backend/services/batch_embedding_service.py`](../../backend/services/batch_embedding_service.py).

- **`frugalgpt.pdf`** —
  L. Chen, M. Zaharia, J. Zou, *"FrugalGPT: How to Use Large Language Models
  While Reducing Cost and Improving Performance"* (arXiv:2305.05176, 2023).
  Source PDF: https://arxiv.org/pdf/2305.05176
  Motivates a cost-aware routing/cascade layer in front of LLM providers — the
  role contextual-orchestrator plays here — rather than every caller hard-wiring
  a single provider/engine.
- **`routellm.pdf`** —
  I. Ong, A. Almahairi, V. Wu, W.-L. Chiang, T. Wu, J. E. Gonzalez,
  M. W. Kadous, I. Stoica, *"RouteLLM: Learning to Route LLMs with Preference
  Data"* (arXiv:2406.18665, 2024).
  Source PDF: https://arxiv.org/pdf/2406.18665
  A learned router that dispatches each request to the cheapest model meeting a
  quality bar — the routing-hub pattern this PR moves batch embedding onto.
- **`hybrid-llm-routing.pdf`** —
  D. Ding, A. Mallick, C. Wang, R. Sim, S. Mukherjee, V. Rühle, L. V. S. Lakshmanan,
  A. H. Awadallah, *"Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing"*
  (arXiv:2404.14618, 2024).
  Source PDF: https://arxiv.org/pdf/2404.14618
  Quality-aware routing across a small/large model pair to balance cost against
  accuracy under load — the cost/quality trade-off the orchestrator centralizes
  so individual naruon hotspots do not.
- **`robust-batch-level-routing.pdf`** —
  J. Markovic-Voronov, K. Behdin, Y. Xu, Z. Zhou, Z. Wang, R. Mazumder,
  *"Robust Batch-Level Query Routing for Large Language Models under Cost and
  Capacity Constraints"* (arXiv:2603.26796, 2026).
  Source PDF: https://arxiv.org/pdf/2603.26796
  Current batch-specific research grounding for this slice: batch routing must
  treat cost and model capacity as coupled constraints, which is why naruon
  submits latency-tolerant import embedding work to contextual-orchestrator
  instead of selecting a provider locally per item.
