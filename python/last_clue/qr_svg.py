"""Stdlib-only QR Code Model 2 encoder that emits SVG.

Avoids the third-party ``qrcode`` package so Arduino App Lab containers start
even when that dependency is missing or failed to install.
"""

from __future__ import annotations

# ECC level M generator polynomials (ISO/IEC 18004)
_ECC_POLY: dict[int, list[int]] = {
    7: [87, 229, 146, 149, 238, 155, 200],
    10: [251, 67, 46, 61, 118, 70, 64, 94, 32, 45],
    13: [74, 152, 176, 100, 86, 100, 106, 104, 130, 218, 206, 140, 78],
    15: [8, 183, 61, 91, 202, 37, 51, 58, 58, 237, 140, 124, 5, 99, 105],
    16: [120, 104, 107, 109, 102, 161, 76, 3, 91, 191, 147, 169, 182, 194, 225, 120],
    17: [
        43, 139, 206, 78, 43, 239, 123, 206, 214, 147, 24, 99, 150, 39, 243, 163, 136
    ],
    18: [
        215, 234, 158, 94, 184, 97, 118, 170, 79, 187, 222, 95, 60, 186, 156, 81, 242, 146
    ],
    20: [
        17, 60, 79, 50, 61, 163, 26, 187, 202, 180, 221, 225, 83, 239, 156, 164, 212, 212, 188, 190
    ],
    22: [
        210, 171, 247, 242, 93, 230, 14, 109, 221, 53, 200, 74, 8, 172, 98, 80, 219, 134, 160, 105, 165, 231
    ],
    24: [
        229, 121, 215, 11, 165, 33, 237, 35, 85, 254, 84, 54, 234, 108, 190, 101, 155, 87, 119, 98, 79, 35, 133, 134
    ],
    26: [
        173, 125, 158, 2, 103, 182, 118, 17, 145, 201, 111, 28, 165, 53, 161, 133, 211, 86, 88, 164, 193, 109, 60, 230, 93, 181
    ],
}

# Capacity for byte mode, ECC-M: (version, data_codewords, ecc_per_block, blocks)
_VERSIONS_M: list[tuple[int, int, int, int]] = [
    (1, 16, 10, 1),
    (2, 28, 16, 1),
    (3, 44, 26, 1),
    (4, 64, 18, 2),
    (5, 86, 24, 2),
    (6, 108, 16, 4),
    (7, 124, 18, 4),
    (8, 154, 22, 4),
    (9, 182, 22, 5),
    (10, 216, 26, 5),
]

_EXP = [0] * 512
_LOG = [0] * 256


def _init_gf() -> None:
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_init_gf()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _reed_solomon(data: list[int], ecc_len: int) -> list[int]:
    gen = _ECC_POLY[ecc_len]
    result = [0] * ecc_len
    for byte in data:
        factor = byte ^ result[0]
        result = result[1:] + [0]
        for i, coef in enumerate(gen):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _bits_to_bytes(bits: list[int]) -> list[int]:
    while len(bits) % 8 != 0:
        bits.append(0)
    out: list[int] = []
    for i in range(0, len(bits), 8):
        value = 0
        for bit in bits[i : i + 8]:
            value = (value << 1) | bit
        out.append(value)
    return out


def _choose_version(payload_len: int) -> tuple[int, int, int, int]:
    # Byte mode: 4-bit mode + length + payload + 4 terminator bits (approx)
    for version, data_cw, ecc_len, blocks in _VERSIONS_M:
        char_bits = 8 if version <= 9 else 16
        needed = 4 + char_bits + payload_len * 8 + 4
        capacity_bits = data_cw * 8
        if needed <= capacity_bits:
            return version, data_cw, ecc_len, blocks
    raise ValueError("URL too long for supported QR versions")


def _build_data_codewords(data: bytes, version: int, data_cw: int) -> list[int]:
    bits: list[int] = []
    # Mode indicator: byte = 0100
    bits.extend([0, 1, 0, 0])
    char_count_bits = 8 if version <= 9 else 16
    length = len(data)
    for shift in range(char_count_bits - 1, -1, -1):
        bits.append((length >> shift) & 1)
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    # Terminator
    for _ in range(min(4, data_cw * 8 - len(bits))):
        bits.append(0)
    while len(bits) % 8 != 0:
        bits.append(0)
    codewords = _bits_to_bytes(bits)
    pad = [0xEC, 0x11]
    pad_i = 0
    while len(codewords) < data_cw:
        codewords.append(pad[pad_i % 2])
        pad_i += 1
    return codewords[:data_cw]


