#!/bin/bash

# Reit Auto Repair - Automated Test Suite
# Runs scenarios defined in test_scenarios.md (Comprehensive)

FLOW_ID="reit-hauptflow-v4"

# Navigate to project root (3 levels up from docs/reference/Reit)
cd "$(dirname "$0")/../../.."
CMD="bun scripts/flow/test-flow.ts"

echo "==================================================="
echo "Reit Auto Repair Flow - Comprehensive Verification"
echo "Based on Mermaid Diagram & Natural Interaction Goals"
echo "==================================================="
echo ""

# Function to run a test case
run_test() {
    NAME="$1"
    shift
    INPUTS=("$@")
    
    echo "---------------------------------------------------"
    echo "TEST: $NAME"
    echo "INPUTS: ${INPUTS[*]}"
    echo "---------------------------------------------------"
    
    $CMD $FLOW_ID --unique-user --inputs "${INPUTS[@]}"
    
    echo ""
    echo "Completed: $NAME"
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

echo "==================================================="
echo "All comprehensive tests completed."
echo "==================================================="
