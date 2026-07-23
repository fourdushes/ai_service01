def summarize_text(text):
    if not text.strip():
        return ""

    sentences = text.split(".")
    return ".".join(sentences[:2]).strip()