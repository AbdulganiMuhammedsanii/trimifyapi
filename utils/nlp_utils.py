import re

def remove_filler_words(transcript):
    filler_words = ["um", "uh", "like", "you know", "basically"]
    pattern = r'\b(?:' + '|'.join(map(re.escape, filler_words)) + r')\b'
    cleaned = re.sub(pattern, '', transcript, flags=re.IGNORECASE)
    return cleaned
