#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    printf 'Usage: %s <markdown-file>\n' "$0" >&2
    exit 2
fi

input_file=$1
if [[ ! -f "$input_file" ]]; then
    printf 'Markdown file not found: %s\n' "$input_file" >&2
    exit 2
fi

if ! command -v pandoc >/dev/null 2>&1; then
    printf 'Pandoc is required. Install Pandoc and retry.\n' >&2
    exit 127
fi

formatted_file=$(mktemp)
before_html=$(mktemp)
after_html=$(mktemp)
trap 'rm -f "$formatted_file" "$before_html" "$after_html"' EXIT

pandoc --from=gfm --to=gfm --wrap=none "$input_file" --output="$formatted_file"
pandoc --from=gfm --to=html5 "$input_file" --output="$before_html"
pandoc --from=gfm --to=html5 "$formatted_file" --output="$after_html"

if ! diff -u "$before_html" "$after_html"; then
    printf 'Rendered output changed; original file was left unchanged.\n' >&2
    exit 1
fi

if cmp -s "$input_file" "$formatted_file"; then
    printf 'Already formatted: %s\n' "$input_file"
    exit 0
fi

cp "$formatted_file" "$input_file"
printf 'Reflowed Markdown: %s\n' "$input_file"
