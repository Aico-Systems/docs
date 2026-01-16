# Reit Hauptflow v5 - Comprehensive Design Plan

> **Status**: Planning
> **Based on**: flow.mermaid business requirements
> **Previous version issues**: v4 missing confirmations, broken terminvereinbarung, no intent change handling

## Executive Summary

The current flow (v4) has critical UX issues:
1. No confirmation before booking/transfers
2. Terminvereinbarung doesn't verify damage report exists
3. Users can't change their mind mid-flow
4. Tool failures silently transfer to Mitarbeiter without explanation

This document defines the correct flow behavior with conversation examples.

---

## Core Design Principles

### 1. Always Confirm Before Actions
Every significant action (booking, transfer, ending call) must be confirmed:
```
Bot: "Soll ich Sie mit einem Mitarbeiter verbinden?"
User: "Ja" → Transfer
User: "Nein" / "Ich möchte doch..." → Return to smart_entry
```

### 2. Allow Intent Changes
Users should be able to change their mind at any point:
```
Bot: "Für den Reparaturtermin brauche ich Ihr Kennzeichen."
User: "Eigentlich wollte ich erst einen Schaden melden"
Bot: "Kein Problem! Was für ein Schaden ist es?"
```

### 3. Explain Prerequisites
When a path requires prerequisites, explain them:
```
User: "Ich brauche einen Reparaturtermin"
Bot: "Für einen Reparaturtermin muss der Schaden bereits aufgenommen sein. 
      Soll ich nachschauen ob für Ihr Fahrzeug ein Schaden hinterlegt ist?"
```

### 4. Graceful Degradation
When automated actions fail, explain and offer alternatives:
```
Bot: "Leider konnte ich den Termin nicht automatisch buchen. 
      Soll ich Sie mit einem Kollegen verbinden, der das für Sie erledigt?"
```

---

## Flow Architecture

```
                         ┌─────────────────┐
                         │     START       │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │  consent_check  │ (NEVER skip from memory)
                         └────────┬────────┘
                             ja/  \nein
                               /    \
                 ┌────────────▼┐    ┌▼─────────────────┐
                 │ smart_entry │    │ confirm_mailbox  │
                 │ (AgenticLLM)│    │ "Kein Problem,   │
                 │             │    │  verbinde mit    │
                 │ ALWAYS      │    │  Mailbox. OK?"   │
                 │ returns     │    └────────┬─────────┘
                 │ here on     │         ja/ \nein
                 │ intent      │           /   \
                 │ change      │    mailbox   smart_entry
                 └──────┬──────┘
                        │
      ┌─────────────────┼─────────────────┬─────────────────┬──────────────┐
      │                 │                 │                 │              │
┌─────▼─────┐    ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐ ┌─────▼─────┐
│ SCHADEN   │    │   STATUS    │   │   TERMIN    │   │  RECHNUNG   │ │ SONSTIGES │
│ (damage)  │    │   (query)   │   │ (appoint.)  │   │  (invoice)  │ │  (other)  │
└─────┬─────┘    └──────┬──────┘   └──────┬──────┘   └──────┬──────┘ └─────┬─────┘
      │                 │                 │                 │              │
      ▼                 ▼                 ▼                 ▼              ▼
  [subflow]        [subflow]         [subflow]        [subflow]      [confirm
                                                                      transfer]
```

---

## Branch 1: Schadensmeldung (Damage Report)

### Business Requirements (from flow.mermaid)
1. Schadensart erfragen
2. Fahrzeug: Hersteller, Modell, Kennzeichen
3. Schuldfrage → bei "andere schuld" → Transfer zu Mitarbeiter
4. Verkehrssicherheit (Spiegel, Scheinwerfer, Reifen kaputt?)
5. Versicherung + bereits gemeldet? + Schadennummer?
6. Terminierung für Besichtigung (Mo-Fr 8-17, Sa 8-11, Folgetag)
7. **Bestätigung vor Buchung**
8. Terminbestätigung per SMS/Email

### Conversation Flow

