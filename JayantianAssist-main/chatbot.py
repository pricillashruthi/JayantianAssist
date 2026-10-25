"""Retrieval chatbot over the Kristu Jayanti website knowledge base.

Pure-Python NLP pipeline: tokenise -> stop-word removal -> light stemming ->
synonym expansion -> BM25 ranking. No external ML dependencies.

Optional: set ANTHROPIC_API_KEY and `pip install anthropic` to have Claude write
a natural-language answer *grounded only* in the retrieved passages.
"""
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

KB_PATH = Path(__file__).parent / "data" / "knowledge_base.json"

STOPWORDS = set("""a an the is are was were be been am do does did of in on at to for from by with and or
but if then than that this these those it its i me my we our you your can could would should will shall may
might about what which who whom whose when where why how tell give show please any some there their them
kristu jayanti kju university college""".split())

# Query expansion: user word -> extra words that appear in the knowledge base
SYNONYMS = {
    "cost": ["fee", "tuition"], "price": ["fee"], "pay": ["fee", "payment"], "money": ["fee"],
    "job": ["placement", "recruiter", "package"], "jobs": ["placement", "recruiter"],
    "salary": ["package", "lpa"], "company": ["recruiter", "placement"], "companies": ["recruiter", "placement"],
    "hire": ["recruiter", "placement"], "campus-placement": ["placement"],
    "join": ["admission", "apply"], "enroll": ["admission", "apply"], "enrol": ["admission", "apply"],
    "register": ["admission", "apply"], "seat": ["admission"], "entry": ["admission"],
    "stay": ["hostel"], "room": ["hostel"], "accommodation": ["hostel"], "dorm": ["hostel"],
    "canteen": ["cafeteria"], "mess": ["cafeteria"], "food": ["cafeteria"], "eat": ["cafeteria"],
    "book": ["library"], "books": ["library"], "borrow": ["library"],
    "test": ["exam"], "tests": ["exam"], "exams": ["exam"], "revaluation": ["grievance", "exam"],
    "marks": ["exam", "assessment"], "results": ["exam"], "result": ["exam"],
    "doctor": ["health", "medical"], "hospital": ["health"], "sick": ["health"], "medical": ["health"],
    "counsellor": ["counselling"], "counselor": ["counselling"], "counseling": ["counselling"], "therapist": ["counselling"],
    "stress": ["counselling"], "depression": ["counselling"], "anxiety": ["counselling"],
    "course": ["programme", "ug", "pg"], "courses": ["programme", "ug", "pg"], "degree": ["programme"],
    "degrees": ["programme"], "branch": ["programme"], "program": ["programme"], "programs": ["programme"],
    "bachelor": ["ug"], "bachelors": ["ug"], "undergraduate": ["ug"], "master": ["pg"], "masters": ["pg"],
    "postgraduate": ["pg"], "doctorate": ["phd"], "doctoral": ["phd"],
    "phone": ["contact", "phone"], "call": ["contact", "phone"], "mail": ["email", "contact"],
    "reach": ["contact"], "located": ["address", "location"], "location": ["address", "campus"],
    "ranking": ["nirf", "rank"], "rank": ["nirf"], "rated": ["naac", "nirf"], "grade": ["naac"],
    "principal": ["vice", "chancellor"], "vc": ["vice", "chancellor"], "head": ["chancellor", "vice"],
    "timing": ["timings"], "hours": ["timings"], "open": ["timings"],
    "wifi": ["wi-fi"], "internet": ["wi-fi"], "sport": ["sports"], "gym": ["sports"], "play": ["sports"],
    "club": ["clubs"], "society": ["clubs"], "fest": ["clubs", "events"],
    "scholar": ["scholarship"], "aid": ["scholarship"], "waiver": ["scholarship"], "loan": ["scholarship"],
    "documents": ["documents"], "certificate": ["documents"], "certificates": ["documents"],
    "computer": ["mca", "bca", "computer"], "it": ["mca", "bca", "computer"], "coding": ["mca", "bca"],
}

GREETINGS = {"hi", "hello", "hey", "hii", "hola", "namaste", "good morning", "good afternoon", "good evening"}
THANKS = {"thanks", "thank you", "thx", "ty", "thank u"}
BYES = {"bye", "goodbye", "see you", "cya"}

