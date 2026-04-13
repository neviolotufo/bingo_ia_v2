def check_quina(marks):
    for row in marks:
        if all(row):
            return True

    for c in range(5):
        if all(marks[r][c] for r in range(5)):
            return True

    if all(marks[i][i] for i in range(5)):
        return True

    if all(marks[i][4 - i] for i in range(5)):
        return True

    return False


def check_mask(marks, coords):
    return all(marks[r][c] for r, c in coords)


PATTERN_MASKS = {
    "l": [
        (0, 0), (1, 0), (2, 0), (3, 0), (4, 0),
        (4, 1), (4, 2), (4, 3), (4, 4),
    ],
    "v": [
        (0, 0), (1, 0), (2, 0), (3, 0), (4, 0),
        (0, 4), (1, 4), (2, 4), (3, 4), (4, 4),
        (4, 1), (4, 2), (4, 3),
    ],
}


def has_bingo(marks, pattern_name: str) -> bool:
    p = (pattern_name or "").strip().lower()

    if p == "quina":
        return check_quina(marks)

    if p in PATTERN_MASKS:
        return check_mask(marks, PATTERN_MASKS[p])

    return False