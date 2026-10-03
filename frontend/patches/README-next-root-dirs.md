# Next root discovery: bounded tinyglobby adapter

This exact-version pnpm patch is coupled to the parent-scoped
`@next/eslint-plugin-next@16.3.6>fast-glob` alias to `tinyglobby@0.2.17`.
No package manifest dependencies or Next rule implementations are patched.
The existing minimatch patch remains required.

The helper keeps its exported `getRootDirs(context)` API and the unchanged
`[context.cwd]` path when `settings.next.rootDir` is absent. Configured roots
are still evaluated against process cwd, matching the supplier. Directory
expansion is disabled; absolute output is chosen for each input independently.
Static pattern spelling (including `./` and trailing `/`) is retained, while
dynamic matches have no directory suffix. Symlink directories retain their
lexical paths through a synchronous directory-entry adapter. The adapter retains
the first non-ENOENT read/stat failure and throws it after globSync returns,
outside fdir's default synchronous error-suppression boundary. ENOENT remains
a no-match; dangling and looping symlinks remain excluded. ELOOP is ignored
only while classifying a symlink. Non-ENOENT symlink-stat failures intentionally
fail closed even though the original supplier suppresses broken-link stat errors.

Supported grammar is deliberately bounded: literals, `*`/`?` wildcards, and
one non-nested brace list with 2–16 nonempty literal alternatives. Each string
is at most 1024 characters with at most 32 wildcard characters. Globstars,
character classes, extglobs/negations, nested/multiple brace groups, and all
brace ranges (including zero-padded and stepped ranges) raise an explicit
`Unsupported Next.js rootDir glob` error before supplier parsing. These are
intentional compatibility limitations, not silently broadened matches. A `+`
anywhere in a brace-containing pattern is explicitly rejected because picomatch
can interpret brace-adjacent plus as repetition. Ordinary plus without braces
remains supported, including wildcard matches to literal-plus directory names.
Globstar rejection also bounds symlink traversal by finite pattern depth;
filesystem/result counts and large caller-provided arrays are not globally
budgeted by this patch. Platform execution here covers macOS, not Windows.

Run permanent candidate checks from frontend:

```sh
node scripts/test-external-braces.mjs
node scripts/test-next-root-dirs.mjs
```

For an actual supplier differential, install the unmodified base in an
independent directory and pass that frontend directory as the optional argument:

```sh
node scripts/test-next-root-dirs.mjs /absolute/path/to/base/frontend
node scripts/test-next-root-dirs-review.mjs /absolute/path/to/base/frontend
```

The differential resolves the real transitive plugin through eslint-config-next
and compares root results plus actual ESLint `no-html-link-for-pages` diagnostics.
The original supplier is never given pathological rejection-test inputs. The
review regression adds bounded brace-plus reproduction and filesystem seam
injection with finally restoration. Independently separated 32/33 question
wildcards, 1024/1025-character dot-prefixed paths, and 16/17 alternatives test
the exact candidate boundaries; ordinary valid positives accompany negatives.
The full-length candidate control uses repeated `./` to avoid Darwin's physical
path limit; it is not an original-supplier long-path compatibility assertion.
These scripts are explicit checks, not assumed CI wiring; package.json stays
unchanged so the integration owner can compose the checks later.

This removes the external lock/installed braces chain only. Embedded braces
implementations in Vite and Playwright remain outside this change; a clean pnpm
audit is not proof that those bundled implementations are repaired.
