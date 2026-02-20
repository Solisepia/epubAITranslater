from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

from .models import BookModel

CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
OPF_NS = {"opf": "http://www.idpf.org/2007/opf"}


def unpack_epub(epub_path: str, keep_workdir: bool = False) -> BookModel:
    src = Path(epub_path)
    if not src.exists():
        raise FileNotFoundError(f"Input EPUB not found: {epub_path}")

    workdir = Path(tempfile.mkdtemp(prefix="epub2zh_"))
    with zipfile.ZipFile(src, "r") as zf:
        zf.extractall(workdir)

    container_path = workdir / "META-INF" / "container.xml"
    if not container_path.exists():
        raise ValueError("Invalid EPUB: META-INF/container.xml missing")

    container_tree = etree.parse(str(container_path))
    rootfile = container_tree.xpath("string(/c:container/c:rootfiles/c:rootfile/@full-path)", namespaces=CONTAINER_NS)
    if not rootfile:
        raise ValueError("Invalid EPUB: OPF rootfile not found in container.xml")

    opf_path = workdir / rootfile
    if not opf_path.exists():
        raise ValueError(f"Invalid EPUB: OPF file missing: {rootfile}")

    opf_tree = etree.parse(str(opf_path))
    opf_dir = opf_path.parent

    manifest_by_id: dict[str, dict[str, str]] = {}
    for item in opf_tree.xpath("/opf:package/opf:manifest/opf:item", namespaces=OPF_NS):
        item_id = item.get("id") or ""
        manifest_by_id[item_id] = {
            "href": item.get("href", ""),
            "media-type": item.get("media-type", ""),
            "properties": item.get("properties", ""),
        }

    spine_items: list[str] = []
    xhtml_files: list[str] = []
    for itemref in opf_tree.xpath("/opf:package/opf:spine/opf:itemref", namespaces=OPF_NS):
        idref = itemref.get("idref")
        if not idref or idref not in manifest_by_id:
            continue
        spine_items.append(idref)
        href = manifest_by_id[idref]["href"]
        if href:
            xhtml_files.append(str((opf_dir / href).resolve().relative_to(workdir.resolve())))

    toc_nav_path = _find_epub3_nav(manifest_by_id, opf_dir, workdir)
    toc_ncx_path = _find_epub2_ncx(opf_tree, manifest_by_id, opf_dir, workdir)

    return BookModel(
        workspace_dir=str(workdir),
        rootfile_path=rootfile,
        opf_path=str(opf_path.resolve().relative_to(workdir.resolve())),
        opf_dir=str(opf_dir.resolve().relative_to(workdir.resolve())),
        spine_items=spine_items,
        xhtml_files=xhtml_files,
        manifest_by_id=manifest_by_id,
        toc_nav_path=toc_nav_path,
        toc_ncx_path=toc_ncx_path,
    )


def cleanup_workspace(workdir: str, keep: bool) -> None:
    if keep:
        return
    shutil.rmtree(workdir, ignore_errors=True)


def _find_epub3_nav(manifest_by_id: dict[str, dict[str, str]], opf_dir: Path, workdir: Path) -> str | None:
    for item in manifest_by_id.values():
        if "nav" in item.get("properties", "").split() and item.get("href"):
            return str((opf_dir / item["href"]).resolve().relative_to(workdir.resolve()))
    return None


def _find_epub2_ncx(opf_tree: etree._ElementTree, manifest_by_id: dict[str, dict[str, str]], opf_dir: Path, workdir: Path) -> str | None:
    toc_id = opf_tree.xpath("string(/opf:package/opf:spine/@toc)", namespaces=OPF_NS)
    if toc_id and toc_id in manifest_by_id:
        href = manifest_by_id[toc_id].get("href", "")
        if href:
            return str((opf_dir / href).resolve().relative_to(workdir.resolve()))

    for item in manifest_by_id.values():
        if item.get("media-type") == "application/x-dtbncx+xml" and item.get("href"):
            return str((opf_dir / item["href"]).resolve().relative_to(workdir.resolve()))
    return None
