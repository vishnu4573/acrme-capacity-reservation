"""Build or preview a curated snapshot of the repository documentation."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "Requirements/acrme_requirements_baseline_v4_0_3.md",
    "Design/acrme_functional_design_document.md",
    "Design/acrme_technical_design_document.md",
    "Design/diagrams/acrme_v4_pipeline.mmd",
    "Design/diagrams/acrme_v4_topology.mmd",
    "Design/diagrams/acrme_v4_domain_model.mmd",
    "Design/diagrams/acrme_v4_engine_modes.mmd",
    "Architecture/e2e-deployment-flow/ACRME_E2E_Deployment_Flow_Diagrams_v2_1.md",
)
REPO_FILES = "https://github.com/vishnu4573/acrme-capacity-reservation/blob/master"
REPO_LINKS = {
    "../environment.yaml": "environment.yaml",
    "../environment_v2.yaml": "environment_v2.yaml",
    "../Requirements/acrme_requirements_baseline_v4_0_2.md": (
        "Requirements/acrme_requirements_baseline_v4_0_2.md"
    ),
    "./ACRME_End_to_End_Deployment_Flow_v2.md": (
        "Architecture/e2e-deployment-flow/ACRME_End_to_End_Deployment_Flow_v2.md"
    ),
    "./ACRME_E2E_Deployment_Flow_Diagrams_Proposed_Changes.md": (
        "Architecture/e2e-deployment-flow/ACRME_E2E_Deployment_Flow_Diagrams_Proposed_Changes.md"
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "serve"))
    args = parser.parse_args()

    output = ROOT / "site"
    marker = ".acrme-zensical-output"
    if args.command == "build" and (
        output.is_symlink() or (output.exists() and not (output / marker).is_file())
    ):
        parser.exit(1, f"Refusing to overwrite {output}: not a generated ACRME site.\n")

    with TemporaryDirectory(prefix=".zensical-", dir=ROOT) as temp:
        project = Path(temp)
        docs = project / "docs"
        docs.mkdir()
        shutil.copyfile(ROOT / "zensical.toml", project / "zensical.toml")
        shutil.copyfile(ROOT / "docs/index.md", docs / "index.md")
        for path in SOURCES:
            target = docs / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix == ".md":
                text = (ROOT / path).read_text(encoding="utf-8")
                for link, repo_path in REPO_LINKS.items():
                    text = text.replace(f"]({link})", f"]({REPO_FILES}/{repo_path})")
                target.write_text(text, encoding="utf-8")
            else:
                shutil.copyfile(ROOT / path, target)

        flags = ["--strict"] if args.command == "build" else []
        try:
            result = subprocess.run(
                [sys.executable, "-m", "zensical", args.command, *flags], cwd=project
            )
        except KeyboardInterrupt:
            return 130

        if result.returncode == 0 and args.command == "build":
            generated = project / "site"
            (generated / marker).touch()
            if output.exists():
                shutil.rmtree(output)
            generated.rename(output)
            print(f"Built documentation: {output / 'index.html'}")
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
