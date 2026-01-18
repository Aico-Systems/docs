#!/bin/bash

# Reit Auto Repair - Automated Test Suite
# Runs scenarios defined in test_scenarios.md (Comprehensive)

FLOW_ID="reit-hauptflow-v4"

# Navigate to project root (3 levels up from docs/reference/Reit)
cd "$(dirname "$0")/../../.."
CMD="bun scripts/flow/test-flow.ts"

# Setup logging
SCRIPT_DIR="$(dirname "$0")"
LOG_FILE="$SCRIPT_DIR/test_results_$(date +%Y%m%d_%H%M%S).log"

echo "==================================================="
echo "Reit Auto Repair Flow - Comprehensive Verification"
echo "Based on Mermaid Diagram & Natural Interaction Goals"
echo "==================================================="
echo ""
echo "Log file: $LOG_FILE"
echo ""

# Redirect all output to both console and log file
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Test Suite Started: $(date)"
echo "Flow ID: $FLOW_ID"
echo ""

# Function to run a test case
run_test() {
    NAME="$1"
    shift
    INPUTS=("$@")

    echo "==========================================================="
    echo "TEST: $NAME"
    echo "INPUTS: ${INPUTS[*]}"
    echo "TIME: $(date +%H:%M:%S)"
    echo "==========================================================="

    START_TIME=$(date +%s)
    $CMD $FLOW_ID --unique-user --no-color --inputs "${INPUTS[@]}" --trace
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ PASSED: $NAME (${DURATION}s)"
    else
        echo "❌ FAILED: $NAME (Exit code: $EXIT_CODE, ${DURATION}s)"
    fi
    echo ""
    echo "-----------------------------------------------------------"
    echo ""
}

# 1. STATUS CHECKS

run_test "1A. Status Check (One-Shot - Happy Path)" \
    "Ja" "Status fuer EICP234, ich bin Nikita Friesen"

run_test "1B. Status Check (Iterative + Partial Smart Entry)" \
    "Ja" "Wann ist mein Auto fertig?" "EICP234" "Nikita"

run_test "1E. Status Check (Correction - Natural Interaction)" \
    "Ja" "Status fuer EICP234" "Ah ne, sorry, EICP235" "Nikita"

# 2. DAMAGE REPORTING

run_test "2A. Damage Report (Self-Fault)" \
    "Ja" "Ich hatte einen Unfall, bin leicht gegen pfeiler gefahren" \
    "Kratzer front, EICP234, Auto faehrt noch, ich bin schuld"

run_test "2B. Damage Report (Third-Party / Transfer)" \
    "Ja" "Jemand ist mir reingefahren" \
    "Delle in Tuer, EICP234, der andere ist schuld"

run_test "2C. Damage Report (Not Drivable)" \
    "Ja" "Auto springt nicht mehr an, Totalschaden"

# 3. APPOINTMENT

run_test "3A. Simple Booking" \
    "Ja" "Brauche Termin fuer Inspektion EICP234"

run_test "3B. Appointment (Implicit Context Switch)" \
    "Ja" "Status EICP234" "Eigentlich will ich doch einen Termin fuer Reparatur machen"

# 4. INVOICE

run_test "4A. Invoice Query" \
    "Ja" "Frage zur Rechnung" "RE-2024-001" "EICP234"

# 5. NATURAL INTERACTION & EDGE CASES

run_test "5A. Context Switching (Damage -> Status)" \
    "Ja" "Ich will einen Schaden melden" "Eigentlich will ich nur wissen wann mein anderes Auto fertig ist" \
    "EICP234" "Nikita"

run_test "5C. Slang / Dialect" \
    "Ja" "Meine Karre ist komplett im Eimer"

run_test "5D. Refusal / Privacy" \
    "Nein, auf keinen Fall"

# 6. SLOT FILLING VARIATIONS (Testing incremental data collection)

run_test "6A. Incremental Status - Name First" \
    "Ja" "Status" "Nikita Friesen" "EICP234"

run_test "6B. Incremental Status - Kennzeichen First" \
    "Ja" "Wann ist mein Auto fertig?" "EICP234" "Nikita Friesen"

run_test "6C. Incremental Status - Both Together" \
    "Ja" "Status" "Nikita Friesen, EICP234"

run_test "6D. Damage Report - All Info Upfront" \
    "Ja" "Schaden melden: Unfall, EICP234, Kratzer vorne links, Auto faehrt noch, ich war schuld, keine Versicherung"

