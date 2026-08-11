import re
import unicodedata

INVISIBLE = dict.fromkeys(
    [
        0x00AD,
        0x061C,
        0x180E,
        0x200B,
        0x200C,
        0x200D,
        0x200E,
        0x200F,
        0x2028,
        0x2029,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2060,
        0x2061,
        0x2062,
        0x2063,
        0x2064,
        0x2066,
        0x2067,
        0x2068,
        0x2069,
        0x206A,
        0x206B,
        0x206C,
        0x206D,
        0x206E,
        0x206F,
        0xFEFF,
    ]
)

PUNCTUATION = {
    0x00A0: " ",
    0x1680: " ",
    0x2000: " ",
    0x2001: " ",
    0x2002: " ",
    0x2003: " ",
    0x2004: " ",
    0x2005: " ",
    0x2006: " ",
    0x2007: " ",
    0x2008: " ",
    0x2009: " ",
    0x200A: " ",
    0x202F: " ",
    0x205F: " ",
    0x3000: " ",
    0x2018: "'",
    0x2019: "'",
    0x201A: "'",
    0x201B: "'",
    0x2032: "'",
    0x2035: "'",
    0x201C: '"',
    0x201D: '"',
    0x201E: '"',
    0x201F: '"',
    0x2033: '"',
    0x2036: '"',
    0x00AB: '"',
    0x00BB: '"',
    0x2026: "...",
    0x2022: "",
    0x00B7: "",
    0x2044: "/",
    0x00D7: "x",
}

DASHES = "‐‑‒–—―−﹘﹣－"
DASH_RUN = re.compile(rf"[ \t]*(?:[{DASHES}]+|-{{2,}})[ \t]*")
THEMATIC_BREAK = re.compile(rf"^[ \t]*([-*_=~{DASHES}])(?:[ \t]*\1){{2,}}[ \t]*$")
EMOJI = re.compile(
    "["
    "\U0001f000-\U0001ffff"
    "\U0001ae00-\U0001b0ff"
    "\U00002190-\U000021ff"
    "\U00002300-\U000023ff"
    "\U000024c2-\U0001f251"
    "\U00002600-\U000027bf"
    "\U00002b00-\U00002bff"
    "\U0000fe00-\U0000fe0f"
    "\U0001f900-\U0001f9ff"
    "\U000e0020-\U000e007f"
    "]+",
    flags=re.UNICODE,
)
HORIZONTAL_SPACE = re.compile(r"(?<=\S)[ \t]{2,}")
SPACE_BEFORE_PUNCTUATION = re.compile(r"[ \t]+([,.;:!?)\]}])")
STRAY_COMMA = re.compile(r",(\s*,)+")
COMMA_AFTER_BREAK = re.compile(r"(^|\n)[ \t]*,[ \t]*", flags=re.MULTILINE)
TRAILING_SPACE = re.compile(r"[ \t]+(\n|$)")


def clean(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.translate(INVISIBLE)
    text = text.translate(PUNCTUATION)
    text = "\n".join(line if THEMATIC_BREAK.match(line) else DASH_RUN.sub(", ", line)
                     for line in text.split("\n"))
    text = EMOJI.sub("", text)
    text = _to_ascii(text)
    return _tidy(text)


def _to_ascii(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.encode("ascii", "ignore").decode("ascii")


def _tidy(text: str) -> str:
    text = HORIZONTAL_SPACE.sub(" ", text)
    text = SPACE_BEFORE_PUNCTUATION.sub(r"\1", text)
    text = STRAY_COMMA.sub(",", text)
    text = COMMA_AFTER_BREAK.sub(r"\1", text)
    text = TRAILING_SPACE.sub(r"\1", text)
    return text.strip() if not text.endswith("\n") else text.lstrip()