#### Happy Path (Self-Fault)
```
Bot: "Super! Was kann ich für Sie tun?"
User: "Ich hatte einen Unfall"

Bot: "Das tut mir leid. Was für ein Schaden ist es - ein Unfall, Parkschaden, 
      Hagelschaden oder Vandalismus?"
User: "Ein Parkschaden"

Bot: "Wie lautet Ihr Kennzeichen?"
User: "M-AB 1234"

Bot: "Waren Sie selbst schuld am Schaden, oder war jemand anderes beteiligt?"
User: "Ich war selbst schuld"

Bot: "Ist Ihr Fahrzeug noch verkehrssicher? Funktionieren Spiegel, 
      Scheinwerfer und Reifen noch?"
User: "Ja, nur ein Kratzer am Kotflügel"

Bot: "Bei welcher Versicherung sind Sie?"
User: "Allianz"

Bot: "Haben Sie den Schaden schon bei der Versicherung gemeldet?"
User: "Nein, noch nicht"

Bot: "Alles klar. Ich habe notiert: Parkschaden am Fahrzeug M-AB 1234, 
      Kratzer am Kotflügel, verkehrssicher, Allianz-versichert.
      
      Für die Besichtigung hätte ich folgende Termine:
      - Morgen, Dienstag, zwischen 8 und 12 Uhr
      - Mittwoch zwischen 8 und 17 Uhr
      
      Welcher Termin passt Ihnen?"
User: "Morgen vormittag wäre gut"

Bot: "Perfekt! Ich buche Dienstag zwischen 8 und 12 Uhr für Sie.
      Sie bekommen eine SMS-Bestätigung. 
      Bitte bringen Sie Fahrzeugpapiere und Versicherungskarte mit.
      
      Kann ich sonst noch etwas für Sie tun?"
User: "Nein, das war's"

Bot: "Vielen Dank für Ihren Anruf. Auf Wiederhören!"
```

#### Other Party at Fault
```
Bot: "Waren Sie selbst schuld am Schaden, oder war jemand anderes beteiligt?"
User: "Der andere Fahrer ist aufgefahren"

Bot: "Bei Fremdverschulden muss das ein Kollege bearbeiten, da es rechtlich 
      komplexer ist. Soll ich Sie verbinden?"
User: "Ja bitte"

Bot: "Ich verbinde Sie jetzt. Ich habe meinem Kollegen bereits mitgeteilt: 
      Auffahrunfall, Kennzeichen M-AB 1234, Fremdverschulden. Einen Moment..."
[Transfer]
```

#### Intent Change Mid-Flow
```
Bot: "Bei welcher Versicherung sind Sie?"
User: "Moment, ich wollte eigentlich nur wissen wie weit mein anderes Auto ist"

Bot: "Kein Problem! Für die Statusabfrage brauche ich das Kennzeichen 
      des anderen Fahrzeugs."
User: "M-XY 5678"
[Continues with status query]
```

#### User Rejects Booking
```
Bot: "Ich buche Dienstag zwischen 8 und 12 Uhr für Sie. Ist das in Ordnung?"
User: "Nein, ich muss erst mit meiner Frau sprechen"

Bot: "Kein Problem! Sie können jederzeit wieder anrufen um einen Termin 
      zu vereinbaren. Ihre Schadensmeldung ist bereits angelegt.
      Kann ich sonst noch etwas für Sie tun?"
```

