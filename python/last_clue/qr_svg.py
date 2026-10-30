"""ISO/IEC 18004 QR Code Model 2 encoder and decoder (PNG + SVG, stdlib-only).

Generates and programmatically decodes QR Code symbols for versions 1-10 (ECC Level M)
using only the Python standard library so Arduino UNO Q App Lab containers need no
external native imaging libraries.
"""

from __future__ import annotations

import re
import struct
import zlib

# Capacity for byte mode, ECC-M: (version, block_data_counts, ecc_per_block)
# Matches ISO/IEC 18004 Table 9.
_VERSIONS_M: tuple[tuple[int, tuple[int, ...], int], ...] = (
    (1, (16,), 10),
    (2, (28,), 16),
    (3, (44,), 26),
    (4, (32, 32), 18),
    (5, (43, 43), 24),
    (6, (27, 27, 27, 27), 16),
    (7, (31, 31, 31, 31), 18),
    (8, (38, 38, 39, 39), 22),
    (9, (36, 36, 36, 37, 37), 22),
    (10, (43, 43, 43, 43, 44), 26),
)

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


def _generator_polynomial(ecc_len: int) -> list[int]:
    """Compute the Reed-Solomon generator polynomial prod_{i=0}^{ecc_len-1} (x - alpha^i)."""
    poly = [1]
    for i in range(ecc_len):
        next_poly = [0] * (len(poly) + 1)
        alpha_i = _EXP[i]
        for j, coeff in enumerate(poly):
            next_poly[j] ^= coeff
            next_poly[j + 1] ^= _gf_mul(coeff, alpha_i)
        poly = next_poly
    return poly[1:]


def _reed_solomon(data: list[int], ecc_len: int) -> list[int]:
    gen = _generator_polynomial(ecc_len)
    result = [0] * ecc_len
    for byte in data:
        factor = byte ^ result[0]
        result = result[1:] + [0]
        for i, coef in enumerate(gen):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _bits_to_bytes(bits: list[int]) -> list[int]:
    rem = len(bits) % 8
    if rem != 0:
        bits = bits + [0] * (8 - rem)
    out: list[int] = []
    for i in range(0, len(bits), 8):
        value = 0
        for bit in bits[i : i + 8]:
            value = (value << 1) | bit
        out.append(value)
    return out


def _choose_version(payload_len: int) -> tuple[int, tuple[int, ...], int]:
    for version, block_counts, ecc_len in _VERSIONS_M:
        data_cw = sum(block_counts)
        char_bits = 8 if version <= 9 else 16
        needed = 4 + char_bits + payload_len * 8
        capacity_bits = data_cw * 8
        if needed <= capacity_bits:
            return version, block_counts, ecc_len
    raise ValueError("URL payload is too long for QR versions 1-10")


def _build_data_codewords(data: bytes, version: int, data_cw: int) -> list[int]:
    bits: list[int] = [0, 1, 0, 0]  # Byte mode indicator (0100)
    char_count_bits = 8 if version <= 9 else 16
    length = len(data)
    for shift in range(char_count_bits - 1, -1, -1):
        bits.append((length >> shift) & 1)
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    for _ in range(min(4, data_cw * 8 - len(bits))):
        bits.append(0)
    while len(bits) % 8 != 0:
        bits.append(0)
    codewords = _bits_to_bytes(bits)
    pad = (0xEC, 0x11)
    pad_i = 0
    while len(codewords) < data_cw:
        codewords.append(pad[pad_i % 2])
        pad_i += 1
    return codewords[:data_cw]


def _interleave(data_cw: list[int], block_counts: tuple[int, ...], ecc_len: int) -> list[int]:
    groups: list[list[int]] = []
    ecc_groups: list[list[int]] = []
    offset = 0
    for count in block_counts:
        chunk = data_cw[offset : offset + count]
        offset += count
        groups.append(chunk)
        ecc_groups.append(_reed_solomon(chunk, ecc_len))

    result: list[int] = []
    max_data = max(len(g) for g in groups)
    for i in range(max_data):
        for g in groups:
            if i < len(g):
                result.append(g[i])
    for i in range(ecc_len):
        for eg in ecc_groups:
            result.append(eg[i])
    return result


def _module_count(version: int) -> int:
    return 21 + (version - 1) * 4


def _place_finders(matrix: list[list[int | None]], size: int) -> None:
    positions = ((0, 0), (size - 7, 0), (0, size - 7))
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


