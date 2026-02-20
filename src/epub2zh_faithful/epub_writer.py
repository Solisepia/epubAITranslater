from __future__ import annotations

import zipfile
from pathlib import Path


def repack_epub(workdir: str, output_epub: str) -> None:
    root = Path(workdir)
    out = Path(output_epub)
    out.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out, "w") as zf:
        mimetype = root / "mimetype"
        if mimetype.exists():
            zf.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel == "mimetype":
                continue
            zf.write(path, rel, compress_type=zipfile.ZIP_DEFLATED)
