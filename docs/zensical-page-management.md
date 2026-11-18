# Manage pages in the local Zensical site

The site builds from a curated snapshot of repository files. Keep each Markdown
source in its usual repository folder; do not copy it into `docs/` just to make
it appear on the site.

| File | What it controls |
|---|---|
| [`tools/docs_site.py`](../tools/docs_site.py) | `SOURCES` lists the pages and assets copied into the build. Paths are relative to the repository root, and the staging step preserves them. |
| [`zensical.toml`](../zensical.toml) | `nav` controls sidebar labels, grouping, and order. Use the same paths as in `SOURCES`. |
| [`docs/index.md`](index.md) | The site home page, copied separately as `index.md`. Update it when a featured link or description changes. |

This guide and the [repository documentation index](README.md) are for contributors
reading the repository; neither is included in the generated site.

## Add a page

1. Choose an existing Markdown file or create one in the appropriate repository
   folder. Check that the page and its linked assets are appropriate for the
   curated site. Keep credentials, deployment YAML, and POC evidence out of the
   build.
2. Add the page's repository-relative path to `SOURCES` in
   [`tools/docs_site.py`](../tools/docs_site.py). For example, if you create
   `Design/review-checklist.md`, add this line inside the tuple:

   ```python
   "Design/review-checklist.md",
   ```

3. Add a matching entry to `nav` in [`zensical.toml`](../zensical.toml). For
   example, put this line inside the existing `Design` list:

   ```toml
   { "Review checklist" = "Design/review-checklist.md" },
   ```

4. Review the page's relative links and images. Add any approved local assets
   the page needs to `SOURCES`, using their exact paths; assets do not need
   `nav` entries. For a document that should remain outside the site, link to
   its repository URL instead. Add a link to [`docs/index.md`](index.md) only
   if the page should be featured on the home page.
5. Build and preview using the checks below.

## Remove or rename a page

1. To remove a page from the site without deleting the original Markdown,
   remove it from both `SOURCES` and `nav`. Removing only the `nav` entry hides
   it from the sidebar; the page can still be built and reached by URL.
2. Remove or redirect links from the home page and any remaining site pages.
   Remove assets from `SOURCES` only if no remaining page needs them.
3. For a rename or move, replace the old path in `SOURCES` and `nav`, then
   update links to the old path and relative links inside the moved page. If
   you only want to change the sidebar label or order, edit `nav` alone.
4. Rebuild and verify that the old page is absent from `site/` and no longer
   opens at its old URL in a fresh preview.

## Build and preview

From the repository root, after following the [one-time setup](../README.md#local-documentation-site):

```bash
.venv-docs/bin/python tools/docs_site.py build
.venv-docs/bin/python tools/docs_site.py serve
```

The first command runs a strict build and writes static HTML to `site/`. Fix any
reported problems, then open [the local preview](http://127.0.0.1:8000) and check
the sidebar, direct page URLs, search, and any changed links or images. Stop a
running preview with `Ctrl+C` and restart it after source or configuration
changes: each invocation stages a fresh snapshot. Edit the source files, not
the generated HTML in `site/`. Neither command publishes the site.
