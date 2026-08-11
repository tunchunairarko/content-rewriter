import pytest

from content_rewriter.cleaning import clean


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("plain ascii text", "plain ascii text"),
        ("zero​width‌space﻿", "zerowidthspace"),
        ("soft­hyphen", "softhyphen"),
        ("non breaking space", "non breaking space"),
        ("em—dash", "em, dash"),
        ("spaced — dash", "spaced, dash"),
        ("double--dash", "double, dash"),
        ("triple---dash", "triple, dash"),
        ("en–dash", "en, dash"),
        ("horizontal―bar", "horizontal, bar"),
        ("hyphen-word stays", "hyphen-word stays"),
        ("smile 😀 here", "smile here"),
        ("flags 🇬🇧 gone", "flags gone"),
        ("hearts ❤️ removed", "hearts removed"),
        ("curly ‘quotes’ and “doubles”", "curly 'quotes' and \"doubles\""),
        ("ellipsis… collapsed", "ellipsis... collapsed"),
        ("café naïve", "cafe naive"),
        ("cyrillic Привет dropped", "cyrillic dropped"),
        ("bullet • point", "bullet point"),
        ("", ""),
    ],
)
def test_clean(raw, expected):
    assert clean(raw) == expected


def test_output_is_pure_ascii():
    assert clean("mixed 😀 — café ‘x’ 中文").isascii()


def test_line_structure_survives():
    assert clean("first line\n\nsecond — line\n") == "first line\n\nsecond, line\n"


def test_collapses_spaces_left_by_removals():
    assert clean("word 😀 word") == "word word"
    assert clean("trailing 😀") == "trailing"


def test_no_double_comma_when_dash_follows_comma():
    assert clean("wait, — actually") == "wait, actually"


def test_keeps_markdown_indentation():
    assert clean("- item\n  - nested\n    - deeper") == "- item\n  - nested\n    - deeper"


def test_keeps_indented_code_blocks():
    assert clean("text\n\n    indented code\n") == "text\n\n    indented code\n"


def test_thematic_breaks_are_not_dashes():
    assert clean("intro\n\n---\n\nnext") == "intro\n\n---\n\nnext"
    assert clean("intro\n\n***\n\nnext") == "intro\n\n***\n\nnext"


def test_setext_underline_survives():
    assert clean("Heading\n===\n") == "Heading\n===\n"


def test_dashes_inside_a_line_still_become_commas():
    assert clean("- item -- with a break") == "- item, with a break"


def test_idempotent():
    once = clean("café — 😀 ‘quoted’")
    assert clean(once) == once
