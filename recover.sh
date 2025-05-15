#!/bin/bash
# MP4 Recovery Toolkit - Shell Script (with Docker integration)
# Builds Docker image, and repairs, analyzes, or batch processes MP4 files.
# Author: Your Name
# License: MIT

# --- Configuration ---
DOCKER_IMAGE_NAME="mp4-recovery-toolkit"
DOCKER_IMAGE_TAG="latest"
FULL_IMAGE_NAME="${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"
# --- End Configuration ---

# Terminal colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check for Docker early
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker is not installed or not in PATH.${NC}"
    echo "Please install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

# Main command dispatcher
MAIN_COMMAND="$1"

case "$MAIN_COMMAND" in
    "setup")
        shift
        setup_docker
        ;;
    "repair")
        shift
        handle_repair_command "$@"
        ;;
    "info")
        shift
        handle_info_command "$@"
        ;;
    "batch")
        shift
        handle_batch_command "$@"
        ;;
    "list")
        shift
        list_techniques_docker
        ;;
    "--help"|"-h"|"")
        show_main_help
        ;;
    *)
        echo -e "${RED}ERROR: Unknown main command \"$MAIN_COMMAND\".${NC}"
        show_main_help
        exit 1
        ;;
esac

# ============================================================================
# Docker Setup
# ============================================================================
setup_docker() {
    echo
    echo -e "${BLUE}===== DOCKER IMAGE SETUP =====${NC}"
    echo "Building Docker image: $FULL_IMAGE_NAME ..."
    
    if ! docker build -t "$FULL_IMAGE_NAME" .; then
        echo -e "${RED}ERROR: Failed to build Docker image. Make sure Dockerfile is in the current directory.${NC}"
        exit 1
    else
        echo -e "${GREEN}Docker image $FULL_IMAGE_NAME built successfully!${NC}"
    fi
    
    exit 0
}

# ============================================================================
# List Techniques (via Docker)
# ============================================================================
list_techniques_docker() {
    echo
    echo -e "${BLUE}===== LIST AVAILABLE TECHNIQUES (via Docker) =====${NC}"
    docker run --rm "$FULL_IMAGE_NAME" --list
    SCRIPT_RUN_ERRORLEVEL=$?
    
    exit $SCRIPT_RUN_ERRORLEVEL
}

# ============================================================================
# Handle 'repair' command and its arguments
# ============================================================================
handle_repair_command() {
    local INPUT_FILE_ARG=""
    local REFERENCE_FILE_ARG=""
    local OUTPUT_FILE_ARG=""
    local TECHNIQUE_OPTION=""
    local ARGS_OK=true
    
    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            "--technique"|"-t")
                if [ -z "$2" ]; then
                    echo -e "${RED}ERROR: --technique option requires a value.${NC}"
                    ARGS_OK=false
                    break
                fi
                TECHNIQUE_OPTION="-t $2"
                shift 2
                ;;
            *)
                if [ -z "$INPUT_FILE_ARG" ]; then
                    INPUT_FILE_ARG="$1"
                elif [ -z "$REFERENCE_FILE_ARG" ]; then
                    REFERENCE_FILE_ARG="$1"
                elif [ -z "$OUTPUT_FILE_ARG" ]; then
                    OUTPUT_FILE_ARG="$1"
                else
                    echo -e "${YELLOW}WARNING: Extraneous argument for repair: $1${NC}"
                fi
                shift
                ;;
        esac
    done
    
    # Validate arguments
    if [ "$ARGS_OK" = "false" ]; then
        show_help_for_sub_command "repair"
        exit 1
    fi
    
    if [ -z "$INPUT_FILE_ARG" ]; then
        echo -e "${RED}ERROR: Missing INPUT_FILE for 'repair'.${NC}"
        show_help_for_sub_command "repair"
        exit 1
    fi
    
    if [ -z "$REFERENCE_FILE_ARG" ]; then
        echo -e "${RED}ERROR: Missing REFERENCE_FILE for 'repair'.${NC}"
        show_help_for_sub_command "repair"
        exit 1
    fi
    
    if [ -z "$OUTPUT_FILE_ARG" ]; then
        echo -e "${RED}ERROR: Missing OUTPUT_FILE for 'repair'.${NC}"
        show_help_for_sub_command "repair"
        exit 1
    fi
    
    execute_repair_docker "$INPUT_FILE_ARG" "$REFERENCE_FILE_ARG" "$OUTPUT_FILE_ARG" "$TECHNIQUE_OPTION"
}