def _interleave(data_cw: list[int], ecc_len: int, blocks: int) -> list[int]:
    if blocks == 1:
        return data_cw + _reed_solomon(data_cw, ecc_len)

    block_size = len(data_cw) // blocks
    short_blocks = blocks - (len(data_cw) % blocks)
    # For simplicity with evenly divisible sizes (true for chosen M table rows)
    groups: list[list[int]] = []
    ecc_groups: list[list[int]] = []
    offset = 0
    for b in range(blocks):
        # Some versions have uneven block sizes; keep simple even split when possible
        size = block_size + (0 if b < short_blocks or len(data_cw) % blocks == 0 else 1)
        if len(data_cw) % blocks != 0:
            # Prefer larger blocks at the end (ISO style)
            size = block_size if b < short_blocks else block_size + 1
        chunk = data_cw[offset : offset + size]
        offset += size
        groups.append(chunk)
        ecc_groups.append(_reed_solomon(chunk, ecc_len))

    result: list[int] = []
    max_data = max(len(g) for g in groups)
    for i in range(max_data):
        for g in groups:
            if i < len(g):
                result.append(g[i])
    for i in range(ecc_len):
        for g in ecc_groups:
            result.append(g[i])
    return result


def _module_count(version: int) -> int:
    return 21 + (version - 1) * 4


def _place_finders(matrix: list[list[int | None]], size: int) -> None:
    positions = [(0, 0), (size - 7, 0), (0, size - 7)]
    for r0, c0 in positions:
        for r in range(-1, 8):
            for c in range(-1, 8):
                rr, cc = r0 + r, c0 + c
                if 0 <= rr < size and 0 <= cc < size:
                    if 0 <= r <= 6 and 0 <= c <= 6:
                        dark = (
                            r in (0, 6)
                            or c in (0, 6)
                            or (2 <= r <= 4 and 2 <= c <= 4)
                        )
                        matrix[rr][cc] = 1 if dark else 0
                    else:
                        matrix[rr][cc] = 0


def _place_timing(matrix: list[list[int | None]], size: int) -> None:
    for i in range(size):
        if matrix[6][i] is None:
            matrix[6][i] = 1 if i % 2 == 0 else 0
        if matrix[i][6] is None:
            matrix[i][6] = 1 if i % 2 == 0 else 0


def _place_dark_module(matrix: list[list[int | None]], version: int) -> None:
    matrix[(4 * version) + 9][8] = 1


def _reserve_format(matrix: list[list[int | None]], size: int) -> None:
    for i in range(9):
        if matrix[8][i] is None:
            matrix[8][i] = 0
        if matrix[i][8] is None:
            matrix[i][8] = 0
    for i in range(8):
        if matrix[8][size - 1 - i] is None:
            matrix[8][size - 1 - i] = 0
        if matrix[size - 1 - i][8] is None:
            matrix[size - 1 - i][8] = 0


def _alignment_centers(version: int) -> list[int]:
    if version == 1:
        return []
    # Simplified table for versions 2-10
    table = {
        2: [6, 18],
        3: [6, 22],
        4: [6, 26],
        5: [6, 30],
        6: [6, 34],
        7: [6, 22, 38],
        8: [6, 24, 42],
        9: [6, 26, 46],
        10: [6, 28, 50],
    }
    return table.get(version, [])


def _place_alignments(matrix: list[list[int | None]], version: int, size: int) -> None:
    centers = _alignment_centers(version)
    for r in centers:
        for c in centers:
            # Skip finder corners
            if (r < 9 and c < 9) or (r < 9 and c > size - 10) or (r > size - 10 and c < 9):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    rr, cc = r + dr, c + dc
                    dark = (
                        abs(dr) == 2
                        or abs(dc) == 2
                        or (dr == 0 and dc == 0)
                    )
                    matrix[rr][cc] = 1 if dark else 0


def _mask_fn(mask: int, r: int, c: int) -> bool:
    if mask == 0:
        return (r + c) % 2 == 0
    if mask == 1:
        return r % 2 == 0
    if mask == 2:
        return c % 3 == 0
    if mask == 3:
        return (r + c) % 3 == 0
    if mask == 4:
        return (r // 2 + c // 3) % 2 == 0
    if mask == 5:
        return (r * c) % 2 + (r * c) % 3 == 0
    if mask == 6:
        return ((r * c) % 2 + (r * c) % 3) % 2 == 0
    return ((r + c) % 2 + (r * c) % 3) % 2 == 0


def _place_data(matrix: list[list[int | None]], codewords: list[int], mask: int) -> None:
    size = len(matrix)
    bits: list[int] = []
    for byte in codewords:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)

    bit_i = 0
    direction_up = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        row_range = range(size - 1, -1, -1) if direction_up else range(size)
        for row in row_range:
            for c in (col, col - 1):
                if matrix[row][c] is not None:
                    continue
                bit = bits[bit_i] if bit_i < len(bits) else 0
                bit_i += 1
                if _mask_fn(mask, row, c):
                    bit ^= 1
                matrix[row][c] = bit
        direction_up = not direction_up
        col -= 2


