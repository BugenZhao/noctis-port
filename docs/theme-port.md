# Noctis themes and semantic highlighting

[Open the live theme and token preview](https://bugenzhao.github.io/noctis-port/).

All **11 original themes** are generated from the user's locally installed
**liviuschera.noctis 10.40.0**: three light and eight dark. The catalog in
`reference/theme-catalog.json` records each advertised name and appearance.
The three light themes use the original names Noctis Hibernus, Noctis Lilac and
Noctis Lux. The picker contains exactly the 11 original names.

Appearance follows the extension's `package.json` registration (`uiTheme`), as
VS Code does. The original port assigned dark appearances to these three
canonical names; they now match their light VS Code originals. Lilac's source
theme JSON also has a stale `type: dark`, while its package registration is `vs`.

## Reproduce and check

```sh
python3 scripts/import_sources.py --extension /path/to/liviuschera.noctis-10.40.0
python3 scripts/generate_themes.py
python3 scripts/generate_themes.py --check
python3 scripts/test_themes.py
```

Python's standard library is sufficient. Source themes and their MIT license are
in `reference/noctis-10.40.0/`; `reference/sources.json` records SHA-256 hashes.
Generation covers every catalog entry. Each file is rebuilt
entirely from source data and explicit mappings, so deleting a generated theme
and rerunning the generator produces the same result. The old
`generate_light_themes.py` and `test_light_themes.py` entry points forward to the
full-catalog workflow.

To query an actual installed rust-analyzer and generate an inspectable HTML
preview (plus a JSON verification report):

```sh
python3 scripts/inspect_rust_tokens.py \
  --rust-analyzer /absolute/path/to/rust-analyzer \
  --output docs/preview.html
```

The implementation run used rust-analyzer `2026-01-19` and received **208 tokens**
from the fixture. Every token resolves through Zed's built-in Rust/default rules
in all 11 palettes. The HTML shows the resulting semantic overlay and the rule,
style name, and source palette behind each token. Native Zed layout and
Tree-sitter composition have separate coverage; see the [audit](semantic-rule-audit.md).

## Use the themes

Install this checkout as a development extension with **zed: install dev extension**,
or copy the generated theme JSON files into Zed's `themes` configuration directory.
Select a Noctis theme in the theme picker; see the catalog table in the README.

Enable LSP semantic highlighting with:

```json
{
  "semantic_tokens": "combined"
}
```

The native chain is **language server → Zed language/default mappings → theme
syntax styles**. The theme supplies names such as `variable.parameter`,
`property`, `lifetime`, `type`, and `keyword`. Zed chooses the mapping, and Noctis
supplies the palette and font styles. Differences from VS Code's token routing
are expected and accepted.

Installation requires zero Noctis-specific `semantic_token_rules`. Earlier
versions supplied generated `noctis.rust.*` / `noctis.semantic.*` routing rules;
remove those rules from your settings when upgrading. Keep personal overrides
such as an unresolved-reference color rule.

## Optional mutable and self refinements

Append the three rules in [mut-self-semantic.json](../settings/mut-self-semantic.json)
to `global_lsp_settings.semantic_token_rules`, after personal overrides:

```json
[
  { "token_modifiers": ["mutable"], "style": ["noctis.mutable"] },
  { "token_type": "selfKeyword", "style": ["noctis.self"] },
  { "token_type": "selfTypeKeyword", "style": ["noctis.self"] }
]
```

`noctis.mutable` takes its color from Noctis's `markup.underline` scope and
preserves the token's existing font style. It applies to every token the server
marks mutable, including variables, parameters, fields and methods.
`noctis.self` uses `keyword.other.rust`, restoring `self` and `Self` to the source
keyword color and regular font. With `&mut self`, the first rule wins for color,
and the self rule supplies font styling.

Rules are global in Zed 1.21: the mutable refinement also applies to other
languages that report that modifier. All 11 themes supply the two styles.
Other themes fall through to their native styles when these names are absent.
The literal `mut` keyword keeps Zed's native keyword mapping; the semantic
`mutable` modifier describes the referenced symbol's mutability.

The HTML and isolated previews include these three rules. In the HTML side
panel, **Enable custom rules** toggles all three together and immediately updates
both the code and selected token inspector. The toggle stays in its chosen mode
when switching themes. All other routing uses Zed's built-in mappings.

## Isolated preview

```sh
python3 scripts/preview.py --theme 'Noctis Minimus'
```

This opens `examples/rust` in a separate Zed data/configuration directory under
`preview-data/`. The preview enables semantic tokens and the optional mutable/self refinements; your normal settings, extensions and session data stay in their normal
directory. Use `--rust-analyzer /absolute/path/to/rust-analyzer` to reuse a
particular installed binary. `--prepare-only` writes the isolated profile without
launching Zed. The launcher sets `ZED_STATELESS=1` for the preview process to
bypass macOS's bundle-based single-instance check; preview logs and the launcher
PID are saved under the chosen data directory.

## Mapping contract

The conversion follows these pinned inputs:

1. Noctis **10.40.0** `tokenColors` and UI colors from the local extension.
2. VS Code **1.138.0**, commit
   [`7debcd0e2acdea1c52de81bf9ee1620444407dda`](https://github.com/microsoft/vscode/tree/7debcd0e2acdea1c52de81bf9ee1620444407dda):
   [scope resolution and semantic style merging](https://github.com/microsoft/vscode/blob/7debcd0e2acdea1c52de81bf9ee1620444407dda/src/vs/workbench/services/themes/common/colorThemeData.ts)
   and [standard token scope definitions and selector scoring](https://github.com/microsoft/vscode/blob/7debcd0e2acdea1c52de81bf9ee1620444407dda/src/vs/platform/theme/common/tokenClassificationRegistry.ts).
3. Locally installed **rust-lang.rust-analyzer 0.3.3057** `package.json`:
   `semanticTokenTypes` and `semanticTokenScopes`. Extracted mapping data lives in
   `reference/semantic-scopes.json`.
4. Zed **1.21.0** [default semantic rules](https://github.com/zed-industries/zed/blob/v1.21.0/assets/settings/default_semantic_token_rules.json),
   [Rust rules](https://github.com/zed-industries/zed/blob/v1.21.0/crates/grammars/src/rust/semantic_token_rules.json),
   and [the renderer](https://github.com/zed-industries/zed/blob/v1.21.0/crates/editor/src/semantic_tokens.rs).

The theme generator resolves Noctis foreground and font style independently
for each native Zed style name. Its `CAPTURES` table records the canonical
TextMate probes; `reference/generated-mapping.json` records each source rule.
These source-color probes build the theme. Runtime LSP token routing is handled
by Zed's built-in rules, with snapshots in `reference/zed-1.21.0` used by the
preview and tests.

Examples of Zed's native Rust mapping for all three light variants:

| Token | Theme style | Color | Font |
| --- | --- | --- | --- |
| Parameter | `variable.parameter` | `#fa8900` | Bold |
| Field | `property` | `#fa8900` | Italic |
| Lifetime | `lifetime` | `#b3694d` | Bold italic |
| Primitive type | `type` | `#0094f0` | Regular |
| Function | `function` | `#0095a8` | Regular |
| Keyword | `keyword` | `#ff5792` | Bold |

## Fidelity boundaries

- **Semantic styles:** native Zed mapping governs the token categories. Tests
  verify style coverage and actual LSP tokens, and compare the model with the
  pinned Zed renderer function. The [audit](semantic-rule-audit.md) records the
  intentional differences from the former VS Code-compatible profile.
- **Tree-sitter:** explicit canonical TextMate probes are recorded in the
  generator's `CAPTURES`. Parser-specific captures and contextual TextMate scopes
  can differ; language-wide pixel parity remains a separate validation task.
- **UI:** `UI_MAP` identifies each direct source role; `ADAPTED_UI_MAP` documents
  the source role used for Zed-specific controls. Additional collaborator cursors
  use the source ANSI palette with a 24% selection tint. Both mappings are recorded
  in the audit manifest. Layout, antialiasing and font rendering are editor-specific.
  Unsupported VS Code UI roles stay in the source snapshot for future work.
  Zed's shared `hint` foreground uses Noctis `descriptionForeground`, giving
  inline Git blame and hint-level messages a muted auxiliary-text color.
- **Source defect:** Lilac's original `inputValidation.infoBackground` is the
  malformed `#00c6ea599ff`. This port reproduces the pinned VS Code
  `Color.fromHex` fallback (`#ff0000`) explicitly; source files stay byte-exact.
- **Personal overrides:** your `unresolvedReference` red/bold rule belongs in
  your user settings and takes precedence over the theme. It is kept separate
  from the reusable Noctis palette.

For runtime inspection, use Zed's **dev: open highlights tree view** on the Rust
fixture to inspect token types, modifiers, and styles.

References: [VS Code semantic highlighting](https://code.visualstudio.com/api/language-extensions/semantic-highlight-guide),
[Zed semantic tokens](https://zed.dev/docs/semantic-tokens),
[Zed theme format](https://zed.dev/docs/extensions/themes).

## GitHub Pages

The public preview is hosted at <https://bugenzhao.github.io/noctis-port/>.
`.github/workflows/pages.yml` copies the committed `docs/preview.html` to the
site root and deploys it using GitHub Actions. Preview or workflow changes on
`main` trigger a deployment; maintainers can also use **Run workflow**.

Regenerate the HTML with `inspect_rust_tokens.py`, review it locally, and commit
it with the corresponding theme changes. The adjacent JSON verification report
and LSP log are local artifacts covered by `.gitignore`. Deployment uses the
committed HTML and requires no language-server download or frontend build.