### Node Structure
```
smart_entry (schadensmeldung intent)
    ↓
check_all_damage_data (condition: schadensart && kennzeichen && schuldfrage && versicherung)
    ↓ true                          ↓ false
confirm_and_book              elicit_damage_step_by_step
    ↓
elicit_schadensart_kennzeichen (slot_filling, can extract schuldfrage/versicherung too)
    ↓
check_schuldfrage_present (condition)
    ↓ true                          ↓ false
[continue]                    elicit_schuldfrage (intent_classification)
                                   ↓ selbst_schuld        ↓ andere_schuld
                              [continue]            confirm_transfer_fremd
                                                        ↓ ja          ↓ nein
                                                    transfer      smart_entry
    ↓
elicit_verkehrssicherheit (if not already captured)
    ↓
elicit_versicherung (slot_filling: versicherung, bereits_gemeldet, schadennummer)
    ↓
create_damage_report (tool)
    ↓ success                       ↓ error
offer_appointment               confirm_transfer_error
    ↓
elicit_termin_preference (slot_filling: date preference)
    ↓
book_besichtigung (tool)
    ↓ success                       ↓ error
confirm_booking                 confirm_transfer_error
    ↓
ask_anything_else (agenticLLM)
    ↓ respond (self-loop)           ↓ done
smart_entry                     end_success
```

---

## Branch 2: Statusabfrage (Status Query)

### Business Requirements
1. Kennzeichen + Name zur Identifikation
2. Fahrzeugstatus anzeigen (Kalkulation, KoVo, KaRo, Lackierer, Finish, etc.)
3. Fertigstellungsdatum (aus Auftragsdaten, nicht schätzen!)
4. Teileverfügbarkeit
5. Bei fehlenden Teilen → Transfer zu Mitarbeiter anbieten
6. Bei Hol-/Bringservice → Lieferzeit abfragen (3h Korridor)

### Conversation Flow

#### Happy Path
```
Bot: "Super! Was kann ich für Sie tun?"
User: "Wie weit ist mein Auto?"

Bot: "Für die Statusabfrage brauche ich Ihr Kennzeichen und Ihren Namen."
User: "M-AB 1234, Müller"

Bot: "Einen Moment, ich schaue nach...

      Ihr Fahrzeug befindet sich aktuell in der Lackierkabine.
      Voraussichtliche Fertigstellung: Freitag, 24. Januar.
      Alle Teile sind verfügbar.
      
      Möchten Sie das Fahrzeug selbst abholen oder sollen wir es liefern?"
User: "Liefern bitte"

Bot: "Wann soll die Lieferung erfolgen? 
      Am Freitag können wir zwischen 14 und 17 Uhr oder zwischen 17 und 20 Uhr liefern."
User: "Zwischen 17 und 20 Uhr"

Bot: "Perfekt! Ich habe die Lieferung für Freitag zwischen 17 und 20 Uhr notiert.
      Ist die Adresse [gespeicherte Adresse] noch korrekt?"
User: "Ja"

Bot: "Alles klar! Sie bekommen eine SMS wenn das Fahrzeug unterwegs ist.
      Kann ich sonst noch etwas für Sie tun?"
```

#### Parts Missing
```
Bot: "Ihr Fahrzeug ist aktuell in der Kalkulation. 
      Leider warten wir noch auf ein Ersatzteil - der Spiegel ist noch nicht geliefert.
      
      Die genaue Lieferzeit kann mein Kollege besser einschätzen.
      Soll ich Sie verbinden?"
User: "Ja bitte"

Bot: "Ich verbinde Sie jetzt. Mein Kollege weiß bereits Bescheid. Einen Moment..."
```

#### Vehicle Not Found
```
Bot: "Leider konnte ich kein Fahrzeug mit dem Kennzeichen M-AB 1234 finden.
      
      Haben Sie vielleicht einen anderen Auftrag bei uns? 
      Oder soll ich Sie mit einem Kollegen verbinden?"
User: "Verbinden Sie mich bitte"
```

### Node Structure
```
smart_entry (statusabfrage intent)
    ↓
elicit_status_identification (slot_filling: kennzeichen, name)
    ↓
lookup_vehicle_status (tool)
    ↓ success                           ↓ error / not_found
handle_status_result                confirm_transfer_not_found
(agenticLLM)
    ↓
[based on status:]
- parts_missing → confirm_transfer_parts
- ready_soon → offer_delivery_or_pickup
- in_progress → inform_and_ask_more

offer_delivery_or_pickup
    ↓ delivery                          ↓ pickup
elicit_delivery_time                end_with_pickup_info
    ↓
confirm_delivery
    ↓
ask_anything_else
```

