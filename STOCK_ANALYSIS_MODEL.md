# Aktienanalyse-Modell — Referenz für Claude

> **Zweck dieser Datei:** Spezifikation eines zweigleisigen Kennzahlen-Modells zur
> Bewertung von Aktien (Long-Term + Short-Term). Diese Datei dient Claude als
> verbindliche Logik-Vorlage. Wenn du (Claude) Aktien analysierst oder Scoring-Code
> schreibst, halte dich an die hier definierten Kennzahlen, Schwellen, Gewichte und
> Entscheidungsregeln. Nichts hier ist ein Autopilot — siehe Abschnitt „Grenzen".

---

## 0. Anleitung für Claude (How to use this file)

- **Zwei getrennte Scores, nie vermischen.** Berechne immer einen `long_term_score`
  (0–100) und einen `short_term_score` (0–100) separat. Gib beide aus, plus die
  Einzelkomponenten, damit nachvollziehbar bleibt, woher der Score kommt.
- **Transparenz vor Eleganz.** Bei jeder Bewertung die zugrunde liegenden Rohwerte
  (z. B. ROIC = 18,3 %), den daraus abgeleiteten Teilscore und das Gewicht
  mitliefern. Keine Black Box.
- **Fehlende Daten ehrlich behandeln.** Wenn eine Kennzahl fehlt, die Komponente
  nicht mit 0 bewerten (das verzerrt), sondern die Gewichte der vorhandenen
  Komponenten re-normalisieren und explizit ausweisen, welche Kennzahl fehlte.
- **Keine Short-Positionen empfehlen.** Das Modell ist long-only. Der Short-Term-Track
  identifiziert nur Long-Signale (siehe Begründung in Abschnitt 3).
- **Das Modell ist ein Filter, kein Urteil.** Qualitative Faktoren (Moat-Substanz,
  Management-Integrität, Disruptionsrisiko, Regulierung) erfasst es nicht. Weise
  am Ende jeder Analyse auf die offenen qualitativen Fragen hin.

---

## 1. Philosophie in einem Satz

Die Outperformance der besten Investoren der letzten 10–15 Jahre lässt sich
akademisch fast vollständig in wenige replizierbare Faktoren zerlegen — **Quality,
Value, niedriges Beta, Momentum** — plus Hebel und Disziplin. Dieses Modell baut
genau diese Faktoren nach, in einer für Privatanleger umsetzbaren, datensparsamen Form.

Konvergenz der Kennzahlen über die Top-Manager hinweg:

| Manager / Fonds | Stil | Kern-Kennzahlen, auf die es ankommt |
|---|---|---|
| Buffett/Munger (Berkshire) | Value/Quality | ROIC/ROE, Owner Earnings, Moat, niedrige Verschuldung |
| Terry Smith (Fundsmith) | Quality-Growth | ROCE >15–30 %, Bruttomarge hoch & stabil, Cash Conversion ≥95–100 %, FCF-Yield |
| Nick Sleep (Nomad) | Quality-Compounding | Skalenvorteile an Kunden weitergegeben, per-share value, sinkende Aktienzahl |
| Seth Klarman (Baupost) | Deep Value | Margin of Safety, Liquidations-/NPV-Wert, Cash halten wenn nichts billig ist |
| Asness (AQR) | Faktor-Quant | Quality-minus-Junk (Profitability, Growth, Safety, Payout), Value, Momentum |
| Druckenmiller | Macro | Liquidität/Zentralbanken, Regime, schnelle Verlustbegrenzung bei These-Bruch |

---

## 2. LONG-TERM-Track (Compounding / Quality-Value)

**Gewichtung der Blöcke:** Quality 45 % · Value 30 % · Safety 15 % · Momentum-Bestätigung 10 %

