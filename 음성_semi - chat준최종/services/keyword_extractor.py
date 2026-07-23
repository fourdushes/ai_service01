from collections import Counter

def extract_keywords(text):
    words = text.replace("\n", " ").split()
    words = [w for w in words if len(w) > 1]

    count = Counter(words)
    return [w for w, _ in count.most_common(5)]