---

## Branch 3: Terminvereinbarung (Repair Appointment)

### Business Requirements
1. **Voraussetzung**: Schaden muss bereits aufgenommen und bewertet sein
2. Nur für verkehrssichere Fahrzeuge
3. Termine: Montag oder Dienstag vormittags, 14 Tage Vorlauf
4. Sync mit PlanSO
5. **Bestätigung vor Buchung**

### Conversation Flow

#### Happy Path (Damage Report Exists)
```
Bot: "Super! Was kann ich für Sie tun?"
User: "Ich möchte einen Reparaturtermin vereinbaren"

Bot: "Gerne! Wie lautet Ihr Kennzeichen?"
User: "M-AB 1234"

Bot: "Einen Moment, ich schaue nach...
      
      Ich sehe Ihren Schaden vom 15. Januar - Parkschaden am Kotflügel.
      
      Für die Reparatur hätte ich folgende Termine:
      - Montag, 27. Januar, vormittags
      - Dienstag, 28. Januar, vormittags
      
      Welcher Tag passt Ihnen besser?"
User: "Montag"

Bot: "Perfekt! Ich buche Montag, den 27. Januar vormittags für Sie.
      Bitte bringen Sie das Fahrzeug zwischen 7:30 und 8:00 Uhr.
      Sie bekommen eine SMS-Bestätigung.
      
      Kann ich sonst noch etwas für Sie tun?"
```

#### No Damage Report Found
```
Bot: "Einen Moment, ich schaue nach...
      
      Für das Kennzeichen M-AB 1234 habe ich leider keinen Schaden hinterlegt.
      
      Für einen Reparaturtermin muss der Schaden erst aufgenommen werden.
      Soll ich das jetzt mit Ihnen machen?"
User: "Ja"

Bot: "Alles klar! Was für ein Schaden ist es?"
[Continues with Schadensmeldung flow]
```

#### Not Roadworthy
```
Bot: "Ich sehe Ihren Schaden - allerdings wurde das Fahrzeug als nicht 
      verkehrssicher eingestuft (Scheinwerfer defekt).
      
      In diesem Fall muss das Fahrzeug abgeschleppt werden.
      Soll ich Sie mit einem Kollegen verbinden, der das organisiert?"
```

### Node Structure
```
smart_entry (terminvereinbarung intent)
    ↓
elicit_termin_kennzeichen (slot_filling)
    ↓
lookup_damage_report (tool)
    ↓ found                             ↓ not_found
check_roadworthy                   offer_create_damage_report
    ↓ yes              ↓ no               ↓ yes           ↓ no
offer_slots     confirm_tow        [schadensmeldung]  ask_anything_else
    ↓
elicit_slot_preference
    ↓
confirm_booking
    ↓ yes                               ↓ no
book_reparatur                     ask_anything_else
    ↓ success          ↓ error
send_confirmation  confirm_transfer_error
    ↓
ask_anything_else
```

---

## Branch 4: Rechnung (Invoice Questions)

### Business Requirements
1. Kennzeichen ODER Rechnungsnummer erfragen
2. Weiterleitung an Buchhaltung

### Conversation Flow
```
Bot: "Super! Was kann ich für Sie tun?"
User: "Ich habe eine Frage zu meiner Rechnung"

Bot: "Für Rechnungsfragen verbinde ich Sie mit der Buchhaltung.
      Haben Sie die Rechnungsnummer oder das Kennzeichen zur Hand?"
User: "Rechnungsnummer 2024-12345"

Bot: "Danke! Ich verbinde Sie jetzt mit der Buchhaltung.
      Ich habe die Rechnungsnummer bereits weitergegeben. Einen Moment..."
[Transfer]
```

### Node Structure
```
smart_entry (rechnung intent)
    ↓
elicit_rechnung_id (slot_filling: kennzeichen OR rechnungsnummer, at least one required)
    ↓
confirm_transfer_buchhaltung
    ↓ yes                               ↓ no
transfer_buchhaltung               ask_anything_else
```

---