execute_repair_docker() {
    local INPUT_FILE_ARG="$1"
    local REFERENCE_FILE_ARG="$2"
    local OUTPUT_FILE_ARG="$3"
    local TECHNIQUE_OPTION="$4"
    
    echo
    echo -e "${BLUE}===== REPAIR MP4 (Dockerized) =====${NC}"
    
    # Get absolute paths
    ABS_INPUT_FILE=$(realpath "$INPUT_FILE_ARG")
    ABS_REFERENCE_FILE=$(realpath "$REFERENCE_FILE_ARG")
    ABS_OUTPUT_FILE=$(realpath "$OUTPUT_FILE_ARG")
    
    if [ ! -f "$ABS_INPUT_FILE" ]; then
        echo -e "${RED}ERROR: Input file does not exist: \"$ABS_INPUT_FILE\"${NC}"
        exit 1
    fi
    
    # Get directories and filenames
    INPUT_DIR=$(dirname "$ABS_INPUT_FILE")
    INPUT_FILENAME=$(basename "$ABS_INPUT_FILE")
    REF_DIR=$(dirname "$ABS_REFERENCE_FILE")
    REF_FILENAME=$(basename "$ABS_REFERENCE_FILE")
    OUTPUT_DIR=$(dirname "$ABS_OUTPUT_FILE")
    OUTPUT_FILENAME=$(basename "$ABS_OUTPUT_FILE")
    
    # Ensure output directory exists
    if [ ! -d "$OUTPUT_DIR" ]; then
        echo "Creating output directory: \"$OUTPUT_DIR\""
        if ! mkdir -p "$OUTPUT_DIR"; then
            echo -e "${RED}ERROR: Could not create output directory: \"$OUTPUT_DIR\"${NC}"
            exit 1
        fi
    fi
    
    echo "  Input File (Host): \"$ABS_INPUT_FILE\""
    echo "  Reference File (Host): \"$ABS_REFERENCE_FILE\""
    echo "  Output File (Host): \"$ABS_OUTPUT_FILE\""
    if [ -n "$TECHNIQUE_OPTION" ]; then
        echo "  Technique Option: $TECHNIQUE_OPTION"
    fi
    
    # Prepare Docker command
    DOCKER_VOLUMES="-v \"$INPUT_DIR:/input:ro\" -v \"$REF_DIR:/reference:ro\" -v \"$OUTPUT_DIR:/output\""
    DOCKER_SCRIPT_ARGS="\"/input/$INPUT_FILENAME\" \"/reference/$REF_FILENAME\" \"/output/$OUTPUT_FILENAME\""
    
    if [ -n "$TECHNIQUE_OPTION" ]; then
        DOCKER_SCRIPT_ARGS="$DOCKER_SCRIPT_ARGS $TECHNIQUE_OPTION"
    fi
    
    DOCKER_RUN_CMD="docker run --rm $DOCKER_VOLUMES \"$FULL_IMAGE_NAME\" $DOCKER_SCRIPT_ARGS"
    echo "Running: $DOCKER_RUN_CMD"
    
    # Execute the command (eval needed to handle quotes in paths properly)
    eval $DOCKER_RUN_CMD
    SCRIPT_RUN_ERRORLEVEL=$?
    
    if [ $SCRIPT_RUN_ERRORLEVEL -eq 0 ]; then
        echo -e "${GREEN}SUCCESS: Repair process completed. Output: \"$ABS_OUTPUT_FILE\"${NC}"
    else
        echo -e "${RED}FAILED: Repair process failed (Error Code: $SCRIPT_RUN_ERRORLEVEL).${NC}"
    fi
    
    exit $SCRIPT_RUN_ERRORLEVEL
}

# ============================================================================
# Handle 'info' command and its arguments
# ============================================================================
handle_info_command() {
    local INFO_FILE_ARG=""
    local DETAILED_OPTION=""
    local ARGS_OK=true
    
    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            "--detailed")
                DETAILED_OPTION="--detailed"
                shift
                ;;
            *)
                if [ -z "$INFO_FILE_ARG" ]; then
                    INFO_FILE_ARG="$1"
                else
                    echo -e "${YELLOW}WARNING: Extraneous argument for info: $1${NC}"
                fi
                shift
                ;;
        esac
    done
    
    # Validate arguments
    if [ "$ARGS_OK" = "false" ]; then
        show_help_for_sub_command "info"
        exit 1
    fi
    
    if [ -z "$INFO_FILE_ARG" ]; then
        echo -e "${RED}ERROR: Missing MP4_FILE for 'info'.${NC}"
        show_help_for_sub_command "info"
        exit 1
    fi
    
    execute_info_docker "$INFO_FILE_ARG" "$DETAILED_OPTION"
}

