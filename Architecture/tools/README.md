# Documentation tools

## Reflow Markdown

[`reflow_markdown.sh`](./reflow_markdown.sh) reflows GitHub-Flavored Markdown
(GFM) so each paragraph and list item is stored as a single source line. Editors
with word wrap enabled will display the text across the available viewport width.

The script uses Pandoc to format the file, then renders the original and formatted
versions to HTML and compares them. It updates the file only when the rendered
output is identical; if the output differs, the original is left unchanged.

### Prerequisites

- Bash
- Pandoc
- `diff`, `cmp`, and `mktemp` (standard on macOS and common Linux distributions)

### Usage

From the repository root:

```bash
./Architecture/tools/reflow_markdown.sh Requirements/acrme_requirements_baseline_v4_0_3.md
```

The script updates the specified file in place after the rendered-output check.
Review the result with:

```bash
git diff --check
git diff -- Requirements/acrme_requirements_baseline_v4_0_3.md
```

Pass any GFM-compatible Markdown file as the sole argument. Files using syntax
outside GFM may be rejected if Pandoc's rendered output changes; in that case,
the script prints the HTML difference and leaves the input untouched.
