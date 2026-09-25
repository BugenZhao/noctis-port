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
from the fixture. All 11 palettes matched their reference semantic styles;
**203 tokens** had a resolved semantic style and **5** rely on base syntax
highlighting in combined mode. The HTML preview displays the semantic layer.
Native Zed rendering remains unverified: the isolated app preview hit a native
window-control failure. The runtime check verifies LSP data and mapping results.

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

The theme files supply Zed's built-in styles, including parameters, fields,
lifetimes, special variables, primitive types and type declarations. The optional
configuration fragments supply additional VS Code-compatible token routing:

- `settings/standard-semantic.json`: VS Code's standard token/scope mapping.
- `settings/rust-semantic.json`: that mapping plus the local rust-analyzer
  extension's Rust-specific overrides and token inheritance.

Choose **one** fragment and merge its keys into your user `settings.json`.
Preserve existing personal semantic rules **before** the generated rules in the
array, so personal overrides retain priority. The fragments use palette style
names, allowing all 11 themes to share exactly the same rules.
The 133 Rust rules are unchanged from the initial light-theme migration, so an
existing installation's semantic configuration continues to work.

Zed 1.21's user semantic rules are global and expose type/modifier selectors,
with no language selector. The **Rust fragment prioritizes Rust parity**: its
shared token rules (notably `keyword`, `type` and `variable`) also affect other
language servers. Use the standard fragment for language-neutral behavior.
These fragments are scoped by their `noctis.*` style names: another theme will
fall through to Zed's built-in styling when those styles are absent.

## Isolated preview

```sh
python3 scripts/preview.py --theme 'Noctis Minimus'
```

This opens `examples/rust` in a separate Zed data/configuration directory under
`preview-data/`. The preview explicitly enables semantic tokens and the Rust
mapping; your normal settings, extensions and session data stay in their normal
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

VS Code resolves foreground and font style independently. A later equally
specific rule wins; `fontStyle: ""` explicitly resets bold and italic. Rust
language-specific fallback mappings receive VS Code's language-specific score.
The generator enumerates relevant modifier combinations and materializes the
resolved styles, preserving property-wise precedence in Zed's ordered rules.

Each `noctis.semantic.*` or `noctis.rust.*` style has an audit entry in
`reference/generated-mapping.json`: token type, modifiers, original scope, and
the original rule responsible for every style property. Noctis 10.40.0 has no
standalone rule styling the `markup.underline` probe, so Rust's `mutable` modifier
does not acquire an invented underline in this port.

Examples of resolved Rust styles shared by all three light variants:

| Token | Color | Font |
| --- | --- | --- |
| Parameter | `#fa8900` | Bold |
| Field/property | `#fa8900` | Italic |
| Readonly field | `#a88c00` | Italic |
| Lifetime | `#b3694d` | Bold italic |
| Primitive type | `#b3694d` | Italic |
| Function | `#0095a8` | Inherits base font |
| Rust keyword | `#e64100` | Normal |
| Rust control-flow keyword | `#ff5792` | Bold |

## Fidelity boundaries

- **Semantic styles:** resolved against the pinned VS Code and rust-analyzer
  mappings. Eight tests compare 59,136 token/modifier/theme combinations with the
  generated Zed rule order and include independent style goldens.
- **Tree-sitter:** explicit canonical TextMate probes are recorded in the
  generator's `CAPTURES`. Parser-specific captures and contextual TextMate scopes
  can differ; language-wide pixel parity remains a separate validation task.
- **UI:** `UI_MAP` identifies each direct source role; `ADAPTED_UI_MAP` documents
  the source role used for Zed-specific controls. Additional collaborator cursors
  use the source ANSI palette with a 24% selection tint. Both mappings are recorded
  in the audit manifest. Layout, antialiasing and font rendering are editor-specific.
  Unsupported VS Code UI roles stay in the source snapshot for future work.
- **Source defect:** Lilac's original `inputValidation.infoBackground` is the
  malformed `#00c6ea599ff`. This port reproduces the pinned VS Code
  `Color.fromHex` fallback (`#ff0000`) explicitly; source files stay byte-exact.
- **Personal overrides:** your `unresolvedReference` red/bold rule belongs in
  your user settings and takes precedence over the theme. It is kept separate
  from the reusable Noctis palette.

For runtime inspection, use VS Code's **Developer: Inspect Editor Tokens and
Scopes** and Zed's **dev: open highlights tree view** on the same Rust fixture.
Compare token type, modifiers, foreground, bold and italic separately.

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