def _reserve_format_and_version(
    matrix: list[list[int | None]], version: int, size: int
) -> None:
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
    if version >= 7:
        for i in range(18):
            r = i // 3
            c = size - 11 + (i % 3)
            matrix[r][c] = 0
            matrix[c][r] = 0


def _alignment_centers(version: int) -> tuple[int, ...]:
    table: dict[int, tuple[int, ...]] = {
        2: (6, 18),
        3: (6, 22),
        4: (6, 26),
        5: (6, 30),
        6: (6, 34),
        7: (6, 22, 38),
        8: (6, 24, 42),
        9: (6, 26, 46),
        10: (6, 28, 50),
    }
    return table.get(version, ())


def _place_alignments(matrix: list[list[int | None]], version: int, size: int) -> None:
    centers = _alignment_centers(version)
    for r in centers:
        for c in centers:
            if (r < 9 and c < 9) or (r < 9 and c > size - 10) or (r > size - 10 and c < 9):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    rr, cc = r + dr, c + dc
                    dark = abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0)
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


def _data_module_coordinates(version: int) -> list[tuple[int, int]]:
    """Return the ordered list of (row, col) coordinates that carry data/ECC bits."""
    size = _module_count(version)
    template: list[list[int | None]] = [[None] * size for _ in range(size)]
    _place_finders(template, size)
    _place_alignments(template, version, size)
    _place_timing(template, size)
    _place_dark_module(template, version)
    _reserve_format_and_version(template, version, size)

    coords: list[tuple[int, int]] = []
    direction_up = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        row_range = range(size - 1, -1, -1) if direction_up else range(size)
        for row in row_range:
            for c in (col, col - 1):
                if template[row][c] is None:
                    coords.append((row, c))
        direction_up = not direction_up
        col -= 2
    return coords


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
    data = (0b00 << 3) | mask  # ECC Level M = 00
    bits = data << 10
    for i in range(4, -1, -1):
        if bits & (1 << (i + 10)):
            bits ^= 0b10100110111 << i
    bits = ((data << 10) | bits) ^ 0b101010000010010
    return [(bits >> i) & 1 for i in range(14, -1, -1)]


def _version_bits(version: int) -> list[int]:
    d = version << 12
    for i in range(5, -1, -1):
        if d & (1 << (i + 12)):
            d ^= 0x1F25 << i
    v_info = (version << 12) | d
    return [(v_info >> i) & 1 for i in range(18)]


