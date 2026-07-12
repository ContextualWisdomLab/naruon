# Codec Carver audio-pipeline integration (naruon)

**Goal:** convert audio/recording attachments through Codec Carver
(`ContextualWisdomLab/codec-carver` — Python CLI + web/async-job service that
carves long recordings into metadata-preserved FLAC/Opus) so naruon can run STT
or feed an omni-modal LLM, and play the normalized audio back in-app.

## Why codec-carver
- Raw recordings (m4a/wav/large) are unwieldy for STT / omni-modal input: too
  big, inconsistent codecs, >context-length duration. Codec Carver normalizes to
  FLAC (lossless) or size-bounded high-bitrate Opus, splits long sources at
  silence, and preserves metadata — the right pre-processing stage.
- It already has the surface naruon needs: async job API (submit→status→result,
  PR #166), opt-in API-key auth (#193), MCP driver, and an optional
  `--transcribe` sidecar (#165). **These are the integration dependencies.**

## Pipeline
```
email/attachment audio  → naruon detects audio MIME/ext
  → naruon BE  POST codec-carver /shrink (async)   [+ CODEC_CARVER_API_KEY]
       → poll job → normalized FLAC/Opus segments (+ optional transcript sidecar)
  → naruon stores segments as workspace document assets
  → STT / omni-modal:
       (a) codec-carver --transcribe sidecar (#165), OR
       (b) naruon feeds FLAC to its own STT / omni-modal LLM
  → transcript flows into the existing content-graph / grounded-extraction path
     (segments become citeable evidence — same moat as documents)
  → FE: native <audio> playback of the Opus/FLAC + transcript view
```

### Config (operator-set, disabled when unset)
- `CODEC_CARVER_BASE_URL` — in-cluster Service URL (mirrors `CLEARFOLIO_BASE_URL`).
- `CODEC_CARVER_API_KEY` — sent per #193's opt-in auth.
- Audio feature hidden while `CODEC_CARVER_BASE_URL` is unset.

## Audio player (task-4 decision)
**Recommendation: do NOT create a separate audio-player repo/submodule.** Native
HTML5 `<audio controls>` plays FLAC/Opus in all target browsers — the lazy,
zero-dependency, accessible default (ponytail: native platform feature over a
library/repo). Transcript-synced playback (highlight the transcript line as audio
plays) is a naruon-internal enhancement built on `<audio>` `timeupdate` events —
still no separate repo. Only stand up a dedicated player repo + submodule if a
genuinely novel need appears (waveform editing, multi-track diarization UI) that
`<audio>` cannot serve — not for MVP playback.

## Slices (PR sequence)
1. **BE client + config** — `services/codec_carver_client.py` (submit/poll/result
   with API-key header + timeout) behind `CODEC_CARVER_BASE_URL`; mocked-transport tests.
2. **Audio detection + convert flow** — detect audio attachments; BE endpoint to
   submit → track job → register normalized segments as assets.
3. **Transcript → content graph** — route transcript (sidecar or naruon STT) into
   content segments so recordings become citeable evidence.
4. **FE playback** — native `<audio>` + transcript view in the attachment/asset surface.

## Depends on (codec-carver PRs, currently open/unmerged)
- #166 async job API (submit→status→result) — the primary integration surface.
- #193 opt-in API-key auth — how naruon authenticates.
- #165 `--transcribe` sidecar — optional STT path (else naruon does STT).
All three are gated by the same central `opencode-review`/`trivy-fs` workflow as
naruon/clearfolio → unblocked by `.github#323`.

## Cross-repo note
naruon + clearfolio + codec-carver all share the org-central CI gate. One fix
(`.github#323`, trivy severity) unblocks the merge queues of all three.
