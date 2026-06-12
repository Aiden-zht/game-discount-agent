#!/usr/bin/env bash
# Unified pipeline for WeChat articles
# Usage: ./pipeline.sh <step> [options]
# Steps: scrape, build, validate, publish, kpi, run

set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${PIPELINE_DIR}/output"
mkdir -p "$OUTPUT_DIR"

usage() {
    echo "Usage: $0 <step> [options]"
    echo ""
    echo "Steps:"
    echo "  scrape   - Download images, upload to CDN, generate HTML"
    echo "  build    - Build article HTML (from state)"
    echo "  validate - LLM validation (AppID, images, HTML)"
    echo "  publish  - Create WeChat draft"
    echo "  kpi      - Calculate KPI scores"
    echo "  run      - Full pipeline (scrape -> validate -> publish -> kpi)"
    echo ""
    echo "Options:"
    echo "  --type discount|thematic"
    echo "  --appids APPID [APPID...]"
    echo "  --images PATH"
    echo "  --state STATE_FILE"
    echo "  --retry   - Retry fix if BLOCKING found"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

STEP="$1"
shift

# Parse arguments
TYPE="discount"
APPIDS=""
IMAGES_DIR=""
STATE_FILE=""
RETRY=""
NO_PUBLISH=""

while [ $# -gt 0 ]; do
    case "$1" in
        --type) TYPE="$2"; shift 2 ;;
        --appids) APPIDS="$2"; shift 2 ;;
        --images) IMAGES_DIR="$2"; shift 2 ;;
        --state) STATE_FILE="$2"; shift 2 ;;
        --retry) RETRY="--retry"; shift ;;
        --no-publish) NO_PUBLISH="--no-publish"; shift ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

if [ -z "$STATE_FILE" ]; then
    STATE_FILE="${OUTPUT_DIR}/state.json"
fi

echo "=== WeChat Article Pipeline ==="
echo "Step: $STEP"
echo "Type: $TYPE"
echo "State: $STATE_FILE"
echo ""

case "$STEP" in
    scrape)
        echo "Step 1/4: Scrape & Upload"
        if [ "$TYPE" = "thematic" ]; then
            python3 "${PIPELINE_DIR}/terraria_scrape.py" "$APPIDS" "$IMAGES_DIR" "$STATE_FILE"
        else
            python3 "${PIPELINE_DIR}/cron_digest.py"
        fi
        ;;
        
    build)
        echo "Step 1.5/4: Build Article HTML"
        python3 "${PIPELINE_DIR}/terraria_build.py" "$STATE_FILE"
        ;;
        
    validate)
        echo "Step 2/4: Validate (LLM check)"
        VAL_FILE="${OUTPUT_DIR}/validation.json"
        python3 "${PIPELINE_DIR}/terraria_validate.py" "$STATE_FILE" "$VAL_FILE" "$TYPE"
        ;;
        
    publish)
        echo "Step 3/4: Publish to WeChat"
        python3 "${PIPELINE_DIR}/terraria_publish.py" "$STATE_FILE" $RETRY
        ;;
        
    kpi)
        echo "Step 4/4: Compute KPI"
        python3 "${PIPELINE_DIR}/terraria_kpi.py" "$STATE_FILE" "${OUTPUT_DIR}/validation.json"
        ;;
        
    run)
        echo "Full pipeline: scrape -> validate -> publish -> kpi"
        
        # Scrape
        echo ""
        echo "=== Step 1/4: Scrape & Upload ==="
        if [ "$TYPE" = "thematic" ]; then
            python3 "${PIPELINE_DIR}/terraria_scrape.py" "$APPIDS" "$IMAGES_DIR" "$STATE_FILE"
        else
            python3 "${PIPELINE_DIR}/cron_digest.py"
        fi
        
        # Validate
        echo ""
        echo "=== Step 2/4: Validate ==="
        VAL_FILE="${OUTPUT_DIR}/validation.json"
        python3 "${PIPELINE_DIR}/terraria_validate.py" "$STATE_FILE" "$VAL_FILE" "$TYPE"
        
        if [ -n "$NO_PUBLISH" ]; then
            echo "Skipping publish (--no-publish flag)"
            exit 0
        fi
        
        # Publish
        echo ""
        echo "=== Step 3/4: Publish ==="
        python3 "${PIPELINE_DIR}/terraria_publish.py" "$STATE_FILE" $RETRY
        
        # KPI
        echo ""
        echo "=== Step 4/4: KPI ==="
        python3 "${PIPELINE_DIR}/terraria_kpi.py" "$STATE_FILE" "$VAL_FILE"
        
        echo ""
        echo "=== Pipeline Complete ==="
        ;;
        
    *)
        echo "Unknown step: $STEP"
        usage
        ;;
esac

echo ""
echo "Done. State file: $STATE_FILE"
