import json
from pathlib import Path
from sqlalchemy import select
from app.models import Word
from app.db import SessionLocal


async def seed_words():
    datasets = [
        (Path("data/irregular_verbs.json"), "irregular_verbs"),
        (Path("data/food_vocabulary.json"), "food"),
    ]
    async with SessionLocal() as session:
        existing = {w.infinitive for w in (await session.execute(select(Word))).scalars().all()}
        for path, category in datasets:
            if not path.exists():
                continue
            words = json.loads(path.read_text(encoding="utf-8"))
            for item in words:
                if item["infinitive"] not in existing:
                    item = {**item, "category": category}
                    session.add(Word(**item))
                    existing.add(item["infinitive"])
        await session.commit()