execute_info_docker() {
    local INFO_FILE_ARG="$1"
    local DETAILED_OPTION="$2"
    
    echo
    echo -e "${BLUE}===== ANALYZE MP4 (Dockerized) =====${NC}"
    
    # Get absolute path
    ABS_INFO_FILE=$(realpath "$INFO_FILE_ARG")
    
    if [ ! -f "$ABS_INFO_FILE" ]; then
        echo -e "${RED}ERROR: MP4 file for info does not exist: \"$ABS_INFO_FILE\"${NC}"
        exit 1
    fi
    
    # Get directory and filename
    INFO_DIR=$(dirname "$ABS_INFO_FILE")
    INFO_FILENAME=$(basename "$ABS_INFO_FILE")
    
    echo "  Analyzing File (Host): \"$ABS_INFO_FILE\""
    if [ -n "$DETAILED_OPTION" ]; then
        echo "  Detailed: Yes"
    fi
    
    # Prepare Docker command
    DOCKER_VOLUMES="-v \"$INFO_DIR:/data:ro\""
    DOCKER_SCRIPT_ARGS="\"/data/$INFO_FILENAME\""
    
    if [ -n "$DETAILED_OPTION" ]; then
        DOCKER_SCRIPT_ARGS="$DOCKER_SCRIPT_ARGS $DETAILED_OPTION"
    fi
    
    DOCKER_RUN_CMD="docker run --rm $DOCKER_VOLUMES --entrypoint python \"$FULL_IMAGE_NAME\" /app/mp4_info.py $DOCKER_SCRIPT_ARGS"
    echo "Running: $DOCKER_RUN_CMD"
    
    # Execute the command (eval needed to handle quotes in paths properly)
    eval $DOCKER_RUN_CMD
    SCRIPT_RUN_ERRORLEVEL=$?
    
    if [ $SCRIPT_RUN_ERRORLEVEL -eq 0 ]; then
        echo -e "${GREEN}SUCCESS: Analysis completed.${NC}"
    else
        echo -e "${RED}FAILED: Analysis failed or file is corrupt (Error Code: $SCRIPT_RUN_ERRORLEVEL).${NC}"
        echo "Suggestion: Try 'repair' command if the file seems damaged."
    fi
    
    exit $SCRIPT_RUN_ERRORLEVEL
}

# ============================================================================
# Handle 'batch' command and its arguments
# ============================================================================
handle_batch_command() {
    local BATCH_INPUT_DIR_ARG=""
    local BATCH_REF_FILE_ARG=""
    local BATCH_OUTPUT_DIR_ARG=""
    local BATCH_TECHNIQUE_OPTION=""
    local ARGS_OK=true
    
    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            "--technique"|"-t")
                if [ -z "$2" ]; then
                    echo -e "${RED}ERROR: --technique option requires a value.${NC}"
                    ARGS_OK=false
                    break
                fi
                BATCH_TECHNIQUE_OPTION="-t $2"
                shift 2
                ;;
            *)
                if [ -z "$BATCH_INPUT_DIR_ARG" ]; then
                    BATCH_INPUT_DIR_ARG="$1"
                elif [ -z "$BATCH_REF_FILE_ARG" ]; then
                    BATCH_REF_FILE_ARG="$1"
                elif [ -z "$BATCH_OUTPUT_DIR_ARG" ]; then
                    BATCH_OUTPUT_DIR_ARG="$1"
                else
                    echo -e "${YELLOW}WARNING: Extraneous argument for batch: $1${NC}"
                fi
                shift
                ;;
        esac
    done
    
    # Validate arguments
    if [ "$ARGS_OK" = "false" ]; then
        show_help_for_sub_command "batch"
        exit 1
    fi
    
    if [ -z "$BATCH_INPUT_DIR_ARG" ]; then
        echo -e "${RED}ERROR: Missing INPUT_DIR for 'batch'.${NC}"
        show_help_for_sub_command "batch"
        exit 1
    fi
    
    if [ -z "$BATCH_REF_FILE_ARG" ]; then
        echo -e "${RED}ERROR: Missing REFERENCE_FILE for 'batch'.${NC}"
        show_help_for_sub_command "batch"
        exit 1
    fi
    
    if [ -z "$BATCH_OUTPUT_DIR_ARG" ]; then
        echo -e "${RED}ERROR: Missing OUTPUT_DIR for 'batch'.${NC}"
        show_help_for_sub_command "batch"
        exit 1
    fi
    
    execute_batch_docker "$BATCH_INPUT_DIR_ARG" "$BATCH_REF_FILE_ARG" "$BATCH_OUTPUT_DIR_ARG" "$BATCH_TECHNIQUE_OPTION"
}

