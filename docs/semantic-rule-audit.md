# Zed default mapping audit

## Adopted behavior

The theme now uses **Zed's native LSP → language/default mappings → theme
styles** chain, with **zero custom Noctis rules**. Zed/VS Code mapping differences
are accepted. The 133-rule parity profile and its generated custom style names
have been removed; personal overrides remain independent.

The source audit below explains the previous parity profile's behavior. Its
safe-deletion experiment is historical evidence; the adopted native chain uses
all built-in mappings directly.

Audited on 2026-09-25 against the installed Zed 1.21.0, all 11 generated Noctis
themes, and the former semantic profiles. This audit holds the theme files
fixed and compares complete semantic overlays, including missing properties.

## Former parity-profile comparison

| Profile | Former rules | Safely removable for parity | Retained for parity | Exhaustive cases |
| --- | ---: | ---: | ---: | ---: |
| Standard | 30 | 18 | 12 | 682 |
| Rust | 133 | 27 | 106 | 2,750 |

For each token type, the audit enumerates every subset of all modifiers used by
any applicable user or built-in rule. Other modifiers cannot affect rule
matching. Every case is checked across all 11 themes. Greedy rule deletion
preserves the complete original overlay, including unspecified properties;
these counts describe a safe subset, rather than a globally minimal rewrite.
The comparison reconstructs the former profiles in memory. The audit command
itself leaves installed settings and generated themes untouched.

The Rust fixture returned **208 actual rust-analyzer tokens**. Using only Zed's
built-in mappings changes **59 tokens in each theme**. Using the reduced Rust
profile preserves **all 2,288 token/theme comparisons**.

Examples for Noctis Hibernus:

| Token | Former parity mapping | Adopted Zed built-in mapping |
| --- | --- | --- |
| `static` keyword | `#e64100`, regular | `#ff5792`, bold |
| `usize` | `#b3694d`, italic | `#0094f0`, regular |
| mutable `item` | `#00bdd6` | `#fa8900` |
| `self` | regular | italic |

The 59 differences comprise 24 keywords, 10 format specifiers, nine primitive
types, six `self` tokens, four variables, three methods, two `Self` tokens, and
one static variable. Parameters, fields, lifetimes, and many other tokens in
this fixture already receive matching styles through Zed's mappings.

## Why theme colors alone cannot preserve every distinction

The built-in rules route both ordinary and `controlFlow` keywords to the same
`keyword` style. They route `builtinType`, `selfTypeKeyword`, and ordinary `type`
tokens to `type`. The default variable rule also ignores `mutable`. Each of
these merges token categories that Noctis styles differently. User routing rules
can preserve those distinctions; changing a single shared theme style affects
every category that reaches it.

The retired generated profile expands modifier combinations, including
`*.mutable`, into type-specific rules. Much of its size comes from this
expansion. Further compression would require a separate rewrite (for example,
factoring shared modifier behavior), with checks for precedence, unknown token
types, other languages, and personal overrides.

## Source and test coverage

See the [pinned sources](../reference/zed-1.21.0/README.md). The source pipeline
reverses user, language, and default rules, then merges every matching rule per
style property. Theme style lookup is exact; each rule tries its style names in
order. An empty highest-priority rule has a separate suppression path.

The audit and HTML preview model that complete pipeline. The older 59,136-case test compares
the generated custom layer with the VS Code reference resolver; it continues to
pass and serves a different purpose.

An independent Rust harness compiles the **unmodified, hash-verified Zed
`convert_token` function** with small GPUI/LSP container stubs. All **10,296
overlays** from the original, reduced, and built-in-only profiles agree with the
audit model. This validates the semantic renderer function; native editor
painting and composition with Tree-sitter remain outside this test.

## Reproduce

```sh
python3 scripts/inspect_rust_tokens.py \
  --rust-analyzer /absolute/path/to/rust-analyzer \
  --output preview-data/audit/preview.html \
  --tokens-output preview-data/audit/tokens.json

python3 scripts/audit_semantic_rules.py \
  --tokens preview-data/audit/tokens.json \
  --output preview-data/audit/report.json

curl -fL https://raw.githubusercontent.com/zed-industries/zed/v1.21.0/crates/editor/src/semantic_tokens.rs \
  -o preview-data/audit/zed-semantic-tokens.rs
python3 scripts/test_zed_renderer.py \
  --source preview-data/audit/zed-semantic-tokens.rs \
  --work-dir preview-data/audit/rust-probe

python3 scripts/test_themes.py
python3 scripts/generate_themes.py --check
```

`report.json` includes every differing case and the complete retained/removed
rule lists. Both audit commands leave the theme and settings files unchanged.
