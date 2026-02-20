from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

CONTAINER_XML = """<?xml version='1.0' encoding='UTF-8'?>
<container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>
  <rootfiles>
    <rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/>
  </rootfiles>
</container>
"""

NAV_TEMPLATE = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns='http://www.w3.org/1999/xhtml' xmlns:epub='http://www.idpf.org/2007/ops'>
  <head><title>TOC</title></head>
  <body>
    <nav epub:type='toc' id='toc'>
      <ol>
        {items}
      </ol>
    </nav>
  </body>
</html>
"""

NCX_TEMPLATE = """<?xml version='1.0' encoding='UTF-8'?>
<ncx xmlns='http://www.daisy.org/z3986/2005/ncx/' version='2005-1'>
  <head><meta name='dtb:uid' content='uid'/></head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
    {navpoints}
  </navMap>
</ncx>
"""

OPF_TEMPLATE = """<?xml version='1.0' encoding='UTF-8'?>
<package xmlns='http://www.idpf.org/2007/opf' version='3.0' unique-identifier='bookid'>
  <metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>
    <dc:identifier id='bookid'>urn:uuid:test-{name}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id='nav' href='nav.xhtml' media-type='application/xhtml+xml' properties='nav'/>
    <item id='ncx' href='toc.ncx' media-type='application/x-dtbncx+xml'/>
    {manifest_items}
  </manifest>
  <spine toc='ncx'>
    {spine_items}
  </spine>
</package>
"""

XHTML_TEMPLATE = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns='http://www.w3.org/1999/xhtml' xmlns:epub='http://www.idpf.org/2007/ops'>
  <head><title>{title}</title></head>
  <body>
    {body}
  </body>
</html>
"""


def make_epub(name: str, chapters: list[tuple[str, str]], expected: dict) -> None:
    epub_path = FIX / f"{name}.epub"
    expected_path = FIX / f"{name}.expected_checks.json"

    nav_items = []
    nav_points = []
    manifest_items = []
    spine_items = []

    files: dict[str, str] = {
        "mimetype": "application/epub+zip",
        "META-INF/container.xml": CONTAINER_XML,
    }

    for idx, (title, body) in enumerate(chapters, start=1):
        chap = f"ch{idx}.xhtml"
        files[f"OEBPS/{chap}"] = XHTML_TEMPLATE.format(title=title, body=body)
        manifest_items.append(f"<item id='c{idx}' href='{chap}' media-type='application/xhtml+xml'/>")
        spine_items.append(f"<itemref idref='c{idx}'/>")
        nav_items.append(f"<li><a href='{chap}#s{idx}'>{title}</a></li>")
        nav_points.append(
            f"<navPoint id='np{idx}' playOrder='{idx}'><navLabel><text>{title}</text></navLabel><content src='{chap}#s{idx}'/></navPoint>"
        )

    files["OEBPS/nav.xhtml"] = NAV_TEMPLATE.format(items="\n".join(nav_items))
    files["OEBPS/toc.ncx"] = NCX_TEMPLATE.format(title=name, navpoints="\n".join(nav_points))
    files["OEBPS/content.opf"] = OPF_TEMPLATE.format(
        name=name,
        title=name,
        manifest_items="\n".join(manifest_items),
        spine_items="\n".join(spine_items),
    )

    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", files["mimetype"], compress_type=zipfile.ZIP_STORED)
        for rel, text in files.items():
            if rel == "mimetype":
                continue
            zf.writestr(rel, text.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)

    expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    FIX.mkdir(parents=True, exist_ok=True)

    make_epub(
        "fixture_basic",
        [
            (
                "Chapter One",
                """
<section id='s1'>
  <h1 id='h1'>Chapter One</h1>
  <p id='p1'>Norman Conquest happened in 1066.</p>
  <ul><li id='li1'>First item</li><li id='li2'>Second item</li></ul>
</section>
""",
            )
        ],
        {
            "must_keep_ids": ["s1", "h1", "p1", "li1", "li2"],
            "must_keep_hrefs": ["ch1.xhtml#s1"],
            "quote_translation_nodes": 0,
        },
    )

    make_epub(
        "fixture_footnotes",
        [
            (
                "Footnotes",
                """
<section id='s1'>
  <p id='p1'>Text with note <a id='nref1' epub:type='noteref' href='#fn1'>1</a>.</p>
  <aside id='fn1' epub:type='footnote'><p id='fnp1'>Footnote body <a href='#nref1'>back</a></p></aside>
</section>
""",
            )
        ],
        {
            "must_keep_ids": ["s1", "p1", "nref1", "fn1", "fnp1"],
            "must_keep_hrefs": ["#fn1", "#nref1", "ch1.xhtml#s1"],
            "quote_translation_nodes": 0,
        },
    )

    make_epub(
        "fixture_quotes",
        [
            (
                "Quotes",
                """
<section id='s1'>
  <blockquote id='bq1'><p>Arma virumque cano.</p></blockquote>
  <blockquote id='bq2'><p>The die is cast.</p></blockquote>
  <blockquote id='bq3'><p>Et tu, Brute?</p></blockquote>
  <p id='pq1'>He said <q id='q1'>alea iacta est</q> in Rome.</p>
  <p id='pq2'>She wrote <q id='q2'>veni vidi vici</q> at dawn.</p>
  <p id='pq3'>They repeated <q id='q3'>carpe diem</q> daily.</p>
  <p id='pc1'><cite id='c1'>Tacitus</cite> recorded events.</p>
  <p id='pc2'><cite id='c2'>Caesar</cite> described war.</p>
  <p id='pc3'><cite id='c3'>Livy</cite> narrated history.</p>
</section>
""",
            )
        ],
        {
            "must_keep_ids": ["s1", "bq1", "bq2", "bq3", "q1", "q2", "q3", "c1", "c2", "c3"],
            "must_keep_hrefs": ["ch1.xhtml#s1"],
            "quote_translation_nodes": 9,
        },
    )

    make_epub(
        "fixture_poetry",
        [
            (
                "Poetry",
                """
<section id='s1'>
  <div id='poem1' class='poem'>
    <p>Line one<br/>Line two<br/>Line three</p>
  </div>
</section>
""",
            )
        ],
        {
            "must_keep_ids": ["s1", "poem1"],
            "must_keep_hrefs": ["ch1.xhtml#s1"],
            "quote_translation_nodes": 0,
        },
    )

    make_epub(
        "fixture_tables",
        [
            (
                "Tables",
                """
<section id='s1'>
  <table id='t1'>
    <tr><th id='th1'>Year</th><th id='th2'>Status</th></tr>
    <tr><td id='td1'>1066</td><td id='td2'>c.</td></tr>
    <tr><td id='td3'>1170</td><td id='td4'>fl.</td></tr>
  </table>
</section>
""",
            )
        ],
        {
            "must_keep_ids": ["s1", "t1", "th1", "th2", "td1", "td2", "td3", "td4"],
            "must_keep_hrefs": ["ch1.xhtml#s1"],
            "quote_translation_nodes": 0,
        },
    )

    make_epub(
        "fixture_code",
        [
            (
                "Code",
                """
<section id='s1'>
  <pre id='pre1'>for i in range(3):\n    print(i)</pre>
  <code id='code1'>SELECT * FROM users WHERE id = 1;</code>
  <p id='p1'>Normal text around code.</p>
</section>
""",
            )
        ],
        {
            "must_keep_ids": ["s1", "pre1", "code1", "p1"],
            "must_keep_hrefs": ["ch1.xhtml#s1"],
            "quote_translation_nodes": 0,
        },
    )


if __name__ == "__main__":
    main()
