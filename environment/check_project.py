"""Check repository-local links and CAD dependencies after moving project files."""
import ast
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    errors = []
    counts = {"python_files": 0, "markdown_links": 0, "cad_references": 0}
    for folder in ("environment", "hw/tools", "hw/tests", "sw/interfaces/python", "sw/pi", "sw/fpga", "sw/tools", "sw/tests", "sw/ui", "sw/supervisor"):
        for path in (root / folder).rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            counts["python_files"] += 1
    documents = [root / "README.md", root / "AGENTS.md"]
    for folder in ("docs", "sw", "hw"):
        documents.extend((root / folder).rglob("*.md"))
    for path in documents:
        # Vendored README snapshots refer to the upstream tree, only part of
        # which is retained here. Preserve them verbatim and check our own docs.
        if path.is_relative_to(root / "hw/shared/vendor"):
            continue
        text = path.read_text(encoding="utf-8")
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            link = link.strip("<>")
            if urlsplit(link).scheme or link.startswith("#"):
                continue
            target = unquote(link.split("#", 1)[0])
            if not (path.parent / target).exists():
                errors.append(f"{path.relative_to(root)}: missing link {link}")
            counts["markdown_links"] += 1
    cad_folders = [folder for product in (root / "hw").iterdir() if product.is_dir()
                   for folder in (product / "boards", product / "layout") if folder.is_dir()]
    for path in (path for folder in cad_folders for path in folder.rglob("*")):
        if path.suffix != ".kicad_pcb" and path.name not in ("fp-lib-table", "sym-lib-table"):
            continue
        for ref in re.findall(r'"\$\{KIPRJMOD\}/([^"\n]+)"', path.read_text(encoding="utf-8")):
            if not (path.parent / ref).exists():
                errors.append(f"{path.relative_to(root)}: missing CAD dependency {ref}")
            counts["cad_references"] += 1
    if errors:
        raise RuntimeError("\n".join(errors))
    print("PASS repository structure:", counts)
    return counts


if __name__ == "__main__":
    check()
