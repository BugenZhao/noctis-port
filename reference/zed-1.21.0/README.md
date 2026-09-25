# Pinned Zed semantic mappings

Unmodified rule snapshots from Zed 1.21.0. `sources.json` records upstream paths
and SHA-256 hashes; the upstream GPL-3.0-or-later license is included here.
These files are audit inputs and are separate from the generated theme assets.

The audit follows these source functions:

- [SemanticTokenStylizer::new](https://github.com/zed-industries/zed/blob/v1.21.0/crates/project/src/lsp_store/semantic_tokens.rs#L660): reverse user + language + default rules, filtered by token type.
- [convert_token](https://github.com/zed-industries/zed/blob/v1.21.0/crates/editor/src/semantic_tokens.rs#L413): require all modifiers, then merge matching rules per property; handle the highest-priority empty rule.
- [SyntaxTheme::style_for_name](https://github.com/zed-industries/zed/blob/v1.21.0/crates/syntax_theme/src/syntax_theme.rs#L73): exact style-name lookup.

`scripts/test_zed_renderer.py` extracts and compiles the original `convert_token`
function from a hash-verified upstream file. Its small GPUI/LSP container stubs
allow checking the audit model independently of building the Zed application.
