# HWP/HWPX attachment recognition merge checklist

- [ ] Hosted Application CI is terminal-success on the exact head.
- [ ] Hosted security checks are terminal-success on the exact head.
- [ ] Coverage gates accept the exact changed production surface.
- [ ] Review threads are zero or resolved.
- [ ] A qualifying independent non-author approval exists.
- [ ] No worker, OCR, LLM, network fetch, or conversion behavior is claimed by this deterministic import slice.
- [ ] Future workers preserve the same deferred payload and source-provenance contract.