## Branch 5: Sonstiges (Other)

### Conversation Flow
```
Bot: "Super! Was kann ich für Sie tun?"
User: "Ich möchte mit dem Geschäftsführer sprechen"

Bot: "Das kann ich leider nicht direkt vermitteln.
      Soll ich Sie mit einem Kollegen verbinden, der Ihnen weiterhelfen kann?"
User: "Ja"

Bot: "Ich verbinde Sie jetzt. Einen Moment..."
```

---

## Global: Intent Change Handling

The `smart_entry` node must detect intent changes and route accordingly.

### Detection Patterns
```
- "eigentlich wollte ich..." → intent change
- "nein, ich meinte..." → intent change  
- "Moment, ich brauche..." → intent change
- "können wir stattdessen..." → intent change
- "vergiss das, ich möchte..." → intent change
```

### AgenticLLM System Instructions
```
Du bist Marie von der Lackiererei Reit.

AKTIONEN:
- schadensmeldung: Neuer Schaden melden
- statusabfrage: Fahrzeugstatus abfragen
- terminvereinbarung: Reparaturtermin vereinbaren
- rechnung: Rechnungsfragen
- sonstiges: Alles andere
- respond: Mehr Details erfragen oder Frage beantworten
- back_to_menu: Nutzer möchte etwas anderes (Intent-Wechsel erkannt)

INTENT-WECHSEL ERKENNEN:
Wenn der Nutzer mitten im Gespräch sein Anliegen ändert:
- "eigentlich wollte ich..." 
- "nein, ich meinte..."
- "können wir stattdessen..."
- "vergiss das"
Dann wähle "back_to_menu" und frage was er stattdessen möchte.

BEISPIEL:
User: "Moment, ich wollte eigentlich nur den Status wissen"
→ Action: back_to_menu
→ Response: "Kein Problem! Für die Statusabfrage brauche ich Ihr Kennzeichen."
```

---

## Global: Confirmation Before Actions

Every transfer and booking must be confirmed.

### Confirmation Node Template
```json
{
  "id": "confirm_transfer_X",
  "type": "elicitation",
  "data": {
    "prompt": "Soll ich Sie mit [X] verbinden?",
    "validationMode": "intent_classification",
    "expectedIntents": ["ja", "nein"],
    "outputVariable": "transfer_confirmed"
  }
}
```

### Edges
```
confirm_transfer_X
    ↓ ja                    ↓ nein
transfer_X              ask_anything_else (or back to smart_entry)
```

---

## Global: "Anything Else?" Pattern

After completing any action, always ask if there's anything else.

### Node Template
```json
{
  "id": "ask_anything_else",
  "type": "agenticLLM",
  "data": {
    "prompt": "Kann ich sonst noch etwas für Sie tun?",
    "systemInstructions": "Frage ob der Kunde noch etwas braucht.\n\nAKTIONEN:\n- schadensmeldung/statusabfrage/etc: Neues Anliegen erkannt\n- done: Kunde ist fertig ('Nein danke', 'Das war alles', etc.)\n- respond: Rückfrage oder Unklarheit"
  }
}
```

### Edges
```
ask_anything_else
    ↓ done                  ↓ [any intent]
end_success             smart_entry (with new intent)
```

---

## Error Handling

### Tool Errors
```
Bot: "Leider konnte ich [Aktion] nicht automatisch durchführen.
      Soll ich Sie mit einem Kollegen verbinden, der das für Sie erledigt?"
```

### Unexpected Input
```
Bot: "Das habe ich nicht verstanden. 
      Können Sie das bitte anders formulieren?"
```

### Timeout
```
Bot: "Sind Sie noch da? 
      [Nach 10s ohne Antwort]
      Falls Sie noch Fragen haben, rufen Sie gerne wieder an. Auf Wiederhören!"
```

---

## Test Scenarios

