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
        self.sans = _first_existing(SANS_CANDIDATES)
        self.bold = _first_existing(SANS_BOLD_CANDIDATES) or self.sans
        self.mono = _first_existing(MONO_CANDIDATES)
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def get(self, family: str, size: int) -> ImageFont.FreeTypeFont:
        key = (family, size)
        if key not in self._cache:
            path = {"sans": self.sans, "bold": self.bold, "mono": self.mono}[family]
            self._cache[key] = (
                ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size)
            )
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
    draw.rounded_rectangle([96, 180, width - 96, height - 180], radius=36, fill=PANEL)

    title_font = FONTS.get("bold", 84)
    lines = _wrap(draw, section.heading, title_font, width - 320)
    y = 300
    for line in lines[:3]:
        draw.text(((width - draw.textlength(line, font=title_font)) / 2, y), line, font=title_font, fill=FG)
        y += 104

    sub_font = FONTS.get("sans", 40)
    draw.text(
        ((width - draw.textlength(section.subheading, font=sub_font)) / 2, y + 20),
        section.subheading,
        font=sub_font,
        fill=ACCENT,
    )

    if section.bullets:
        chip_font = FONTS.get("bold", 30)
        widths = [draw.textlength(b, font=chip_font) + 52 for b in section.bullets]
        total = sum(widths) + 20 * (len(widths) - 1)
        x = (width - total) / 2
        cy = y + 130
        for bullet, w in zip(section.bullets, widths):
            draw.rounded_rectangle([x, cy, x + w, cy + 58], radius=29, fill=PANEL_HI)
            draw.text((x + 26, cy + 13), bullet, font=chip_font, fill=MUTED)
            x += w + 20
    return image


def _render_bullets(section: Section, width: int, height: int) -> Image.Image:
    image, draw = _new_canvas(width, height)
    top = _draw_header(draw, section, width)
    available = height - top - 90
    max_width = width - 260
    bullets = [str(b).lstrip("•-* ").strip() for b in section.bullets]

    for size in (42, 38, 34, 30, 26, 22):
        font = FONTS.get("sans", size)
        wrapped = [_wrap(draw, b, font, max_width) for b in bullets]
        line_h = int(size * 1.45)
        total = sum(len(w) * line_h + int(size * 0.85) for w in wrapped)
        if total <= available:
            break

    y = top
    for wrapped_bullet in wrapped:
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
    size = 30
    while size > 11 and (
        len(lines) * int(size * 1.4) > available or longest * char_w * size > usable_width
    ):
        size -= 1
    font = FONTS.get("mono", size)
    line_h = int(size * 1.4)
    gutter_font = FONTS.get("mono", max(11, size - 4))

    panel_bottom = min(height - 50, top + len(lines) * line_h + 40)
    draw.rounded_rectangle([96, top, width - 96, panel_bottom], radius=20, fill=PANEL)

    tokens = _tokenize("\n".join(lines), section.language)
    highlight = set(section.highlight)
    y = top + 20
    for number, token_line in enumerate(tokens[: len(lines)], start=1):
        if number in highlight:
            draw.rectangle([112, y - 4, width - 112, y + line_h - 4], fill=PANEL_HI)
            draw.rectangle([112, y - 4, 118, y + line_h - 4], fill=ACCENT_2)
        draw.text((140, y + 2), f"{number:>3}", font=gutter_font, fill=(80, 96, 124))
        x = text_left
        dim = number not in highlight and highlight
        for text, color in token_line:
            if dim:
                color = tuple(int(c * 0.45 + 30) for c in color)
            draw.text((x, y), text, font=font, fill=color)
            x += draw.textlength(text, font=font)
        y += line_h
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
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for section in script.sections:
        path = out_dir / f"{section.id}.png"
        render_section(section, width, height).save(path)
        paths.append(path)
    return paths
