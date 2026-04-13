import re

UNIDADES = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2,
    "três": 3, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9
}

DEZ_A_DEZENOVE = {
    "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "quatorze": 14, "catorze": 14, "quinze": 15,
    "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19
}

DEZENAS = {
    "vinte": 20,
    "trinta": 30,
    "quarenta": 40,
    "cinquenta": 50,
    "sessenta": 60,
    "setenta": 70,
}

IGNORAR = {"número", "numero", "bola", "saiu", "veio", "o", "a", "de", "e"}


def parse_number_words(text: str):
    words = [w for w in text.split() if w not in IGNORAR]
    if not words:
        return None

    total = 0
    used = False

    for w in words:
        if w in DEZ_A_DEZENOVE:
            total += DEZ_A_DEZENOVE[w]
            used = True
        elif w in DEZENAS:
            total += DEZENAS[w]
            used = True
        elif w in UNIDADES:
            total += UNIDADES[w]
            used = True

    if used and 1 <= total <= 75:
        return total

    return None


def parse_bingo_input(text: str):
    if not text:
        return None

    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    words_value = parse_number_words(text)

    digit_tokens = re.findall(r"\d+", text)
    digit_values = []

    for i, token in enumerate(digit_tokens):
        try:
            n = int(token)
            if 1 <= n <= 75:
                digit_values.append((i, token, n))
        except ValueError:
            pass

    if digit_values:
        digit_values.sort(key=lambda item: (len(item[1]), item[0]))
        best = digit_values[-1][2]

        if words_value is not None:
            for _, _, n in digit_values:
                if n == words_value:
                    return n

        return best

    if words_value is not None:
        return words_value

    return None