import math
import re
from collections import Counter


TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text):
    return TOKEN_PATTERN.findall((text or "").lower())


def build_embedding(text):
    counts = Counter(tokenize(text))
    norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
    return {token: value / norm for token, value in counts.items()}


def cosine_similarity(left_embedding, right_embedding):
    if len(left_embedding) > len(right_embedding):
        left_embedding, right_embedding = right_embedding, left_embedding
    return sum(value * right_embedding.get(token, 0.0) for token, value in left_embedding.items())