### 1. Happy Paths
```bash
# Schadensmeldung selbst schuld
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Ich hatte einen Parkschaden" \
  "M-AB 1234" \
  "Selbst schuld" \
  "Ja, alles funktioniert noch" \
  "Allianz" \
  "Nein, noch nicht gemeldet" \
  "Morgen vormittag" \
  "Ja" \
  "Nein danke"

# Statusabfrage
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Wie weit ist mein Auto?" \
  "M-AB 1234, Müller" \
  "Abholen" \
  "Nein danke"

# Terminvereinbarung
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Ich brauche einen Reparaturtermin" \
  "M-AB 1234" \
  "Montag" \
  "Ja" \
  "Nein danke"
```

### 2. Transfer Paths
```bash
# Fremdverschulden
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Ich hatte einen Unfall" \
  "M-XY 5678" \
  "Der andere war schuld" \
  "Ja"  # Confirm transfer

# Rechnung
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Frage zur Rechnung" \
  "2024-12345" \
  "Ja"  # Confirm transfer
```

### 3. Edge Cases
```bash
# Intent change mid-flow
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Ich brauche einen Termin" \
  "Moment, eigentlich wollte ich den Status wissen" \
  "M-AB 1234, Müller"

# Reject confirmation
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Schaden melden" \
  "Parkschaden, M-AB 1234, selbst schuld, Allianz" \
  "Nein, ich möchte keinen Termin" \
  "Nein danke"

# No damage report for Termin
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Reparaturtermin bitte" \
  "M-XX 9999" \
  "Ja, Schaden aufnehmen" \
  [continues with Schadensmeldung]

# User asks capabilities
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Was kannst du alles?" \
  "Ich möchte den Status wissen" \
  "M-AB 1234, Müller"
```

### 4. Rejection Paths
```bash
# Reject consent
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Nein" \
  "Ja"  # Confirm mailbox transfer

# Reject transfer, continue differently
bun test-flow.ts reit-hauptflow-v5 --inputs \
  "Ja" \
  "Unfall, M-AB 1234, der andere war schuld" \
  "Nein, nicht verbinden" \
  "Ich möchte lieber den Status eines anderen Autos wissen" \
  "M-XY 5678, Schmidt"
```

---

## Node Count Estimate

| Component | Nodes |
|-----------|-------|
| Entry (start, consent, smart_entry) | 3 |
| Schadensmeldung path | 12 |
| Statusabfrage path | 8 |
| Terminvereinbarung path | 10 |
| Rechnung path | 3 |
| Sonstiges path | 2 |
| Shared (ask_anything_else, confirmations) | 6 |
| End nodes | 3 |
| **Total** | **~47** |

This is similar to the original v3 flow but with proper structure and confirmations.

---

## Implementation Priority

### Phase 1: Core Fixes
1. Add confirmation nodes before all transfers
2. Fix rechnung slot validation
3. Add `ask_anything_else` after all completed actions

### Phase 2: Terminvereinbarung Redesign
1. Add damage report lookup
2. Add prerequisite check and offer to create
3. Add roadworthiness check
4. Add slot offering with real dates

### Phase 3: Intent Change Handling
1. Add `back_to_menu` action to smart_entry
2. Update system instructions for intent detection
3. Add edges from all waiting nodes back to smart_entry

### Phase 4: Status Query Enhancement
1. Add parts availability check
2. Add delivery/pickup flow
3. Add time slot selection for delivery

---

## Success Criteria

All test scenarios in `test-reit-scenarios.ts` must pass:
- [ ] consent_rejected
- [ ] consent_accepted
- [ ] schadensmeldung_selbst_schuld_complete
- [ ] schadensmeldung_fremdverschulden
- [ ] schadensmeldung_fast_path
- [ ] schadensmeldung_intent_change
- [ ] statusabfrage_complete
- [ ] statusabfrage_parts_missing
- [ ] terminvereinbarung_complete
- [ ] terminvereinbarung_no_damage_report
- [ ] terminvereinbarung_not_roadworthy
- [ ] rechnung_transfer
- [ ] sonstiges_transfer
- [ ] intent_change_midflow
- [ ] user_asks_capabilities
- [ ] reject_all_confirmations