FALLBACK = (
    "I couldn't find that on the Kristu Jayanti website data I have. "
    "Try asking about admissions, fees, courses, placements, hostels, library, exams, scholarships, "
    "clubs or sports. You can also contact the university directly: 080-68737777 or info@kristujayanti.com."
)

_TOKEN_RE = re.compile(r"[a-z0-9\+\#\.\-]+")


def _stem(w: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ies", "ied", "es", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            if suf in ("ies", "ied"):
                return w[: -len(suf)] + "y"
            return w[: -len(suf)]
    return w


def tokenize(text: str):
    words = [w.strip(".-") for w in _TOKEN_RE.findall(text.lower())]
    return [_stem(w) for w in words if w and w not in STOPWORDS]


def expand_query(text: str):
    base = [w.strip(".-") for w in _TOKEN_RE.findall(text.lower())]
    extra = []
    for w in base:
        extra.extend(SYNONYMS.get(w, []))
    # also handle two-word phrases
    return tokenize(text) + [_stem(e) for e in extra]


class Chatbot:
    def __init__(self, kb_path: Path = KB_PATH, k1: float = 1.5, b: float = 0.75):
        self.docs = json.loads(Path(kb_path).read_text(encoding="utf-8"))
        self.k1, self.b = k1, b
        self.doc_tokens = []
        for d in self.docs:
            # Title and keywords are repeated so they weigh more than body text.
            tokens = tokenize(d["text"]) + 3 * tokenize(d["title"]) + 3 * tokenize(d.get("keywords", ""))
            self.doc_tokens.append(tokens)
        self.tfs = [Counter(t) for t in self.doc_tokens]
        self.avgdl = sum(len(t) for t in self.doc_tokens) / len(self.doc_tokens)
        n = len(self.docs)
        df = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, top_k: int = 3):
        q = expand_query(query)
        if not q:
            return []
        scores = []
        for i, tf in enumerate(self.tfs):
            dl = len(self.doc_tokens[i])
            s = 0.0
            for t in set(q):
                f = tf.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        return [(s, self.docs[i]) for s, i in scores[:top_k]]

    def answer(self, message: str) -> dict:
        msg = message.strip().lower().rstrip("!.?")
        if msg in GREETINGS:
            return {"answer": "Hello! I'm the Kristu Jayanti University assistant. Ask me about admissions, fees, courses, "
                              "placements, hostels, library, exams, scholarships, clubs or sports.", "sources": []}
        if msg in THANKS:
            return {"answer": "You're welcome! Ask me anything else about Kristu Jayanti.", "sources": []}
        if msg in BYES:
            return {"answer": "Goodbye! All the best.", "sources": []}

        hits = self.search(message, top_k=3)
        if not hits or hits[0][0] < 1.5:
            return {"answer": FALLBACK, "sources": []}

        best_score, best = hits[0]
        passages = [best]
        # include a second passage only when it is nearly as relevant
        if len(hits) > 1 and hits[1][0] >= 0.75 * best_score:
            passages.append(hits[1][1])

        answer = self._generate(message, passages) or "\n\n".join(f"**{p['title']}**\n{p['text']}" for p in passages)
        sources = [{"title": p["title"], "url": p["url"]} for p in passages]
        related = [{"title": d["title"], "url": d["url"]} for _, d in hits if d not in passages]
        return {"answer": answer, "sources": sources, "related": related}

    @staticmethod
    def _generate(question: str, passages: list):
        """Optional LLM answer grounded in retrieved passages. Returns None if not configured."""
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return None
        try:
            import anthropic  # type: ignore

            client = anthropic.Anthropic(api_key=key)
            context = "\n\n".join(f"[{p['title']}]\n{p['text']}" for p in passages)
            msg = client.messages.create(
                model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
                max_tokens=500,
                system=("You are the Kristu Jayanti University assistant. Answer ONLY from the context given. "
                        "If the answer is not in the context, say you don't have it and suggest calling 080-68737777. "
                        "Be concise and friendly."),
                messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
            )
            return msg.content[0].text
        except Exception:
            return None


if __name__ == "__main__":
    bot = Chatbot()
    while True:
        try:
            q = input("You: ")
        except EOFError:
            break
        print("Bot:", bot.answer(q)["answer"], "\n")