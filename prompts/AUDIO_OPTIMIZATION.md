# Audio/TTS Optimization Guidelines

When designing flows for voice/phone interactions, prompts must be optimized for **spoken delivery**, not reading.

## Number Formatting

Always write numbers as words for natural speech:

```
BAD:  "von 8 bis 17 Uhr"
GOOD: "von acht bis siebzehn Uhr"

BAD:  "mindestens 14 Tagen Vorlauf"
GOOD: "mindestens vierzehn Tagen Vorlauf"

BAD:  "Drücken Sie die 1 für Ja"
GOOD: "Drücken Sie die Eins für Ja"
```

## Sentence Structure

- **Maximum 15 words** per sentence/clause
- Use natural pauses via commas and periods
- Avoid nested clauses
- Front-load important information

```
BAD:  "Um Ihnen optimal helfen zu können, würde ich gerne unser Gespräch
       aufzeichnen und Ihre Daten verarbeiten."

GOOD: "Ich möchte Ihnen optimal helfen. Dazu würde ich das Gespräch gerne
       aufzeichnen. Ist das für Sie in Ordnung?"
```

## AgenticLLM System Instructions Template

Add this to every AgenticLLM node's `systemInstructions`:

```
WICHTIG für Sprachausgabe:
- Kurze Sätze, maximal fünfzehn Wörter
- Zahlen als Worte: "acht Uhr" statt "8 Uhr"
- Natürliche Pausen durch Kommas
- Keine Abkürzungen verwenden
- Freundlich aber direkt antworten
```

## Avoid in Prompts

- Abbreviations (z.B. → zum Beispiel)
- Technical jargon
- Long lists without pauses
- Complex date formats (use "dreizehnter Januar" not "13.01.")
```