def _format_bits(mask: int) -> list[int]:
    # ECC-M = 00, combined with 3-bit mask, BCH(15,5)
    data = (0b00 << 3) | mask
    bits = data << 10
    for i in range(4, -1, -1):
        if bits & (1 << (i + 10)):
            bits ^= 0b10100110111 << i
    bits = (data << 10 | bits) ^ 0b101010000010010
    return [(bits >> i) & 1 for i in range(14, -1, -1)]


def _draw_format(matrix: list[list[int | None]], mask: int) -> None:
    size = len(matrix)
    bits = _format_bits(mask)
    # Horizontal near finder
    coords_a = [
        (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
    ]
    for i, (r, c) in enumerate(coords_a):
        matrix[r][c] = bits[i]
    # Second copy
    coords_b = [
        (size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8), (size - 5, 8),
        (size - 6, 8), (size - 7, 8),
        (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5), (8, size - 4),
        (8, size - 3), (8, size - 2), (8, size - 1),
    ]
    for i, (r, c) in enumerate(coords_b):
        matrix[r][c] = bits[i]


def _penalty(matrix: list[list[int]]) -> int:
    size = len(matrix)
    score = 0
    # N1: runs of 5+
    for row in matrix:
        run = 1
        for i in range(1, size):
            if row[i] == row[i - 1]:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run = 1
        if run >= 5:
            score += 3 + (run - 5)
    for c in range(size):
        run = 1
        for r in range(1, size):
            if matrix[r][c] == matrix[r - 1][c]:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run = 1
        if run >= 5:
            score += 3 + (run - 5)
    # N2: 2x2 blocks
    for r in range(size - 1):
        for c in range(size - 1):
            v = matrix[r][c]
            if (
                v == matrix[r][c + 1]
                and v == matrix[r + 1][c]
                and v == matrix[r + 1][c + 1]
            ):
                score += 3
    # N4: balance
    dark = sum(sum(row) for row in matrix)
    total = size * size
    percent = (dark * 100) // total
    score += abs(percent - 50) // 5 * 10
    return score


def encode_qr_matrix(payload: str) -> list[list[int]]:
    """Return a binary QR matrix for the given UTF-8 text payload."""
    data = payload.encode("utf-8")
    version, data_cw, ecc_len, blocks = _choose_version(len(data))
    data_codewords = _build_data_codewords(data, version, data_cw)
    final_codewords = _interleave(data_codewords, ecc_len, blocks)
    size = _module_count(version)

    best: list[list[int]] | None = None
    best_score = 10**9
    for mask in range(8):
        matrix: list[list[int | None]] = [[None] * size for _ in range(size)]
        _place_finders(matrix, size)
        _place_alignments(matrix, version, size)
        _place_timing(matrix, size)
        _place_dark_module(matrix, version)
        _reserve_format(matrix, size)
        _place_data(matrix, final_codewords, mask)
        _draw_format(matrix, mask)
        concrete = [[int(cell or 0) for cell in row] for row in matrix]
        score = _penalty(concrete)
        if score < best_score:
            best_score = score
            best = concrete
    assert best is not None
    return best


def matrix_to_svg(matrix: list[list[int]], *, border: int = 2, module_size: int = 8) -> str:
    """Render a QR matrix as a self-contained SVG string."""
    size = len(matrix)
    dim = (size + border * 2) * module_size
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" '
        f'width="{dim}" height="{dim}" shape-rendering="crispEdges">'
        f'<rect width="100%" height="100%" fill="#ffffff"/>'
    ]
    for r, row in enumerate(matrix):
        for c, cell in enumerate(row):
            if cell:
                x = (c + border) * module_size
                y = (r + border) * module_size
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{module_size}" '
                    f'height="{module_size}" fill="#000000"/>'
                )
    parts.append("</svg>")
    return "".join(parts)


def generate_qr_svg(url: str) -> str:
    """Generate a scannable SVG QR code for a join URL using only the stdlib."""
    matrix = encode_qr_matrix(url)
    return matrix_to_svg(matrix)
