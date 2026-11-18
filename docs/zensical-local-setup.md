# Zensical: local setup, preview, and maintenance

Zensical turns Markdown into a searchable documentation site. It works in any
repository, even if the application itself does not use Python. The steps
below set up a local preview; they do not publish anything.

## 1. Install Zensical

Open a terminal at the repository root. If the repo already has
`zensical.toml` or `mkdocs.yml`, follow its README and use its existing
dependency file and commands. Do not initialize a second site over it.
For this repo, see [ACRME's setup](#use-the-existing-acrme-site).

Use Python 3.11 or newer and install Zensical in a docs-only virtual environment:

**macOS / Linux**

```bash
python3 --version
python3 -m venv .venv-docs
.venv-docs/bin/python -m pip install zensical
.venv-docs/bin/python -m zensical --version
```

**Windows PowerShell**

```powershell
py -3 --version
py -3 -m venv .venv-docs
.\.venv-docs\Scripts\python.exe -m pip install zensical
.\.venv-docs\Scripts\python.exe -m zensical --version
```

If `py` is not available on Windows, use `python` after checking its version.
The examples below use `.venv-docs/bin/python`; on Windows, substitute
`.\.venv-docs\Scripts\python.exe`. No activation is needed.

## 2. Create the site files

For an existing repo without a site, start with the files below. Reuse an
existing docs folder only if its contents belong in the site. Otherwise, use
a dedicated folder such as `site-docs/` and set `docs_dir` accordingly. Do not
set `docs_dir` to the repository root. If `site/` already serves another
purpose, choose an unused `site_dir`: Zensical writes generated output there.

```text
repo/
├── zensical.toml
└── docs/
    ├── index.md
    └── getting-started.md
```

Create `zensical.toml` at the repository root:

```toml
[project]
site_name = "My Project Docs"
docs_dir = "docs"
site_dir = "site"
dev_addr = "127.0.0.1:8000"
nav = [
  { Home = "index.md" },
  { "Getting started" = "getting-started.md" },
]
```

Create `docs/index.md` with `# My Project Docs` as its first heading and add
`[Getting started](getting-started.md)` to link to the second page. Create
`docs/getting-started.md` with a `# Getting started` heading and a few lines
about your project. Paths in `nav` are relative to `docs_dir`, not the repo root.

For a fresh, empty project, you can instead run
`.venv-docs/bin/python -m zensical new .` to generate starter files. Review what
it adds before committing, including any generated GitHub Actions workflow.
Leave deployment workflows out if you only want a local site.

If the repo already uses MkDocs and you want to migrate, start with the
[MkDocs migration guide](https://zensical.org/docs/compatibility/mkdocs/migration/)
and check that the settings and plugins you rely on are supported.

## 3. Preview and build locally

From the folder containing `zensical.toml`, run:

```bash
.venv-docs/bin/python -m zensical serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). A standard Zensical
preview rebuilds and reloads as you save Markdown changes. Keep the terminal
open while you work and press `Ctrl+C` to stop the server. If port 8000 is
busy, run `serve --dev-addr 127.0.0.1:8001` in place of `serve` and open
[http://127.0.0.1:8001](http://127.0.0.1:8001).

Before sharing changes, run a strict build:

```bash
.venv-docs/bin/python -m zensical build --strict
```

Fix reported issues, then check changed pages, links, images, and search in
the browser. The static output goes to `site/` by default. Edit the source
Markdown and configuration, not the generated HTML.

## 4. Manage the site

| Task | What to change |
|---|---|
| Add a page | Add a Markdown file under `docs_dir` and an entry in `nav` if it belongs in the sidebar. |
| Reorder or relabel pages | Edit the order or labels in `nav`. Changing a label does not rename the file. |
| Move or rename a page | Update its `nav` entry, links to the old path, and relative links inside the moved page. |
| Remove a page | Move it out of `docs_dir` or exclude it with `exclude_docs`. Remove its navigation entry and update incoming links. Removing only its `nav` entry does not prevent it from being built or opened by URL. |
| Add images or downloads | Store approved files under `docs_dir` (for example, in `assets/`) and link to them using paths relative to the Markdown page. Assets do not need sidebar entries. |
| Change the home page or theme | Edit `index.md` for home-page content, `site_name` for the title, or `[project.theme]` for theme settings. |

Keep secrets, private data, and unrelated files outside `docs_dir`. Treat the
whole generated output as shareable, not just the pages visible in the sidebar.

For a team, put `zensical==<tested-version>` in `requirements-docs.txt`,
replacing `<tested-version>` with the output of the version command. Commit
the Markdown, assets, configuration, and dependency file. Add `/.venv-docs/`
and `/site/` (or your chosen output folder) to `.gitignore` if those paths are
dedicated to this setup.

On a new checkout, create the virtual environment and use the pinned file
instead of installing the latest release:

```bash
.venv-docs/bin/python -m pip install -r requirements-docs.txt
```

To upgrade, change the pin on a branch, install from that file again, and run
`build --clean --strict`. Verify the preview before merging. The same strict
build can run in CI without a publishing step.

## Troubleshooting

| Symptom | Check |
|---|---|
| `No module named zensical` | Install with the same virtual environment's Python that runs the preview. |
| Configuration not found | Run from the folder with `zensical.toml`, or pass `--config-file` with its path. |
| Page is missing or link is broken | Check the exact filename and capitalization, its path relative to `docs_dir` in `nav`, and its path relative to the linking page in Markdown. |
| Preview looks stale or config changes do not appear | Stop and restart `serve`. If build output still looks wrong, try `build --clean --strict`. |

## Use the existing ACRME site

Follow the [ACRME README](../README.md#local-documentation-site) to install
the pinned version and run `tools/docs_site.py serve` or `tools/docs_site.py build`
with the virtual environment's Python. Use the wrapper rather than the direct
Zensical commands above: it stages only the approved pages and assets from their
original repository folders. Because the preview serves a staged snapshot, stop
and restart it after source or configuration changes.

See [Manage pages in the local Zensical site](zensical-page-management.md) for
the ACRME-specific steps for adding, removing, and renaming pages.

Official references: [Installation](https://zensical.org/docs/get-started/),
[Preview](https://zensical.org/docs/usage/preview/),
[Build](https://zensical.org/docs/usage/build/), and
[Configuration](https://zensical.org/docs/setup/basics/).
