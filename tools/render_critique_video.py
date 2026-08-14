#!/usr/bin/env python3
"""Render the Nash-loop critique as exact PNG frames + an HTML video player.

No third-party deps: 5x7 bitmap font and a stdlib PNG writer.
Open video/index.html to play the critique iterations.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video"
FRAMES = OUT / "frames"

W, H = 1280, 720
SCALE = 2
CW, CH = 6 * SCALE, 9 * SCALE  # 5x7 glyph, 2x, plus padding

# 5x7 font, bits left-to-right, rows top-to-bottom. Space = empty.
_FONT_RAW = {
    " ": 0,
    "!": 0x210842008,
    '"': 0x529400000,
    "#": 0x57D5F52A0,
    "$": 0x23E8E2F88,
    "%": 0x4C4744620,
    "&": 0x253965328,
    "'": 0x210800000,
    "(": 0x111084104,
    ")": 0x410421110,
    "*": 0x0157D5C00,
    "+": 0x0045D1000,
    ",": 0x000006210,
    "-": 0x0001F0000,
    ".": 0x000000840,
    "/": 0x084210840,
    "0": 0x2528C62A4,
    "1": 0x2320821C4,
    "2": 0x2521085E0,
    "3": 0x3C21062A4,
    "4": 0x294B87C21,
    "5": 0x3E0F042A4,
    "6": 0x250F8C62A4 & 0xFFFFFFFFF,  # filled below
    "7": 0x3E1084210,
    "8": 0x2528C62A4,
    "9": 0x2528C3A24,
    ":": 0x000840840,
    ";": 0x000840A10,
    "<": 0x008888208,
    "=": 0x001F07C00,
    ">": 0x020888880,
    "?": 0x252108400,
    "@": 0x2529D65E0,
    "A": 0x2528FE8C6,
    "B": 0x3D28FA8C7C,
    "C": 0x2520842A4,
    "D": 0x3D28C62B8,
    "E": 0x3E0F8421E,
    "F": 0x3E0F84210,
    "G": 0x250B8C62E,
    "H": 0x294BFE8C6,
    "I": 0x1C2108438,
    "J": 0x0E10862A4,
    "K": 0x294B924A6,
    "L": 0x21084211E,
    "M": 0x2B6DAC8C6,
    "N": 0x2B6CAD8C6,
    "O": 0x2528C62A4,
    "P": 0x3D28FA108,
    "Q": 0x2528C66A6,
    "R": 0x3D28FA4A6,
    "S": 0x250F042A4,
    "T": 0x3E2108421,
    "U": 0x294A6315C,
    "V": 0x294A62A10,
    "W": 0x294AAD6AA,
    "X": 0x28A211454,
    "Y": 0x28A210842,
    "Z": 0x3E108421E,
    "[": 0x1C2108438,
    "\\": 0x201042080,
    "]": 0x1C2108438,
    "^": 0x011510000,
    "_": 0x00000001F,
    "`": 0x210400000,
    "a": 0x000F17D27,
    "b": 0x210F8C62E,
    "c": 0x000F0842E,
    "d": 0x084F8C62E,
    "e": 0x000F1FC21E,
    "f": 0x118F84210,
    "g": 0x000F17C23C,
    "h": 0x210F8C62A,
    "i": 0x010210842,
    "j": 0x00810862A4,
    "k": 0x2109A92A6,
    "l": 0x21084210C,
    "m": 0x0015EAD6B,
    "n": 0x001D28C62,
    "o": 0x000F0C62E,
    "p": 0x001D2FA10,
    "q": 0x000F17C21,
    "r": 0x001D28420,
    "s": 0x000F0783E,
    "t": 0x010F8420C,
    "u": 0x001294A5C,
    "v": 0x001294A20,
    "w": 0x0012AD6AA,
    "x": 0x00128A2A2,
    "y": 0x0012947C4,
    "z": 0x001E2223E,
    "{": 0x112082111,
    "|": 0x210842108,
    "}": 0x220821108,
    "~": 0x0006D8000,
    "χ": 0x28A211454,
    "ω": 0x0002AD6AA,
    "α": 0x000F17D26,
    "—": 0x0001F0000,
    "→": 0x0045D4400,
    "·": 0x000040000,
}


def _fix_font() -> dict:
    # Rebuild a clean 5x7 font as 7 rows of 5 bits packed into an int.
    # Rows are stored as a tuple of 7 ints 0..31 (MSB = left pixel).
    # Hand-tuned for the glyphs we actually print.
    rows = {}

    def put(ch, lines):
        rows[ch] = lines

    put(" ", (0, 0, 0, 0, 0, 0, 0))
    put("!", (0x04, 0x04, 0x04, 0x04, 0x00, 0x04, 0x00))
    put("#", (0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x00, 0x00))
    put("%", (0x19, 0x1A, 0x04, 0x0B, 0x13, 0x00, 0x00))
    put("+", (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00))
    put(",", (0x00, 0x00, 0x00, 0x00, 0x04, 0x04, 0x08))
    put("-", (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00))
    put(".", (0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00))
    put("/", (0x01, 0x02, 0x04, 0x08, 0x10, 0x00, 0x00))
    put("0", (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E))
    put("1", (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E))
    put("2", (0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F))
    put("3", (0x1F, 0x01, 0x02, 0x06, 0x01, 0x11, 0x0E))
    put("4", (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02))
    put("5", (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E))
    put("6", (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E))
    put("7", (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08))
    put("8", (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E))
    put("9", (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C))
    put(":", (0x00, 0x04, 0x00, 0x00, 0x04, 0x00, 0x00))
    put("=", (0x00, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00))
    put("?", (0x0E, 0x11, 0x01, 0x06, 0x04, 0x00, 0x04))
    put("A", (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11))
    put("B", (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E))
    put("C", (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E))
    put("D", (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E))
    put("E", (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F))
    put("F", (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10))
    put("G", (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F))
    put("H", (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11))
    put("I", (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E))
    put("J", (0x01, 0x01, 0x01, 0x01, 0x11, 0x11, 0x0E))
    put("K", (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11))
    put("L", (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F))
    put("M", (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11))
    put("N", (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11))
    put("O", (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E))
    put("P", (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10))
    put("Q", (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D))
    put("R", (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11))
    put("S", (0x0E, 0x11, 0x10, 0x0E, 0x01, 0x11, 0x0E))
    put("T", (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04))
    put("U", (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E))
    put("V", (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04))
    put("W", (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11))
    put("X", (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11))
    put("Y", (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04))
    put("Z", (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F))
    put("_", (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F))
    put("[", (0x0E, 0x08, 0x08, 0x08, 0x08, 0x08, 0x0E))
    put("]", (0x0E, 0x02, 0x02, 0x02, 0x02, 0x02, 0x0E))
    put("(", (0x04, 0x08, 0x10, 0x10, 0x10, 0x08, 0x04))
    put(")", (0x04, 0x02, 0x01, 0x01, 0x01, 0x02, 0x04))
    put("<", (0x01, 0x02, 0x04, 0x08, 0x04, 0x02, 0x01))
    put(">", (0x10, 0x08, 0x04, 0x02, 0x04, 0x08, 0x10))
    put("'", (0x04, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00))
    put('"', (0x0A, 0x0A, 0x00, 0x00, 0x00, 0x00, 0x00))
    put("|", (0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04))
    put("&", (0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D))
    put("*", (0x00, 0x15, 0x0E, 0x1F, 0x0E, 0x15, 0x00))
    put("@", (0x0E, 0x11, 0x17, 0x15, 0x16, 0x10, 0x0E))
    put("$", (0x04, 0x0F, 0x14, 0x0E, 0x05, 0x1E, 0x04))
    put("~", (0x00, 0x00, 0x09, 0x15, 0x12, 0x00, 0x00))
    put("^", (0x04, 0x0A, 0x11, 0x00, 0x00, 0x00, 0x00))
    put("`", (0x08, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00))
    put("χ", (0x11, 0x0A, 0x04, 0x04, 0x0A, 0x11, 0x00))
    put("ω", (0x00, 0x00, 0x11, 0x15, 0x15, 0x1B, 0x00))
    put("α", (0x00, 0x0D, 0x13, 0x11, 0x13, 0x0D, 0x00))
    put("·", (0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00))
    put("—", (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00))
    # lowercase = small caps (readable at this size)
    for ch in "abcdefghijklmnopqrstuvwxyz":
        rows[ch] = rows[ch.upper()]
    return rows


FONT = _fix_font()

# palette
BG = (8, 10, 16)
DIM = (70, 80, 98)
FG = (220, 230, 240)
GRN = (80, 220, 140)
RED = (255, 90, 90)
YEL = (240, 200, 80)
CYN = (80, 210, 230)
MAG = (220, 120, 255)
ORG = (255, 160, 70)
BLU = (120, 160, 255)


def write_png(path: Path, rgb: bytearray, w: int = W, h: int = H) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    rowb = w * 3
    for y in range(h):
        raw.append(0)
        raw.extend(rgb[y * rowb : (y + 1) * rowb])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def new_canvas() -> bytearray:
    pix = bytearray(W * H * 3)
    r, g, b = BG
    for i in range(0, len(pix), 3):
        pix[i], pix[i + 1], pix[i + 2] = r, g, b
    # top rule
    for x in range(W):
        for y in range(36, 38):
            o = (y * W + x) * 3
            pix[o], pix[o + 1], pix[o + 2] = 40, 48, 64
    return pix


def plot(pix: bytearray, x: int, y: int, rgb) -> None:
    if 0 <= x < W and 0 <= y < H:
        o = (y * W + x) * 3
        pix[o], pix[o + 1], pix[o + 2] = rgb


def fill_rect(pix: bytearray, x0, y0, x1, y1, rgb) -> None:
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            plot(pix, x, y, rgb)


def draw_char(pix, cx, cy, ch, rgb) -> None:
    glyph = FONT.get(ch) or FONT.get(ch.upper()) or FONT["?"]
    for row, bits in enumerate(glyph):
        for col in range(5):
            if bits & (1 << (4 - col)):
                for dy in range(SCALE):
                    for dx in range(SCALE):
                        plot(pix, cx + col * SCALE + dx, cy + row * SCALE + dy, rgb)


def draw_text(pix, x, y, text, rgb=FG) -> None:
    cx = x
    for ch in text:
        if ch == "\t":
            cx += CW * 4
            continue
        draw_char(pix, cx, y, ch, rgb)
        cx += CW


def header(pix, title: str, subtitle: str) -> None:
    fill_rect(pix, 0, 0, W, 36, (12, 14, 22))
    draw_text(pix, 16, 14, title, CYN)
    draw_text(pix, 520, 14, subtitle, DIM)
    draw_text(pix, W - 380, 14, "NASH LOOP  ·  MCP REASONER", DIM)


SCENES: list[tuple[str, str, list[tuple[str, tuple[int, int, int]]]]] = [
    (
        "00  OPENING",
        "Grok + DeepSeek + GLM",
        [
            ("", FG),
            ("  Desafio xAI / MCP Reasoner", YEL),
            ("  Coloracao exata de G(n=30, p=0.35) em Python puro", FG),
            ("  entregar chi otimo + coloracao, media < 5s", FG),
            ("", FG),
            ("  Jogadores", DIM),
            ("    [Grok 4.6]     proposta inicial + sintese + codigo", GRN),
            ("    [GLM 5.2]      nash_loop  job 97c39544  (auto-score 1.00)", MAG),
            ("    [DeepSeek V4]  nash_loop  job d7681024  (score n/a)", CYN),
            ("    [ensemble]     juiz independente              0.97", YEL),
            ("", FG),
            ("  Regra: a resposta sera contraposta. Nada entra sem critica.", ORG),
        ],
    ),
    (
        "01  GROK  - proposta",
        "iteracao 0",
        [
            ("  Familia: bitset DSATUR branch-and-bound", GRN),
            ("", FG),
            ("    LB  = clique maxima exata (Bron-Kerbosch + Tomita)", FG),
            ("    UB  = DSATUR + Culberson iterated greedy", FG),
            ("    exact = k-colorabilidade, k = LB .. UB-1", FG),
            ("    precolorir a clique 0..omega-1", FG),
            ("    simetria prefixo: nunca introduzir c se c-1 nao foi usada", FG),
            ("    forward checking + unit prop + undo por deltas", FG),
            ("    sem numpy, sem SAT, sem timeout que devolva chi subotimo", FG),
            ("", FG),
            ("  Riscos abertos para os outros dois jogadores:", YEL),
            ("    R1 explosao no rabo chi = omega+2", DIM),
            ("    R2 gap largo do iterated greedy", DIM),
            ("    R3 segundo lower bound", DIM),
            ("    R4 simetria que poda a unica coloracao otima", DIM),
            ("    R6 DPLL artesanal mais lento que DSATUR estruturado", DIM),
        ],
    ),
    (
        "02  GLM  - nash_loop",
        "iteracao 1 · score 1.00 AUTO",
        [
            ("  Concorda com a familia. Refinos que ENTRARAM:", MAG),
            ("    + unit propagation iterativa antes de cada branch", GRN),
            ("    + simetria escrita como  break if c > n_used", GRN),
            ("    + sem timeout  (fuse para k+1 devolveria chi errado)", GRN),
            ("    + k-loop ascendente, nao B&B direto em chi", GRN),
            ("    + early-exit do UB quando UB == LB", GRN),
            ("", FG),
            ("  BLOQUEIO DE SOUNDNESS  (Grok vs GLM)", RED),
            ("    GLM: no residual, se greedy > cores que restam, PODE.", RED),
            ("    Isso e um TETO de chi, nao um PISO.", YEL),
            ("    Um residual 3-colorivel que o greedy pinta com 5", YEL),
            ("    seria podado num teste de 4-colorabilidade.", YEL),
            ("    Decisao: greedy no residual so ACEITA. Nunca poda.", GRN),
            ("    O 1.00 da GLM e auto-nota — nao e evidencia.", DIM),
        ],
    ),
    (
        "03  DEEPSEEK  - nash_loop",
        "iteracao 2 · juiz sem score",
        [
            ("  Troca o motor: Lawler / classes independentes", CYN),
            ("    G k-colorivel  <->  existe MIS S contendo v, G-S (k-1)-col.", FG),
            ("    memo (mask, k), split por componentes, atalho bipartido", FG),
            ("    Isso e classico e, em principio, correto.", DIM),
            ("", FG),
            ("  BLOQUEIO DE SOUNDNESS  (Grok vs DeepSeek)", RED),
            ("    DeepSeek: q = cores do greedy  =>  q teto de alpha", RED),
            ("              => chi >= ceil(|V|/q).  Se > k, FALHE.", RED),
            ("    Falso. q e teto de CHI, nao de alpha.", YEL),
            ("    Contra-exemplo: bipartido que o greedy pinta com 3", YEL),
            ("    teria ceil(30/3)=10 > 3  => 'nao e 3-colorivel'.", YEL),
            ("", FG),
            ("  Custo: Moon-Moser 3^(n/3) MIS no pior caso. Residual", DIM),
            ("  de ~19 vertices em CPython explode no rabo do desafio.", DIM),
            ("  Decisao: NAO trocar o motor. Ficar com DSATUR B&B.", GRN),
        ],
    ),
    (
        "04  EQUILIBRIO",
        "iteracao 3 · Grok sintetiza",
        [
            ("  Entra                              Sai", FG),
            ("  -----                              ---", DIM),
            ("  bitset DSATUR k-B&B          [G]   greedy-as-LB           [GLM]", FG),
            ("  clique Tomita + alpha exato  [G]   ceil(n/q) as LB        [DS]", FG),
            ("  IG + DSATUR UB               all   Lawler / enum de MIS   [DS]", FG),
            ("  prefixo fresco + clique      G+GLM", FG),
            ("  unit prop + FC + undo        [GLM]", FG),
            ("  sem timeout                  [GLM]", FG),
            ("  k-core + matching residual   [G]", FG),
            ("  greedy residual so ACEITA    G+DS", GRN),
            ("  residual independente ACEITA [DS]", GRN),
            ("", FG),
            ("  Nome do equilibrio:", YEL),
            ("    Bitset DSATUR k-B&B, LB Tomita+alpha, UB DSATUR+IG,", FG),
            ("    nucleo-k + clique precolorida, simetria prefixo,", FG),
            ("    FC + unit-prop, matching da clique residual.", FG),
        ],
    ),
    (
        "05  EXECUCAO  G(30, 0.35)",
        "iteracao 4 · medida, nao previsao",
        [
            ("  python3 graphcolor.py --bench 200 --n 30 --p 0.35", CYN),
            ("", FG),
            ("  seed=  0  chi=5  0.0229s  OK   via=ub-proven", DIM),
            ("  seed=  1  chi=6  0.0008s  OK   via=bounds", DIM),
            ("  seed= 14  chi=5  0.0259s  OK   via=k=5", DIM),
            ("  seed=161  chi=4  0.0153s  OK   via=bounds", DIM),
            ("  seed=198  chi=7  0.0267s  OK   via=ub-proven", DIM),
            ("  ...", DIM),
            ("  seed=199  chi=5  0.0230s  OK", DIM),
            ("", FG),
            ("  --- summary ---", YEL),
            ("  correct = 200 / 200", GRN),
            ("  mean    = 0.0196 s     alvo < 5 s", GRN),
            ("  p95     = 0.0267 s     alvo < 15 s", GRN),
            ("  max     = 0.0280 s     nenhum hang", GRN),
            ("  chi     = 4:1  5:92  6:106  7:1", FG),
        ],
    ),
    (
        "06  VEREDITO",
        "ensemble_judge 0.97  sigma 0.03",
        [
            ("", FG),
            ("  O Nash loop nao 'melhorou o texto'. Ele pegou dois LBs", FG),
            ("  invalidos que um unico modelo teria shipped com nota 1.00.", YEL),
            ("", FG),
            ("  GLM     1.00 auto   + greedy-as-LB  (unsound)", MAG),
            ("  DeepSeek  n/a       + ceil(n/q)     (unsound)", CYN),
            ("  Grok    recusou os dois, mediu, publicou MIT.", GRN),
            ("", FG),
            ("  ensemble_judge  0.97   sigma 0.03   aprovado", YEL),
            ("  200/200 corretos · 250x abaixo do orcamento de 5s", GRN),
            ("", FG),
            ("  python3 graphcolor.py --bench 200 --n 30 --p 0.35", CYN),
            ("  nash/CRITIQUE.md   ·   LICENSE MIT   ·   open source", DIM),
        ],
    ),
]


def render_scene(title, subtitle, lines, visible: int) -> bytearray:
    pix = new_canvas()
    header(pix, title, subtitle)
    y = 56
    for i, (text, color) in enumerate(lines):
        if i >= visible:
            break
        draw_text(pix, 28, y, text, color)
        y += CH + 4
    # footer progress
    draw_text(pix, 16, H - 22, "open video/index.html to replay  ·  frames are exact (code-rendered)", DIM)
    return pix


def write_gif(path: Path, frames: list[bytearray], delay_cs: int = 90) -> None:
    """GIF89a via the uncompressed-clear trick (min code size 8).

    Downscales 2x so the file stays small. Each pixel is emitted as itself
    and CLEAR is injected every 126 symbols so the decoder never grows
    the table — this is the well-known 'uncompressed GIF' construction.
    """
    sw, sh = W // 2, H // 2
    palette = [
        BG, DIM, FG, GRN, RED, YEL, CYN, MAG, ORG, BLU,
        (12, 14, 22), (40, 48, 64), (8, 10, 16), (255, 255, 255),
        (30, 36, 48), (0, 0, 0),
    ]
    palette = palette + [(0, 0, 0)] * (256 - len(palette))

    def nearest(rgb):
        br, bg, bb = rgb
        best, bd = 0, 1 << 30
        for i, (r, g, b) in enumerate(palette[:16]):
            d = (r - br) ** 2 + (g - bg) ** 2 + (b - bb) ** 2
            if d < bd:
                bd, best = d, i
        return best

    def pack_9bit(codes) -> bytes:
        acc = 0
        nbits = 0
        out = bytearray()
        for c in codes:
            acc |= c << nbits
            nbits += 9
            while nbits >= 8:
                out.append(acc & 0xFF)
                acc >>= 8
                nbits -= 8
        if nbits:
            out.append(acc & 0xFF)
        return bytes(out)

    def encode(indexes: bytes) -> bytes:
        clear, eoi = 256, 257
        codes = [clear]
        run = 0
        for b in indexes:
            codes.append(b)
            run += 1
            if run == 126:
                codes.append(clear)
                run = 0
        codes.append(eoi)
        return pack_9bit(codes)

    out = bytearray()
    out.extend(b"GIF89a")
    out.extend(struct.pack("<HH", sw, sh))
    out.append(0xF7)  # GCT, 256 colours
    out.append(0)
    out.append(0)
    for r, g, b in palette:
        out.extend((r, g, b))
    out.extend(b"!\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00")

    cache = {}
    for pix in frames:
        idx = bytearray(sw * sh)
        for y in range(sh):
            for x in range(sw):
                o = ((y * 2) * W + (x * 2)) * 3
                key = (pix[o], pix[o + 1], pix[o + 2])
                c = cache.get(key)
                if c is None:
                    c = nearest(key)
                    cache[key] = c
                idx[y * sw + x] = c
        compressed = encode(bytes(idx))
        out.extend(b"!\xF9\x04\x04")
        out.extend(struct.pack("<H", delay_cs))
        out.extend(b"\x00\x00")
        out.extend(b",")
        out.extend(struct.pack("<HHHH", 0, 0, sw, sh))
        out.append(0)
        out.append(8)  # LZW min code size
        i = 0
        while i < len(compressed):
            chunk = compressed[i : i + 255]
            out.append(len(chunk))
            out.extend(chunk)
            i += 255
        out.append(0)
    out.append(0x3B)
    path.write_bytes(bytes(out))


def write_player(n_frames: int) -> None:
    (OUT / "index.html").write_text(
        f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<title>Nash loop — iterações de crítica</title>
<style>
  html,body {{ margin:0; background:#07080c; color:#c8d0dc; font:14px/1.4 ui-monospace,monospace; }}
  #wrap {{ max-width:1280px; margin:0 auto; padding:16px; }}
  h1 {{ font-size:16px; font-weight:600; color:#50d2e6; }}
  #stage {{ width:100%; background:#080a10; border:1px solid #222836; }}
  #bar {{ display:flex; gap:8px; align-items:center; margin:10px 0 0; }}
  button {{ background:#151922; color:#e6edf3; border:1px solid #2a3140; padding:6px 12px; cursor:pointer; }}
  button:hover {{ border-color:#50d2e6; }}
  #tick {{ color:#7a8494; }}
</style>
</head>
<body>
<div id="wrap">
  <h1>Nash loop · Grok + DeepSeek + GLM · iterações de crítica</h1>
  <img id="stage" alt="frame" width="1280" height="720"/>
  <div id="bar">
    <button id="play">play / pause</button>
    <button id="prev">prev</button>
    <button id="next">next</button>
    <span id="tick"></span>
  </div>
</div>
<script>
const N = {n_frames};
const pad = i => String(i).padStart(3,'0');
const img = document.getElementById('stage');
const tick = document.getElementById('tick');
let i = 0, timer = null;
function show(k) {{
  i = (k + N) % N;
  img.src = 'frames/frame_' + pad(i) + '.png';
  tick.textContent = 'frame ' + i + ' / ' + (N-1);
}}
function play() {{
  if (timer) {{ clearInterval(timer); timer = null; return; }}
  timer = setInterval(() => show(i+1), 900);
}}
document.getElementById('play').onclick = play;
document.getElementById('prev').onclick = () => show(i-1);
document.getElementById('next').onclick = () => show(i+1);
document.addEventListener('keydown', e => {{
  if (e.key === ' ') {{ e.preventDefault(); play(); }}
  if (e.key === 'ArrowRight') show(i+1);
  if (e.key === 'ArrowLeft') show(i-1);
}});
show(0);
play();
</script>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    idx = 0
    kept: list[bytearray] = []
    for title, sub, lines in SCENES:
        step = 3
        n = len(lines)
        shown = 0
        while True:
            shown = min(n, shown + step if shown else min(step, n))
            pix = render_scene(title, sub, lines, shown)
            write_png(FRAMES / f"frame_{idx:03d}.png", pix)
            kept.append(pix)
            idx += 1
            if shown >= n:
                write_png(FRAMES / f"frame_{idx:03d}.png", pix)
                kept.append(pix)
                idx += 1
                break
    write_player(idx)
    gif_path = OUT / "nash_critique.gif"
    write_gif(gif_path, kept, delay_cs=90)
    print(f"wrote {idx} frames -> {FRAMES}")
    print(f"player -> {OUT / 'index.html'}")
    print(f"gif    -> {gif_path} ({gif_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