def _draw_format_and_version(
    matrix: list[list[int | None]], version: int, mask: int
) -> None:
    size = len(matrix)
    bits = _format_bits(mask)
    coords_a = (
        (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
    )
    for i, (r, c) in enumerate(coords_a):
        matrix[r][c] = bits[i]
    coords_b = (
        (size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8), (size - 5, 8),
        (size - 6, 8), (size - 7, 8),
        (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5), (8, size - 4),
        (8, size - 3), (8, size - 2), (8, size - 1),
    )
    for i, (r, c) in enumerate(coords_b):
        matrix[r][c] = bits[i]

    if version >= 7:
        vbits = _version_bits(version)
        for i in range(18):
            r = i // 3
            c = size - 11 + (i % 3)
            matrix[r][c] = vbits[i]
            matrix[c][r] = vbits[i]


def _penalty(matrix: list[list[int]]) -> int:
    size = len(matrix)
    score = 0
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
    for r in range(size - 1):
        for c in range(size - 1):
            v = matrix[r][c]
            if (
                v == matrix[r][c + 1]
                and v == matrix[r + 1][c]
                and v == matrix[r + 1][c + 1]
            ):
                score += 3
    dark = sum(sum(row) for row in matrix)
    total = size * size
    percent = (dark * 100) // total
    score += abs(percent - 50) // 5 * 10
    return score


def encode_qr_matrix(payload: str) -> list[list[int]]:
    """Return a validated ISO/IEC 18004 binary QR matrix for a UTF-8 string."""
    if not payload:
        raise ValueError("QR payload cannot be empty")
    data = payload.encode("utf-8")
    version, block_counts, ecc_len = _choose_version(len(data))
    data_cw = sum(block_counts)
    data_codewords = _build_data_codewords(data, version, data_cw)
    final_codewords = _interleave(data_codewords, block_counts, ecc_len)
    size = _module_count(version)

    best: list[list[int]] | None = None
    best_score = 10**9
    for mask in range(8):
        matrix: list[list[int | None]] = [[None] * size for _ in range(size)]
        _place_finders(matrix, size)
        _place_alignments(matrix, version, size)
        _place_timing(matrix, size)
        _place_dark_module(matrix, version)
        _reserve_format_and_version(matrix, version, size)
        _place_data(matrix, final_codewords, mask)
        _draw_format_and_version(matrix, version, mask)
        concrete = [[int(cell or 0) for cell in row] for row in matrix]
        score = _penalty(concrete)
        if score < best_score:
            best_score = score
            best = concrete
    assert best is not None
    return best


def matrix_to_svg(matrix: list[list[int]], *, border: int = 4, module_size: int = 8) -> str:
    """Render a QR matrix as a self-contained SVG string with a 4-module quiet zone."""
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


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def matrix_to_png(matrix: list[list[int]], *, border: int = 4, module_size: int = 8) -> bytes:
    """Render a QR matrix as an 8-bit grayscale PNG image using only the Python stdlib."""
    size = len(matrix)
    dim = (size + border * 2) * module_size

    white_row = b"\x00" + (b"\xff" * dim)
    scanlines = bytearray()

    for _ in range(border * module_size):
        scanlines.extend(white_row)

    for row in matrix:
        row_pixels = bytearray(b"\x00")
        row_pixels.extend(b"\xff" * (border * module_size))
        for cell in row:
            px = b"\x00" if cell else b"\xff"
            row_pixels.extend(px * module_size)
        row_pixels.extend(b"\xff" * (border * module_size))
        for _ in range(module_size):
            scanlines.extend(row_pixels)

    for _ in range(border * module_size):
        scanlines.extend(white_row)

    ihdr = struct.pack(">IIBBBBB", dim, dim, 8, 0, 0, 0, 0)
    compressed = zlib.compress(bytes(scanlines), level=6)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def generate_qr_svg(url: str) -> str:
    """Generate a validated SVG QR code for the given URL."""
    matrix = encode_qr_matrix(url)
    return matrix_to_svg(matrix)


def generate_qr_png(url: str) -> bytes:
    """Generate a validated PNG QR code for the given URL."""
    matrix = encode_qr_matrix(url)
    return matrix_to_png(matrix)


# --- Programmatic QR Decoder & Integrity Verifier ---


def decode_qr_matrix(matrix: list[list[int]]) -> str:
    """Verify finder patterns, format bits, and Reed-Solomon ECC, then decode UTF-8 payload."""
    size = len(matrix)
    if size < 21 or (size - 21) % 4 != 0:
        raise ValueError(f"Invalid QR matrix dimension: {size}")
    version = ((size - 21) // 4) + 1
    version_spec = next((spec for spec in _VERSIONS_M if spec[0] == version), None)
    if version_spec is None:
        raise ValueError(f"Unsupported QR version: {version}")
    _, block_counts, ecc_len = version_spec

    # 1. Verify 7x7 finder patterns at all 3 corners
    for r0, c0 in ((0, 0), (size - 7, 0), (0, size - 7)):
        for r in range(7):
            for c in range(7):
                expected = (
                    1
                    if (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                    else 0
                )
                if matrix[r0 + r][c0 + c] != expected:
                    raise ValueError(f"Invalid finder pattern at ({r0 + r}, {c0 + c})")

    # 2. Extract and verify both format information copies
    coords_a = (
        (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
    )
    coords_b = (
        (size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8), (size - 5, 8),
        (size - 6, 8), (size - 7, 8),
        (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5), (8, size - 4),
        (8, size - 3), (8, size - 2), (8, size - 1),
    )
    bits_a = [matrix[r][c] for r, c in coords_a]
    bits_b = [matrix[r][c] for r, c in coords_b]
    if bits_a != bits_b:
        raise ValueError("Format information copies A and B do not match")

    matched_mask: int | None = None
    for candidate_mask in range(8):
        if _format_bits(candidate_mask) == bits_a:
            matched_mask = candidate_mask
            break
    if matched_mask is None:
        raise ValueError("Format information failed BCH(15,5) verification")

    # 3. Read and unmask all data & ECC bits
    coords = _data_module_coordinates(version)
    raw_bits: list[int] = []
    for r, c in coords:
        bit = matrix[r][c]
        if _mask_fn(matched_mask, r, c):
            bit ^= 1
        raw_bits.append(bit)

    total_codewords = sum(block_counts) + len(block_counts) * ecc_len
    interleaved_cw = _bits_to_bytes(raw_bits[: total_codewords * 8])

    # 4. De-interleave blocks and verify Reed-Solomon ECC codewords
    num_blocks = len(block_counts)
    data_blocks: list[list[int]] = [[] for _ in range(num_blocks)]
    ecc_blocks: list[list[int]] = [[] for _ in range(num_blocks)]

    idx = 0
    max_data = max(block_counts)
    for col_i in range(max_data):
        for b_i, b_len in enumerate(block_counts):
            if col_i < b_len:
                data_blocks[b_i].append(interleaved_cw[idx])
                idx += 1
    for _ in range(ecc_len):
        for b_i in range(num_blocks):
            ecc_blocks[b_i].append(interleaved_cw[idx])
            idx += 1

    for b_i in range(num_blocks):
        expected_ecc = _reed_solomon(data_blocks[b_i], ecc_len)
        if expected_ecc != ecc_blocks[b_i]:
            raise ValueError(f"Reed-Solomon ECC verification failed for block {b_i}")

    data_cw: list[int] = []
    for block in data_blocks:
        data_cw.extend(block)

    # 5. Parse byte-mode bitstream into UTF-8 string
    data_bits: list[int] = []
    for byte in data_cw:
        for shift in range(7, -1, -1):
            data_bits.append((byte >> shift) & 1)

    mode = (data_bits[0] << 3) | (data_bits[1] << 2) | (data_bits[2] << 1) | data_bits[3]
    if mode != 0b0100:
        raise ValueError(f"Expected byte mode (0b0100), got {bin(mode)}")

    char_count_bits = 8 if version <= 9 else 16
    length = 0
    for bit in data_bits[4 : 4 + char_count_bits]:
        length = (length << 1) | bit

    payload_start = 4 + char_count_bits
    payload_bits = data_bits[payload_start : payload_start + length * 8]
    payload_bytes = bytes(_bits_to_bytes(payload_bits))
    return payload_bytes.decode("utf-8")


def decode_qr_png(png_bytes: bytes) -> str:
    """Parse a PNG QR code image and decode its embedded URL."""
    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG header")

    pos = 8
    width = height = 0
    idat_parts: list[bytes] = []
    while pos < len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos : pos + 4])[0]
        chunk_type = png_bytes[pos + 4 : pos + 8]
        chunk_data = png_bytes[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            if bit_depth != 8 or color_type != 0 or width != height:
                raise ValueError("Unsupported PNG format for QR decoder")
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    raw = zlib.decompress(b"".join(idat_parts))
    stride = width + 1
    pixels: list[list[int]] = []
    for r in range(height):
        row_start = r * stride
        filter_type = raw[row_start]
        if filter_type != 0:
            raise ValueError("Unsupported PNG scanline filter")
        row = [0 if b < 128 else 1 for b in raw[row_start + 1 : row_start + stride]]
        pixels.append(row)

    # Locate top-left dark pixel to determine border and module_size
    first_r = first_c = None
    for r in range(height):
        for c in range(width):
            if pixels[r][c] == 0:
                first_r, first_c = r, c
                break
        if first_r is not None:
            break
    if first_r is None or first_c is None:
        raise ValueError("No dark modules found in PNG")

    # Top finder bar is 7 modules wide
    run = 0
    while first_c + run < width and pixels[first_r][first_c + run] == 0:
        run += 1
    module_size = run // 7
    if module_size < 1:
        raise ValueError("Could not determine QR module size from PNG")

    border = first_c // module_size
    qr_size = (width // module_size) - 2 * border
    matrix: list[list[int]] = []
    for r in range(qr_size):
        py = (r + border) * module_size + (module_size // 2)
        row_vals: list[int] = []
        for c in range(qr_size):
            px = (c + border) * module_size + (module_size // 2)
            row_vals.append(1 if pixels[py][px] == 0 else 0)
        matrix.append(row_vals)

    return decode_qr_matrix(matrix)


def decode_qr_svg(svg_text: str) -> str:
    """Parse an SVG QR code string and decode its embedded URL."""
    vb_match = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg_text)
    if not vb_match:
        raise ValueError("SVG missing viewBox attribute")
    dim = int(vb_match.group(1))
    rect_matches = re.findall(
        r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" fill="#000000"/>',
        svg_text,
    )
    if not rect_matches:
        raise ValueError("No dark module rects found in SVG")

    module_size = int(rect_matches[0][2])
    min_x = min(int(m[0]) for m in rect_matches)
    border = min_x // module_size
    qr_size = (dim // module_size) - 2 * border

    matrix = [[0] * qr_size for _ in range(qr_size)]
    for x_str, y_str, _, _ in rect_matches:
        c = (int(x_str) // module_size) - border
        r = (int(y_str) // module_size) - border
        if 0 <= r < qr_size and 0 <= c < qr_size:
            matrix[r][c] = 1

    return decode_qr_matrix(matrix)
