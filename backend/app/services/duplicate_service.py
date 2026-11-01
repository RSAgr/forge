import math
import re
from collections import Counter

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Grievance

STOP_WORDS = {"the", "a", "an", "is", "are", "was", "were", "and", "or", "to", "of", "in", "on"}


def _terms(value: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", value.lower())
    return [term for i, word in enumerate(words) for term in (word, f"{word} {words[i+1]}" if i + 1 < len(words) else None) if term and term not in STOP_WORDS]


def text_similarity(left: str, right: str) -> float:
    docs = [_terms(left), _terms(right)]
    if not docs[0] or not docs[1]:
        return 0.0
    df = Counter(set(docs[0]) | set(docs[1]))
    vectors = []
    for terms in docs:
        counts = Counter(terms)
        vector = {term: (count / len(terms)) * (math.log(3 / (1 + df[term])) + 1) for term, count in counts.items()}
        norm = math.sqrt(sum(weight * weight for weight in vector.values()))
        vectors.append({term: weight / norm for term, weight in vector.items()})
    return sum(weight * vectors[1].get(term, 0) for term, weight in vectors[0].items())


def find_duplicate(db: Session, category: str, description: str, latitude: float, longitude: float):
    rows = db.execute(text("""
        SELECT id, description FROM grievances
        WHERE duplicate_of IS NULL AND category = :category
          AND ST_DWithin(location, ST_SetSRID(ST_MakePoint(:longitude,:latitude),4326)::geography,250)
    """), {"category": category, "latitude": latitude, "longitude": longitude}).mappings().all()
    if not rows:
        return None
    ranked = [(text_similarity(description, row["description"]), row["id"]) for row in rows]
    similarity, grievance_id = max(ranked, default=(0.0, None))
    return db.get(Grievance, grievance_id) if similarity >= 0.3 else None
