import pytest

from content_rewriter.documents import (
    Kind,
    UnsupportedFormat,
    kind_of,
    load,
    output_path_for,
    save,
    supported_filter,
)


@pytest.mark.parametrize("suffix", [".txt", ".md", ".markdown"])
def test_plain_text_round_trip(tmp_path, suffix):
    source = tmp_path / f"input{suffix}"
    source.write_text("# Heading\n\nbody text\n", encoding="utf-8")

    assert load(source) == "# Heading\n\nbody text\n"

    target = tmp_path / f"output{suffix}"
    save(target, "new body")
    assert target.read_text(encoding="utf-8") == "new body"


def test_docx_round_trip(tmp_path):
    docx = pytest.importorskip("docx")

    source = tmp_path / "input.docx"
    document = docx.Document()
    document.add_paragraph("first paragraph")
    document.add_paragraph("second paragraph")
    document.save(source)

    assert load(source) == "first paragraph\n\nsecond paragraph"

    target = tmp_path / "output.docx"
    save(target, "alpha\n\nbeta")
    assert [p.text for p in docx.Document(target).paragraphs] == ["alpha", "beta"]


@pytest.mark.parametrize("name", ["input.pdf", "legacy.doc", "sheet.xlsx"])
def test_unknown_extension_rejected(tmp_path, name):
    source = tmp_path / name
    source.write_bytes(b"\x00binary")
    with pytest.raises(UnsupportedFormat):
        load(source)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "absent.txt")


def test_output_path_keeps_format_and_marks_name(tmp_path):
    assert output_path_for(tmp_path / "essay.md").name == "essay.rewritten.md"
    assert output_path_for(tmp_path / "essay.docx").name == "essay.rewritten.docx"


def test_docx_structure_becomes_markdown(tmp_path):
    docx = pytest.importorskip("docx")

    source = tmp_path / "report.docx"
    document = docx.Document()
    document.add_paragraph("Quarterly Report", style="Title")
    document.add_paragraph("Findings", style="Heading 1")
    document.add_paragraph("Detail", style="Heading 2")

    mixed = document.add_paragraph()
    mixed.add_run("plain and ")
    mixed.add_run("bold").bold = True
    mixed.add_run(" and ")
    mixed.add_run("italic").italic = True

    document.add_paragraph("first bullet", style="List Bullet")
    document.add_paragraph("second bullet", style="List Bullet")
    document.add_paragraph("first step", style="List Number")
    document.add_paragraph("a quotation", style="Quote")
    document.save(source)

    assert load(source) == (
        "# Quarterly Report\n\n"
        "# Findings\n\n"
        "## Detail\n\n"
        "plain and **bold** and *italic*\n\n"
        "- first bullet\n"
        "- second bullet\n\n"
        "1. first step\n\n"
        "> a quotation"
    )


def test_markdown_becomes_docx_styles(tmp_path):
    docx = pytest.importorskip("docx")

    target = tmp_path / "out.docx"
    save(
        target,
        "# Title\n\n## Section\n\nbody **bold** text\n\n- one\n- two\n\n1. step\n\n> quoted",
    )

    paragraphs = docx.Document(target).paragraphs
    assert [p.style.name for p in paragraphs] == [
        "Heading 1",
        "Heading 2",
        "Normal",
        "List Bullet",
        "List Bullet",
        "List Number",
        "Quote",
    ]
    assert [p.text for p in paragraphs] == [
        "Title",
        "Section",
        "body bold text",
        "one",
        "two",
        "step",
        "quoted",
    ]
    assert [run.text for run in paragraphs[2].runs if run.bold] == ["bold"]


def test_docx_round_trip_preserves_structure(tmp_path):
    pytest.importorskip("docx")

    markdown = (
        "# Title\n\n## Section\n\nbody **bold** text\n\n- one\n- two\n\n1. step\n\n> quoted"
    )
    target = tmp_path / "round.docx"
    save(target, markdown)

    assert load(target) == markdown


def test_wrapped_markdown_lines_join_into_one_paragraph(tmp_path):
    docx = pytest.importorskip("docx")

    target = tmp_path / "wrapped.docx"
    save(target, "first line\nsecond line\n\nnext block")

    assert [p.text for p in docx.Document(target).paragraphs] == [
        "first line second line",
        "next block",
    ]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("notes.txt", Kind.PLAIN),
        ("notes.md", Kind.MARKDOWN),
        ("notes.markdown", Kind.MARKDOWN),
        ("notes.docx", Kind.MARKDOWN),
    ],
)
def test_kind_of(tmp_path, name, expected):
    assert kind_of(tmp_path / name) is expected


def test_kind_of_nothing_is_plain():
    assert kind_of(None) is Kind.PLAIN


def test_supported_filter_lists_every_readable_extension():
    for extension in ("*.txt", "*.md", "*.docx"):
        assert extension in supported_filter()
    assert "*.doc " not in supported_filter()
    assert "*.doc)" not in supported_filter()


def test_docx_zip_bomb_is_rejected(tmp_path):
    import zipfile

    bomb = tmp_path / "bomb.docx"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"A" * 200_000_000)

    with pytest.raises(UnsupportedFormat) as error:
        load(bomb)
    assert "too large" in str(error.value).lower()


def test_corrupt_docx_gives_a_clean_error(tmp_path):
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"this is not a zip archive")

    with pytest.raises(UnsupportedFormat):
        load(broken)