run_test "6E. Damage Report - Step by Step" \
    "Ja" "Ich hatte einen Unfall" "EICP234" "Parkschaden" "Kratzer an der Tuer" "Ja, faehrt noch" "Jemand anderes war schuld" "Allianz" "SC-2024-123"

# 7. ROUTING & INTENT DETECTION

run_test "7A. Direct Intent - Termin" \
    "Ja" "Ich brauche einen Termin"

run_test "7B. Direct Intent - Rechnung" \
    "Ja" "Ich habe eine Frage zu meiner Rechnung"

run_test "7C. Direct Intent - Schaden" \
    "Ja" "Ich moechte einen Schaden melden"

run_test "7D. Ambiguous -> Clarification" \
    "Ja" "Ich habe ein Problem mit meinem Auto"

# 8. MEMORY & PERSISTENCE TESTS

run_test "8A. Status with Auto-Store Memory" \
    "Ja" "Status" "Max Mustermann" "M-AB 1234"

run_test "8B. Damage Confirmation Flow" \
    "Ja" "Schaden melden" "Unfall" "M-TEST-123" "Andere schuld" "Ich" "Nein" "M-TEST-456" "Max"

# 9. EDGE CASES & ERROR HANDLING

run_test "9A. Empty Response After Consent" \
    "Ja" ""

run_test "9B. Invalid Kennzeichen Format" \
    "Ja" "Status" "Nikita" "123ABC"

run_test "9C. Multiple Context Switches" \
    "Ja" "Status" "Nein, doch Termin" "Nein, eigentlich Schaden" "EICP234"

run_test "9D. Transfer After Not Found" \
    "Ja" "Status" "NOTFOUND123" "Nikita" "Ja"

run_test "9E. Decline Transfer" \
    "Ja" "Status" "NOTFOUND999" "Nikita" "Nein"

# 10. NATURAL LANGUAGE VARIATIONS

run_test "10A. Casual Language" \
    "Joa klar" "Wann kann ich meine Karre abholen?" "EICP234" "Nikita"

run_test "10B. Formal Language" \
    "Ja, einverstanden" "Ich moechte mich nach dem Status meines Fahrzeugs erkundigen" "EICP234" "Nikita Friesen"

run_test "10C. Mixed Information Order" \
    "Ja" "EICP234 Status von Nikita Friesen"

run_test "10D. Repetition & Clarification" \
    "Ja" "Status" "Nikita" "Wie bitte?" "Nikita Friesen" "EICP234"

# 11. COMPLETE FLOW SCENARIOS (End-to-End)

run_test "11A. Complete Status Flow - Found" \
    "Ja" "Wann ist mein Auto fertig?" "EICP234" "Nikita Friesen"

run_test "11B. Complete Status Flow - Not Found -> Transfer" \
    "Ja" "Status" "NOTEXIST123" "Max Mustermann" "Ja, bitte weiterleiten"

run_test "11C. Complete Damage Self-Fault Flow" \
    "Ja" "Ich hatte einen Unfall" "Kratzer an der Tuer" "EICP234" "Ich war schuld" \
    "Kratzer links" "Ja faehrt noch" "Allianz"

run_test "11D. Third-Party Damage -> Transfer" \
    "Ja" "Schaden melden" "Parkschaden" "M-TW 4567" "Der andere war schuld"

run_test "11E. Invoice Complete Flow" \
    "Ja" "Frage zur Rechnung" "RE-2024-001"

# 12. SLOT ACCUMULATION TESTS

run_test "12A. Status - Accumulate Slots Correctly" \
    "Ja" "Status bitte" "Nikita" "EICP234"

run_test "12B. Status - All Info Together" \
    "Ja" "Status fuer Nikita Friesen mit Kennzeichen EICP234"

run_test "12C. Damage - Partial Then Complete" \
    "Ja" "Unfall gehabt" "Kratzer" "EICP234"

# 13. EDGE CASES

run_test "13A. User Declines Transfer" \
    "Ja" "Status" "NOTFOUND999" "Test User" "Nein danke"

run_test "13B. User Wants Different Intent" \
    "Ja" "Status" "NOTFOUND999" "Test User" "Nein" "Eigentlich will ich einen Termin"

run_test "13C. Very Short Responses" \
    "Ja" "Status" "ABC123" "Max"

echo "==========================================================="
echo "Test Suite Completed: $(date)"
echo "==========================================================="
echo ""
echo "All comprehensive tests completed."
echo "Results saved to: $LOG_FILE"
echo ""