execute_batch_docker() {
    local BATCH_INPUT_DIR_ARG="$1"
    local BATCH_REF_FILE_ARG="$2"
    local BATCH_OUTPUT_DIR_ARG="$3"
    local BATCH_TECHNIQUE_OPTION="$4"
    
    echo
    echo -e "${BLUE}===== BATCH REPAIR MP4 (Dockerized) =====${NC}"
    
    # Get absolute paths
    ABS_BATCH_INPUT_DIR=$(realpath "$BATCH_INPUT_DIR_ARG")
    ABS_BATCH_REF_FILE=$(realpath "$BATCH_REF_FILE_ARG")
    ABS_BATCH_OUTPUT_DIR=$(realpath "$BATCH_OUTPUT_DIR_ARG")
    
    if [ ! -d "$ABS_BATCH_INPUT_DIR" ]; then
        echo -e "${RED}ERROR: Batch input directory does not exist: \"$ABS_BATCH_INPUT_DIR\"${NC}"
        exit 1
    fi
    
    if [ ! -f "$ABS_BATCH_REF_FILE" ]; then
        echo -e "${RED}ERROR: Batch reference file does not exist: \"$ABS_BATCH_REF_FILE\"${NC}"
        exit 1
    fi
    
    # Ensure output directory exists
    if [ ! -d "$ABS_BATCH_OUTPUT_DIR" ]; then
        echo "Creating batch output directory: \"$ABS_BATCH_OUTPUT_DIR\""
        if ! mkdir -p "$ABS_BATCH_OUTPUT_DIR"; then
            echo -e "${RED}ERROR: Could not create batch output dir: \"$ABS_BATCH_OUTPUT_DIR\"${NC}"
            exit 1
        fi
    fi
    
    # Get reference directory and filename
    BATCH_REF_DIR=$(dirname "$ABS_BATCH_REF_FILE")
    BATCH_REF_FILENAME=$(basename "$ABS_BATCH_REF_FILE")
    
    echo "  Input Directory (Host): \"$ABS_BATCH_INPUT_DIR\""
    echo "  Reference File (Host): \"$ABS_BATCH_REF_FILE\""
    echo "  Output Directory (Host): \"$ABS_BATCH_OUTPUT_DIR\""
    if [ -n "$BATCH_TECHNIQUE_OPTION" ]; then
        echo "  Technique for all: $BATCH_TECHNIQUE_OPTION"
    fi
    
    # Counters for summary
    TOTAL_SUCCESS_COUNT=0
    TOTAL_FAIL_COUNT=0
    TOTAL_PROCESSED_COUNT=0
    TOTAL_SKIPPED_COUNT=0
    
    # Process each MP4 file
    for INPUT_FILE in "$ABS_BATCH_INPUT_DIR"/*.mp4; do
        # Skip if no matches found
        [ -e "$INPUT_FILE" ] || continue
        
        TOTAL_PROCESSED_COUNT=$((TOTAL_PROCESSED_COUNT + 1))
        CURRENT_INPUT_FILENAME=$(basename "$INPUT_FILE")
        CURRENT_OUTPUT_FILENAME="$CURRENT_INPUT_FILENAME"
        
        echo
        echo -e "${BLUE}--- Processing: $CURRENT_INPUT_FILENAME ---${NC}"
        
        # Skip if output already exists
        if [ -f "$ABS_BATCH_OUTPUT_DIR/$CURRENT_OUTPUT_FILENAME" ]; then
            echo "    Skipping, output file already exists: \"$ABS_BATCH_OUTPUT_DIR/$CURRENT_OUTPUT_FILENAME\""
            TOTAL_SKIPPED_COUNT=$((TOTAL_SKIPPED_COUNT + 1))
            continue
        fi
        
        # Prepare Docker command
        DOCKER_VOLUMES="-v \"$ABS_BATCH_INPUT_DIR:/input:ro\" -v \"$BATCH_REF_DIR:/reference:ro\" -v \"$ABS_BATCH_OUTPUT_DIR:/output\""
        DOCKER_SCRIPT_ARGS="\"/input/$CURRENT_INPUT_FILENAME\" \"/reference/$BATCH_REF_FILENAME\" \"/output/$CURRENT_OUTPUT_FILENAME\""
        
        if [ -n "$BATCH_TECHNIQUE_OPTION" ]; then
            DOCKER_SCRIPT_ARGS="$DOCKER_SCRIPT_ARGS $BATCH_TECHNIQUE_OPTION"
        fi
        
        DOCKER_RUN_CMD="docker run --rm $DOCKER_VOLUMES \"$FULL_IMAGE_NAME\" $DOCKER_SCRIPT_ARGS"
        echo "    Running: $DOCKER_RUN_CMD"
        
        # Execute the command (eval needed to handle quotes in paths properly)
        eval $DOCKER_RUN_CMD
        
        if [ $? -eq 0 ]; then
            echo -e "    ${GREEN}SUCCESS: \"$CURRENT_INPUT_FILENAME\" repaired.${NC}"
            TOTAL_SUCCESS_COUNT=$((TOTAL_SUCCESS_COUNT + 1))
        else
            echo -e "    ${RED}FAILED: \"$CURRENT_INPUT_FILENAME\" repair failed (Error Code: $?).${NC}"
            TOTAL_FAIL_COUNT=$((TOTAL_FAIL_COUNT + 1))
        fi
    done
    
    echo
    echo -e "${BLUE}--- Batch Processing Summary ---${NC}"
    echo "  Total MP4 files found: $TOTAL_PROCESSED_COUNT"
    echo "  Successfully repaired: $TOTAL_SUCCESS_COUNT"
    echo "  Skipped (already exist): $TOTAL_SKIPPED_COUNT"
    echo "  Failed to repair: $TOTAL_FAIL_COUNT"
    
    exit 0
}

# ============================================================================
# Help Display and Script Exit Points
# ============================================================================
show_main_help() {
    echo
    echo -e "${BLUE}===== MP4 Recovery Toolkit =====${NC}"
    echo
    echo "Usage: $(basename "$0") COMMAND [OPTIONS] [ARGUMENTS...]"
    echo
    echo "Commands:"
    echo "  setup                      Build the Docker image '$FULL_IMAGE_NAME'."
    echo "                              (Dockerfile must be in the current directory)."
    echo
    echo "  list                       Lists available recovery techniques (runs in Docker)."
    echo
    echo "  repair [options] INPUT_FILE REFERENCE_FILE OUTPUT_FILE"
    echo "                              Repairs a single MP4 file."
    echo "      INPUT_FILE             Path to the damaged MP4 file."
    echo "      REFERENCE_FILE         Path to a healthy reference MP4 file."
    echo "      OUTPUT_FILE            Path where the repaired MP4 file will be saved."
    echo "      Options:"
    echo "        -t N, --technique N  (Optional) Use specific technique number N."
    echo "                              If omitted, all techniques are tried by the master script."
    echo
    echo "  info [options] MP4_FILE"
    echo "                              Analyzes a single MP4_FILE."
    echo "      MP4_FILE               Path to the MP4 file to analyze."
    echo "      Options:"
    echo "        --detailed           (Optional) Provides more detailed analysis output."
    echo
    echo "  batch [options] INPUT_DIR REFERENCE_FILE OUTPUT_DIR"
    echo "                              Repairs all *.mp4 files in INPUT_DIR."
    echo "      INPUT_DIR              Directory containing damaged MP4 files."
    echo "      REFERENCE_FILE         Path to a single healthy reference MP4 for all files."
    echo "      OUTPUT_DIR             Directory where repaired files will be saved."
    echo "      Options:"
    echo "        -t N, --technique N  (Optional) Apply specific technique N to all files."
    echo "                              If omitted, all techniques are tried for each file."
    echo
    echo "  --help, -h                 Show this help message."
    echo
    echo "Example usage:"
    echo "  $(basename "$0") setup"
    echo "  $(basename "$0") list"
    echo "  $(basename "$0") repair \"/path/to/damaged.mp4\" \"/path/to/good.mp4\" \"/path/to/repaired.mp4\""
    echo "  $(basename "$0") repair damaged.mp4 reference.mp4 output.mp4 -t 2"
    echo "  $(basename "$0") info \"my video.mp4\" --detailed"
    echo "  $(basename "$0") batch \"/path/to/damaged_files\" \"/path/to/global_ref.mp4\" \"/path/to/repaired_output\" -t 10"
    echo
    
    exit 0
}

# Helper for showing command-specific help hints on error
show_help_for_sub_command() {
    echo "For correct usage of the '$1' command, see general help:"
    echo "  $(basename "$0") --help"
}

# Call the main command dispatcher with all arguments
"$@"