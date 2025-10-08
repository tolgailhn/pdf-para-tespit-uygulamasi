def extract_totals_only(text):
    """
    'Total/Totale/Totaal' ve Almanca: Bruttobetrag, Nettobetrag, Gesamtbetrag, Summe.
    Çıktı: list of dicts: {cur, val(float), pos(int), label(str), labeled(bool), raw(str)}
    """
    candidates = []

    def push(cur, amt_str, label, pos):
        num = normalize_number_str(amt_str)
        try:
            val = float(num)
            candidates.append({
                "cur": cur,
                "val": val,
                "pos": pos,
                "label": label or "",
                "labeled": bool(label),
                "raw": f"{label or ''} {cur} {amt_str}".strip()
            })
        except:
            pass

    labels = r"(Total|Totale|Totaal|Summe|Gesamtbetrag|Bruttobetrag|Nettobetrag)"
    currs  = r"(EUR|GBP|PLN|SEK)"

    # 1) LABEL ... CUR AMT
    for m in re.finditer(rf"{labels}.*?\b{currs}\s+([0-9\.,]+)", text, flags=re.IGNORECASE|re.DOTALL):
        lbl, cur, amt = m.group(1), m.group(2), m.group(3)
        push(cur, amt, lbl, m.start())

    # 2) CUR AMT ... LABEL
    for m in re.finditer(rf"\b{currs}\s+([0-9\.,]+).*?{labels}", text, flags=re.IGNORECASE|re.DOTALL):
        cur, amt, lbl = m.group(1), m.group(2), m.group(3)
        push(cur, amt, lbl, m.start())

    # 3) Total CUR AMT (klasik)
    for m in re.finditer(rf"(?:^|\s){labels}\s+{currs}\s+([0-9\.,]+)", text, flags=re.IGNORECASE):
        lbl, cur, amt = m.group(1), m.group(2), m.group(3)
        push(cur, amt, lbl, m.start())

    # Yedek: hiçbir şey bulunmazsa boş döner
    return candidates
