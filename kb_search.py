"""Пошуковий шар KB — ранжування за релевантністю.

Два рівні, без зовнішніх залежностей у базовому:
  * lexical (TF-IDF cosine) — працює завжди, без ключа. Ранжує за збігом слів.
  * vector (embeddings) — якщо є провайдер (VOYAGE_API_KEY або OPENAI_API_KEY):
    рахуємо вектор запиту і косинус до векторів у колонці `Embedding`.
    Це дає пошук «за змістом», у т.ч. крос-мовний, чого TF-IDF не вміє.

kb_api.search() викликає rank() — лексично зараз, векторно щойно буде embeddings.
"""
import json
import math
import os
import re

from kb_schema import (NAME_COL, SUMMARY_COL, EMBEDDING_COL)

_WORD = re.compile(r"[\wʼ'-]+", re.UNICODE)
# поля, що формують пошуковий текст картки (крім службових)
_TEXT_FIELDS = [NAME_COL, SUMMARY_COL, "Категорія", "Тип документа", "Сфера",
                "Форма", "Питання / тригер", "Тип послуги", "Послуги", "Джерело",
                "Право", "Юрисдикція / регіон"]


def _tokens(text):
    return [w.lower() for w in _WORD.findall(text or "")]


def record_text(rec):
    return " ".join(str(rec.get(f, "")) for f in _TEXT_FIELDS if rec.get(f))


# --- TF-IDF cosine (lexical) -------------------------------------------------
def _tfidf_rank(query, records):
    docs = [_tokens(record_text(r)) for r in records]
    qtok = _tokens(query)
    if not qtok:
        return [(r, 0.0) for r in records]
    N = len(docs) or 1
    df = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((N + 1) / (n + 1)) + 1 for t, n in df.items()}

    def vec(toks):
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        return {t: (c / len(toks)) * idf.get(t, math.log(N + 1) + 1)
                for t, c in tf.items()}

    qv = vec(qtok)
    qn = math.sqrt(sum(v * v for v in qv.values())) or 1.0
    out = []
    for r, d in zip(records, docs):
        dv = vec(d)
        dot = sum(qv.get(t, 0) * dv.get(t, 0) for t in qv)
        dn = math.sqrt(sum(v * v for v in dv.values())) or 1.0
        out.append((r, dot / (qn * dn)))
    return out


# --- vector (embeddings, опційно) -------------------------------------------
def _embedder():
    """Повертає fn(text)->list[float] якщо є провайдер, інакше None."""
    if os.environ.get("VOYAGE_API_KEY"):
        try:
            import voyageai
            client = voyageai.Client()

            def embed(text):
                return client.embed([text], model="voyage-3",
                                    input_type="query").embeddings[0]
            return embed
        except ImportError:
            pass
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI()

            def embed(text):
                return client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text).data[0].embedding
            return embed
        except ImportError:
            pass
    return None


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _vector_rank(query, records, embed):
    qv = embed(query)
    out = []
    for r in records:
        raw = r.get(EMBEDDING_COL, "")
        if not raw:
            out.append((r, 0.0)); continue
        try:
            dv = json.loads(raw)
            out.append((r, _cosine(qv, dv)))
        except Exception:
            out.append((r, 0.0))
    return out


# --- публічне ----------------------------------------------------------------
def rank(query, records, limit=10, min_score=0.01):
    """Відранжувати records за релевантністю до query. Вектор, якщо є embeddings."""
    embed = _embedder()
    have_vectors = embed and any(r.get(EMBEDDING_COL) for r in records)
    scored = _vector_rank(query, records, embed) if have_vectors \
        else _tfidf_rank(query, records)
    scored.sort(key=lambda x: x[1], reverse=True)
    mode = "vector" if have_vectors else "lexical"
    hits = []
    for r, s in scored:
        if s < min_score:
            continue
        hits.append({**r, "_score": round(s, 4), "_match": mode})
    return hits[:limit]


def embed_text(text):
    """Порахувати вектор для тексту (для наповнення колонки Embedding). None без ключа."""
    embed = _embedder()
    return embed(text) if embed else None
