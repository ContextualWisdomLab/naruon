# HWP/HWPX shipped-state note

This branch intentionally keeps HWPX and HWP in a deterministic recognition state.
The importer identifies the family, gates obviously invalid bytes, and stores a
bounded deferred payload. It does not infer document semantics. This protects
buyer trust by preventing unsupported Korean enterprise documents from silently
disappearing while still keeping the LLM and conversion boundary explicit.