| Kennzahl | Misst | Gut / Exzellent | Schlecht (Red Flag) | Gewicht |
|---|---|---|---|---|
| **ROIC** (alt. ROCE) | Kapitaleffizienz / Moat | >15 % gut · >20–25 % exzellent (über ≥5–10 J) | <10 % | 15 % |
| **Bruttomarge** (Level + Stabilität) | Pricing Power | >40 % gut · >60 % exzellent | volatil / fallend | 10 % |
| **Cash Conversion** (FCF / Net Income) | Echtheit der Gewinne | ≥90 % gut · ≥100 % exzellent | <70 % | 10 % |
| **Operative Marge** (Trend) | Effizienz | stabil oder steigend | strukturell fallend | 10 % |
| **FCF-Yield** (FCF / EV) | Bewertung | >4–5 % attraktiv | <2 % (teuer) | 15 % |
| **Earnings Yield** (EBIT / EV) | Bewertung (Greenblatt) | oberes Quartil des Universums | unteres Quartil | 15 % |
| **Net Debt / EBITDA** | Bilanzrisiko | <1,5x gut · <1,0x exzellent | >3x | 8 % |
| **Zinsdeckung** (EBIT / Zinsaufwand) | Überlebensfähigkeit | >10x | <3x | 7 % |
| **12-1-Monat-Momentum** | Timing-Bestätigung | positiv = grünes Licht | stark negativ = warten | 10 % |

**Optionale Quality-Overlays (Bonus, kein Pflichtgewicht):**
- **Piotroski F-Score ≥ 7** (9 binäre Tests zu Profitabilität, Verschuldung, Effizienz) → Quality-Bestätigung.
- **Aktienzahl-Trend sinkend** (Buybacks ohne Verwässerung) → Sleep/Buffett-Signal.
- **Für Growth-/SaaS-Titel:** Rule of 40 (Umsatzwachstum % + FCF- oder EBITDA-Marge % ≥ 40) und Net Revenue Retention als zusätzliches Quality-Overlay.

**Hinweis zur Persistenz (wichtig für Gewichtung):** Profitabilität (ROIC, Marge)
ist die *persistenteste* Quality-Eigenschaft über 5–10 Jahre; Wachstum und Payout
sind am wenigsten persistent. Deshalb wird ROIC/Marge höher gewichtet als
kurzfristiges Wachstum.

---

## 3. SHORT-TERM-Track (Momentum / Revisions / Mean-Reversion)

**Gewichtung der Blöcke:** Momentum 40 % · Earnings Revisions 30 % · Technicals/Sentiment 20 % · Mean-Reversion-Overlay 10 %

| Kennzahl | Misst | Bullisches Signal | Gewicht |
|---|---|---|---|
| **12-1-Monat-Preismomentum** | Mittelfristiger Trend | Top-Dezil des Universums (nie shorten) | 25 % |
| **6-1- / 3-1-Monat-Momentum** | Schnellere Trends | positiv & beschleunigend | 15 % |
| **Earnings Revisions** (Analysten, 1–3 Mon.) | Cash-Flow-News | Aufwärtsrevisionen | 20 % |
| **Earnings Surprise / SUE** | Earnings Momentum | positive Überraschung | 10 % |
| **RSI (14 Tage)** | Overbought / Oversold | <30 = Reversal-Chance · >70 = Vorsicht | 10 % |
| **Preis vs. 50/200-Tage-MA** | Trend-Regime | über MA = Trend intakt | 10 % |
| **Short-Term-Reversal** (letzter Monat) | Mean Reversion | extremer 1-Monats-Verlierer *in einer Qualitätsfirma* | 10 % |

**Warum long-only:** Eine Studie zur 12-1-Momentum-Strategie auf den S&P 500
(2006–2024) zeigt eine Netto-Rendite von **−2,79 % p. a.** (Sharpe −0,23). Der
Long-Leg verdiente +7,9 %, aber der Short-Leg verlor in Momentum-Crashes (2009,
2020) katastrophal. **Konsequenz: Nur den Long-Leg nutzen.**

---

## 4. Entscheidungslogik

```
Kaufen (langfristig):
  long_term_score > 70
  UND FCF-Yield ODER Earnings-Yield im oberen Bereich
  UND keine Bilanz-Red-Flag (Net Debt/EBITDA < 3x, Zinsdeckung > 3x)
  → Momentum dient nur als Timing-Bestätigung, nicht als Veto

Trading (kurzfristig):
  short_term_score > 70
  → Positionsgröße begrenzen
  → keine Shorts
  → harte Verlustdisziplin: bei Bruch der These raus (Druckenmiller-Prinzip,
    kein mechanischer Stop, sondern Ausstieg bei Änderung der Annahmen)

Regime-Overlay (simpel, Macro):
  Bei invertierter Zinskurve / restriktiver Geldpolitik
  → Gewicht des Short-Term-Tracks reduzieren, Quality/Defensive hochfahren
```

