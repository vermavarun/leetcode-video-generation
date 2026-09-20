"""Render each script section to a 1920x1080 slide image with Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

from .config import MODELS_DIR
from .script_gen import Section, VideoScript

BG = (13, 20, 36)
PANEL = (20, 30, 52)
PANEL_HI = (30, 45, 78)
FG = (232, 240, 255)
MUTED = (139, 158, 189)
ACCENT = (56, 189, 248)
ACCENT_2 = (250, 204, 21)

# Smallest legible code size at 1080p; below this we scroll instead of shrink.
MIN_CODE_SIZE = 17
MAX_CODE_SIZE = 30

# Difficulty chips get their own (background, text) colours on the title slide.
DIFFICULTY_COLORS = {
    "easy": ((22, 78, 62), (110, 231, 183)),
    "medium": ((80, 62, 16), (252, 211, 77)),
    "hard": ((88, 32, 40), (252, 165, 165)),
}

SANS_CANDIDATES = [
    MODELS_DIR / "fonts" / "Inter-Regular.ttf",
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]
SANS_BOLD_CANDIDATES = [
    MODELS_DIR / "fonts" / "Inter-Bold.ttf",
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
MONO_CANDIDATES = [
    MODELS_DIR / "fonts" / "JetBrainsMono-Regular.ttf",
    Path("/System/Library/Fonts/Monaco.ttf"),
    Path("/System/Library/Fonts/Supplemental/Courier New.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
]

# Devanagari needs a script-specific face; these also cover Latin text.
DEVANAGARI_CANDIDATES = [
    MODELS_DIR / "fonts" / "NotoSansDevanagari.ttf",
    Path("/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc"),
    Path("/System/Library/Fonts/Supplemental/DevanagariMT.ttc"),
    Path("/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf"),
]

# Language -> (regular candidates, bold candidates)
LANGUAGE_FONTS = {
    "hi": (DEVANAGARI_CANDIDATES, DEVANAGARI_CANDIDATES),
}

CODE_COLORS = {
    Token.Keyword: (198, 149, 255),
    Token.Keyword.Type: (94, 234, 212),
    Token.Name.Class: (250, 204, 21),
    Token.Name.Function: (125, 211, 252),
    Token.Name.Builtin: (125, 211, 252),
    Token.Literal.String: (167, 243, 208),
    Token.Literal.Number: (253, 186, 116),
    Token.Comment: (110, 130, 160),
    Token.Operator: (244, 114, 182),
    Token.Punctuation: (170, 185, 210),
}


def _first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


class Fonts:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
        self.set_language("en")

    def set_language(self, language: str) -> None:
        sans_candidates, bold_candidates = LANGUAGE_FONTS.get(
            language, (SANS_CANDIDATES, SANS_BOLD_CANDIDATES)
        )
        self.sans = _first_existing(sans_candidates) or _first_existing(SANS_CANDIDATES)
        self.bold = _first_existing(bold_candidates) or self.sans
        self.mono = _first_existing(MONO_CANDIDATES)
        self._cache.clear()

    def get(self, family: str, size: int) -> ImageFont.FreeTypeFont:
        key = (family, size)
        if key not in self._cache:
            path = {"sans": self.sans, "bold": self.bold, "mono": self.mono}[family]
            if path is None:
                font = ImageFont.load_default(size)
            else:
                # TrueType collections keep Bold at face index 1.
                index = 1 if family == "bold" and path.suffix.lower() == ".ttc" else 0
                font = ImageFont.truetype(str(path), size, index=index)
            self._cache[key] = font
        return self._cache[key]


FONTS = Fonts()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = str(text).split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _code_color(token_type) -> tuple[int, int, int]:
    while token_type is not None:
        if token_type in CODE_COLORS:
            return CODE_COLORS[token_type]
        token_type = token_type.parent
    return FG


def _tokenize(code: str, language: str) -> list[list[tuple[str, tuple[int, int, int]]]]:
    try:
        lexer = get_lexer_by_name(language)
    except ClassNotFound:
        return [[(line, FG)] for line in code.splitlines()]

    lines: list[list[tuple[str, tuple[int, int, int]]]] = [[]]
    for token_type, value in lex(code, lexer):
        color = _code_color(token_type)
        parts = value.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append([])
            if part:
                lines[-1].append((part, color))
    return lines


def _wrap_tokens(
    token_line: list[tuple[str, tuple[int, int, int]]], max_chars: int
) -> list[list[tuple[str, tuple[int, int, int]]]]:
    """Soft-wrap one syntax-highlighted source line into visual rows."""
    if sum(len(text) for text, _ in token_line) <= max_chars:
        return [token_line or [("", FG)]]

    rows: list[list[tuple[str, tuple[int, int, int]]]] = [[]]
    used = 0
    for text, color in token_line:
        pos = 0
        while pos < len(text):
            if used >= max_chars:
                rows.append([("  ", FG)])  # continuation indent
                used = 2
            piece = text[pos : pos + (max_chars - used)]
            rows[-1].append((piece, color))
            pos += len(piece)
            used += len(piece)
    return rows


def _visible_window(rows_per_line: list[int], highlight: set[int], budget: int) -> tuple[int, int]:
    """Pick the 0-based line range to show, centred on the highlighted lines."""
    total = len(rows_per_line)
    if sum(rows_per_line) <= budget:
        return 0, total - 1

    marked = sorted(n - 1 for n in highlight if 1 <= n <= total)
    first = marked[0] if marked else 0
    last = marked[-1] if marked else 0
    used = sum(rows_per_line[first : last + 1])

    # Grow outwards, preferring context above so the signature stays visible.
    while used < budget and (first > 0 or last < total - 1):
        if first > 0 and used + rows_per_line[first - 1] <= budget:
            first -= 1
            used += rows_per_line[first]
        elif last < total - 1 and used + rows_per_line[last + 1] <= budget:
            last += 1
            used += rows_per_line[last]
        else:
            break

    # A highlight taller than the budget still has to be clipped somewhere.
    while used > budget and last > first:
        used -= rows_per_line[last]
        last -= 1
    return first, last


# --------------------------------------------------------------------------
# Chrome
# --------------------------------------------------------------------------


def _new_canvas(width: int, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width, 8], fill=ACCENT)
    return image, draw


def _draw_header(draw, section: Section, width: int) -> int:
    x = 96
    y = 78
    if section.footer:
        chip_font = FONTS.get("bold", 26)
        text_w = draw.textlength(section.footer.upper(), font=chip_font)
        draw.rounded_rectangle(
            [width - 96 - text_w - 44, y + 4, width - 96, y + 52], radius=24, fill=PANEL_HI
        )
        draw.text((width - 96 - text_w - 22, y + 14), section.footer.upper(), font=chip_font, fill=ACCENT)

    heading_font = FONTS.get("bold", 62)
    for line in _wrap(draw, section.heading, heading_font, width - 480)[:2]:
        draw.text((x, y), line, font=heading_font, fill=FG)
        y += 74
    if section.subheading:
        sub_font = FONTS.get("sans", 34)
        draw.text((x, y + 4), section.subheading, font=sub_font, fill=MUTED)
        y += 52
    draw.line([(x, y + 22), (x + 140, y + 22)], fill=ACCENT, width=6)
    return y + 70


# --------------------------------------------------------------------------
# Slide kinds
# --------------------------------------------------------------------------


def _render_title(section: Section, width: int, height: int) -> Image.Image:
    image, draw = _new_canvas(width, height)
    pad = 96
    inner = width - 2 * pad - 160

    for title_size in (88, 78, 68, 58, 50, 44, 38):
        title_font = FONTS.get("bold", title_size)
        title_lines = _wrap(draw, section.heading, title_font, inner)
        if len(title_lines) <= 3:
            break

    sub_lines: list[str] = []
    sub_size = 36
    if section.subheading:
        for sub_size in (40, 36, 32, 28, 24):
            sub_font = FONTS.get("sans", sub_size)
            sub_lines = _wrap(draw, section.subheading, sub_font, inner)
            if len(sub_lines) <= 3:
                break

    chip_font = FONTS.get("bold", 28)
    chip_rows: list[list[tuple[str, float]]] = []
    row: list[tuple[str, float]] = []
    row_width = 0.0
    for bullet in section.bullets:
        chip_width = draw.textlength(bullet, font=chip_font) + 52
        if row and row_width + chip_width + 20 > inner:
            chip_rows.append(row)
            row, row_width = [], 0.0
        row.append((bullet, chip_width))
        row_width += chip_width + 20
    if row:
        chip_rows.append(row)

    title_h = len(title_lines) * int(title_size * 1.18)
    sub_h = len(sub_lines) * int(sub_size * 1.4)
    chips_h = len(chip_rows) * 74
    total = title_h + (34 + sub_h if sub_lines else 0) + (44 + chips_h if chip_rows else 0)

    # Size the card to the content instead of leaving a large empty band.
    vpad = 120
    panel_top = max(120, (height - total - 2 * vpad) // 2)
    panel_bottom = height - panel_top
    draw.rounded_rectangle([pad, panel_top, width - pad, panel_bottom], radius=36, fill=PANEL)

    y = panel_top + (panel_bottom - panel_top - total) / 2
    for line in title_lines[:3]:
        draw.text(((width - draw.textlength(line, font=title_font)) / 2, y), line, font=title_font, fill=FG)
        y += int(title_size * 1.18)

    if sub_lines:
        y += 34
        for line in sub_lines:
            draw.text(((width - draw.textlength(line, font=sub_font)) / 2, y), line, font=sub_font, fill=ACCENT)
            y += int(sub_size * 1.4)

    if chip_rows:
        y += 44
        for chip_row in chip_rows:
            total_w = sum(w for _, w in chip_row) + 20 * (len(chip_row) - 1)
            x = (width - total_w) / 2
            for text, chip_width in chip_row:
                fill, text_color = DIFFICULTY_COLORS.get(text.lower(), (PANEL_HI, MUTED))
                draw.rounded_rectangle([x, y, x + chip_width, y + 58], radius=29, fill=fill)
                draw.text((x + 26, y + 13), text, font=chip_font, fill=text_color)
                x += chip_width + 20
            y += 74
    return image


def _render_bullets(section: Section, width: int, height: int) -> Image.Image:
    image, draw = _new_canvas(width, height)
    top = _draw_header(draw, section, width)
    available = height - top - 90
    max_width = width - 260
    bullets = [str(b).lstrip("•-* ").strip() for b in section.bullets]

    for size in (42, 38, 34, 30, 26, 23, 20, 18):
        font = FONTS.get("sans", size)
        wrapped = [_wrap(draw, b, font, max_width) for b in bullets]
        line_h = int(size * 1.45)
        total = sum(len(w) * line_h + int(size * 0.85) for w in wrapped)
        if total <= available:
            break

    y = top
    for wrapped_bullet in wrapped:
        if y + len(wrapped_bullet) * line_h > height - 60:
            break
        draw.ellipse([96, y + line_h / 2 - 7, 110, y + line_h / 2 + 7], fill=ACCENT)
        for line in wrapped_bullet:
            draw.text((140, y), line, font=font, fill=FG)
            y += line_h
        y += int(size * 0.85)
    return image


def _render_kv(section: Section, width: int, height: int) -> Image.Image:
    image, draw = _new_canvas(width, height)
    top = _draw_header(draw, section, width)
    label_font = FONTS.get("bold", 32)
    value_font = FONTS.get("mono", 36)
    max_width = width - 460

    y = top
    for label, value in section.rows:
        lines = _wrap(draw, value, value_font, max_width)
        box_h = max(96, len(lines) * 50 + 44)
        draw.rounded_rectangle([96, y, width - 96, y + box_h], radius=20, fill=PANEL)
        draw.rounded_rectangle([96, y, 104, y + box_h], fill=ACCENT)
        draw.text((136, y + 26), label.upper(), font=label_font, fill=ACCENT)
        vy = y + 22
        for line in lines:
            draw.text((340, vy), line, font=value_font, fill=FG)
            vy += 50
        y += box_h + 26
        if y > height - 120:
            break
    return image


def _render_code(section: Section, width: int, height: int) -> Image.Image:
    image, draw = _new_canvas(width, height)
    top = _draw_header(draw, section, width)

    lines = [line.replace("\t", "    ").rstrip() for line in section.code.splitlines()]
    available = height - top - 70
    text_left = 210
    usable_width = width - 112 - text_left - 40

    # Monospace advance scales linearly, so solve for the largest fitting size.
    ref = 30
    char_w = draw.textlength("M" * 20, font=FONTS.get("mono", ref)) / 20 / ref
    longest = max((len(line) for line in lines), default=1)
    size = int(usable_width / (char_w * max(longest, 1)))
    size = max(MIN_CODE_SIZE, min(MAX_CODE_SIZE, size))
    line_h = int(size * 1.4)
    max_chars = max(20, int(usable_width / (char_w * size)))
    row_budget = max(4, available // line_h)

    tokens = _tokenize("\n".join(lines), section.language)[: len(lines)]
    highlight = set(section.highlight)
    rows_per_line = [len(_wrap_tokens(t, max_chars)) for t in tokens]

    first, last = _visible_window(rows_per_line, highlight, row_budget)
    hidden_above, hidden_below = first, len(lines) - 1 - last

    shown = sum(rows_per_line[first : last + 1])
    panel_bottom = min(height - 50, top + shown * line_h + 40)
    draw.rounded_rectangle([96, top, width - 96, panel_bottom], radius=20, fill=PANEL)

    gutter_font = FONTS.get("mono", max(11, size - 4))
    font = FONTS.get("mono", size)
    y = top + 20
    for index in range(first, last + 1):
        number = index + 1
        for row_i, token_row in enumerate(_wrap_tokens(tokens[index], max_chars)):
            if number in highlight:
                draw.rectangle([112, y - 4, width - 112, y + line_h - 4], fill=PANEL_HI)
                draw.rectangle([112, y - 4, 118, y + line_h - 4], fill=ACCENT_2)
            if row_i == 0:
                draw.text((140, y + 2), f"{number:>3}", font=gutter_font, fill=(80, 96, 124))
            x = text_left
            dim = number not in highlight and bool(highlight)
            for text, color in token_row:
                if dim:
                    color = tuple(int(c * 0.45 + 30) for c in color)
                draw.text((x, y), text, font=font, fill=color)
                x += draw.textlength(text, font=font)
            y += line_h

    hint_font = FONTS.get("sans", 24)
    if hidden_above:
        draw.text((140, top - 32), f"\u2191 {hidden_above} more lines above", font=hint_font, fill=MUTED)
    if hidden_below:
        draw.text(
            (140, panel_bottom + 6), f"\u2193 {hidden_below} more lines below", font=hint_font, fill=MUTED
        )
    return image


def _render_outro(section: Section, width: int, height: int) -> Image.Image:
    image = _render_bullets(section, width, height)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, height - 10, width, height], fill=ACCENT)
    return image


RENDERERS = {
    "title": _render_title,
    "bullets": _render_bullets,
    "kv": _render_kv,
    "code": _render_code,
    "outro": _render_outro,
}


def render_section(section: Section, width: int, height: int) -> Image.Image:
    return RENDERERS.get(section.kind, _render_bullets)(section, width, height)


def render_all(script: VideoScript, out_dir: Path, width: int = 1920, height: int = 1080) -> list[Path]:
    FONTS.set_language(script.language)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for section in script.sections:
        path = out_dir / f"{section.id}.png"
        render_section(section, width, height).save(path)
        paths.append(path)

    # Slide counts change when sections repaginate; drop frames from older runs.
    for stale in set(out_dir.glob("*.png")) - set(paths):
        stale.unlink()
    return paths
