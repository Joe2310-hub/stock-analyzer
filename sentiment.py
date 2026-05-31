import os
import json
import anthropic


def analyze_news_sentiment(news: list, ticker: str) -> dict:
    """
    Analysiert die Stimmung der News-Headlines mit Claude Haiku.
    Gibt pro Headline ein Sentiment + einen Gesamtscore zurück.
    """
    if not news or not os.getenv("ANTHROPIC_API_KEY"):
        return {"items": [], "overall_score": None, "overall_label": None, "zusammenfassung": None}

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    headlines_text = "\n".join(
        f"{i+1}. {n['title']}" + (f" ({n['publisher']})" if n.get("publisher") else "")
        for i, n in enumerate(news)
    )

    prompt = f"""Du bist ein Finanzanalyst. Bewerte die Stimmung dieser Börsennachrichten für {ticker}.

Nachrichten:
{headlines_text}

Regeln:
- Bewerte jede Nachricht aus Sicht eines Aktionärs: Ist das gut, schlecht oder neutral für den Kurs?
- Achte auf Finanzkontext: "Gewinn verfehlt" = negativ, "Aktienrückkauf" = positiv, "Klage eingereicht" = negativ
- Sei präzise, keine Floskeln

Antworte NUR mit validem JSON, kein Text davor oder danach:
{{
  "items": [
    {{
      "id": 1,
      "sentiment": "positiv",
      "score": 0.7,
      "grund": "Kurze Begründung (max. 8 Wörter)"
    }}
  ],
  "overall_score": 0.4,
  "overall_label": "leicht positiv",
  "zusammenfassung": "Ein Satz zur Gesamtstimmung der Nachrichten."
}}

Sentiment-Werte: "positiv", "neutral", "negativ"
Score pro Headline: -1.0 (sehr negativ) bis +1.0 (sehr positiv)
overall_score: gewichteter Durchschnitt aller Headlines
overall_label: "sehr positiv" / "positiv" / "leicht positiv" / "neutral" / "leicht negativ" / "negativ" / "sehr negativ"
"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        return result
    except Exception:
        return {"items": [], "overall_score": None, "overall_label": None, "zusammenfassung": None}