**Gewichts-Anpassung nach Regime (optional, fortgeschritten):**
- Value-Spread historisch weit (oberes Perzentil) → Value-Block höher gewichten.
- „Quant-Winter" / Momentum-Crash-Umfeld → Quality/Defensive hochfahren.
- Faktor lässt über 24–36 Monate nach Implementierung deutlich nach → prüfen (Decay).

---

## 5. Datenquellen für die Implementierung

| Quelle | Stärke | Schwäche |
|---|---|---|
| **Financial Modeling Prep (FMP)** | Beste Fundamentaldaten-API (Income/Balance/Cashflow/DCF), für Fundamentalanalyse gebaut | US-Fokus, kostenpflichtig für Tiefe |
| **yfinance** | Kostenlos, schnell für Preishistorie & Basis-Fundamentals | Web-Scraping, nicht produktionsstabil, Lücken |
| **Alpha Vantage** | 50+ technische Indikatoren + Fundamentals, offizieller MCP-Server für Claude | Free-Tier limitiert (25 Requests/Tag, 5/Minute) |
| **EODHD / Marketstack** | Bessere EU-/Xetra-Abdeckung | Qualität variiert |

**Praxis-Setup:** Zwei Anbieter kombinieren — FMP (oder EODHD für EU) für
Fundamentals + yfinance/Alpha Vantage für Preise & technische Indikatoren.
Hinweis: IEX Cloud wurde am 31.08.2024 eingestellt — nicht mehr verwenden.

---

## 6. Umsetzungsreihenfolge

1. **Phase 1 (zuerst):** Long-Term-Track bauen. Robuster, datensparsamer
   (Quartalsdaten genügen), faktoriell am besten belegt. Kern: ROIC, Bruttomarge,
   Cash Conversion, FCF-Yield, Net Debt/EBITDA.
2. **Phase 2:** Short-Term-Track ergänzen (Momentum + Revisions), ausschließlich
   Long-Signale.
3. **Phase 3:** Validierung — Backtest mit survivorship-bias-freien Daten (delistete
   Firmen einbeziehen!), Transaktionskosten einrechnen (Short-Term-Turnover ~50 %/Monat).

---

## 7. Grenzen des Modells (vor jeder naiven Anwendung lesen)

- **Faktor-Decay ist real und quantifiziert.** McLean & Pontiff (2016): Renditen
  von Faktoren sind out-of-sample 26 % niedriger und nach Publikation 58 % niedriger.
  Faktoren verschwinden nicht, aber sie schrumpfen.
- **Survivorship-/Backfill-Bias.** „Best-Manager"-Listen sind um ~3–5 % p. a.
  überzeichnet. Backtests ohne delistete Firmen überschätzen Renditen massiv.
- **Retail-Replikation hat Grenzen.** Medallion (Kapazität, Kosten-Edge), Buffett
  (günstiger Insurance-Float-Hebel, AAA-Rating) und Druckenmiller (Liquiditäts-Timing)
  sind strukturell nicht kopierbar. Dieses Modell repliziert die *Faktoren*, nicht
  die *Hebel*.
- **Selbst Top-Prozesse haben lange Durststrecken.** Terry Smith hat den MSCI World
  2021–2025 fünf Jahre in Folge verfehlt (2025: +0,8 % vs. +12,8 %). Plane mehrjährige
  Underperformance ein. Erwartungsanker: Buffetts langfristiger Sharpe liegt bei ~0,79.
- **Skill vs. Luck statistisch schwer trennbar.** Bei 2 % Alpha p. a. braucht es
  ~36 Jahre Daten für 95 % Konfidenz, dass es kein Zufall ist. 10–15-Jahres-Track-Records
  sind statistisch oft nicht aussagekräftig.
- **Definitionen konsistent halten.** ROCE vs. ROIC, EBITDA- vs. FCF-Marge bei Rule
  of 40 — eine Definition wählen und durchhalten, sonst „Metric Shopping".
- **Mechanik schlägt nicht Urteilsvermögen.** Das Modell erfasst keine qualitativen
  Moats, kein Management, kein Disruptionsrisiko. Es ist ein Filter, der die
  Kandidatenliste verengt — die finale Entscheidung bleibt beim Menschen.

---

*Letzte inhaltliche Basis: Recherche-Querschnitt der Top-Investoren und der
akademischen Faktor-Literatur (u. a. AQR „Buffett's Alpha" 2018, „Quality Minus
Junk"; McLean & Pontiff 2016; Schwartz & Hanauer „Formula Investing" 2024).
Dies ist kein Anlageberatungsdokument.*
