# Vite 8.1.4 bundled braces: bounded-depth remediation

This patch **bounds recursion; it does not remove braces or chokidar**. Vite
8.1.4's installed `dist/node/chunks/node.js` still contains braces 3.0.3 and
chokidar 3.6.0. Package-audit results alone do not assess embedded supplier code.

The supplier delta is unchanged from the original depth-guard proposal: parser
stack admission rejects more than 64 nested brace/parenthesis blocks, and the
compile, expand and stringify AST walkers reject depth greater than 65. These
limits are not user-overridable. Excessive inputs produce a `SyntaxError` carrying
`ERR_VITE_BRACES_DEPTH`; they are not silently accepted or normalized.

The vendor patch uses eight zero-context replacement hunks. Otherwise pure
insertions consume and re-add the preceding supplier line as an identity anchor:
pnpm's handling of plain zero-context insertions moved the guards one line early
in the rejected first attempt. Fresh installation of the anchored serialization
must reproduce the original supplier bytes. Context lines containing a
leading diff space followed by supplier tabs cause Git whitespace errors when
that patch file itself is added by an outer repository patch. Removing only
context avoids those errors without reformatting installed supplier code or
relaxing Git checks. pnpm 11.5.3 regenerates the effective patch hash and frozen
installation applies the patch. Whole installed Vite supplier-file bytes must
match the original proposal, not merely selected guard snippets. Keep the patch
bound to Vite 8.1.4; supplier upgrades require renewed verification.

The real consumer is bundled chokidar's brace expansion in glob directory
filtering. Vite defaults to `disableGlobbing: true`, but user watch options can
override that default. `watch: null` bypasses watcher initialization; neither
setting constitutes embedded dependency removal. Replacing the bundle with
chokidar 4 is not a drop-in fix: its removed glob support needs separately
reviewed adapters and downstream compatibility tests.

Verification scripts `test-vite-braces.mjs` and `test-vite-watch.mjs` run through
both `test` and `test:dependencies`. They cover depth rejection, adjacent parser
limits, direct AST rejection, ordinary alternatives/ranges, and real installed
watcher event controls. The watcher error controls exercise `_handleError`, not
injected real syscall failures. They do not prove every asynchronous hostile-path
error propagation case; an uncaught invalid-configuration error may still abort
a caller.

No new cardinality, expansion-size, regex-backtracking, or general glob-input
protection is claimed. Existing upstream range/length and other semantics remain.
Local tests/install/build/audit are not hosted security approval, merge, browser
E2E, Docker, backend verification, deployment, or released usability evidence.
