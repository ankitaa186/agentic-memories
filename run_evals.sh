#!/bin/bash
################################################################################
# Agentic Memories - Evaluation Runner
# 
# This script runs prompt evaluations to test extraction quality.
# It tests prompts directly without running the full API or storage pipeline.
#
# Usage:
#   ./run_evals.sh              # Run with current prompt
#   ./run_evals.sh --v2         # Run with EXTRACTION_PROMPT_V2
#   ./run_evals.sh --help       # Show help
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
EVAL_SCRIPT="$SCRIPT_DIR/tests/evals/test_prompts_direct.py"

################################################################################
# Functions
################################################################################

print_header() {
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo -e "${BLUE}$1${NC}"
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

show_help() {
    cat << EOF
Agentic Memories - Evaluation Runner

USAGE:
    ./run_evals.sh [OPTIONS]

OPTIONS:
    --help, -h      Show this help message

WHAT IT DOES:
    1. Interactive menu to choose test suite and prompt
    2. Sets up Python virtual environment automatically
    3. Installs dependencies (if needed)
    4. Verifies OPENAI_API_KEY is set
    5. Runs evaluation and displays results
    6. Saves detailed results to tests/evals/results/

TEST SUITES:
    Basic (20 cases, ~2 min)           - Quick validation
    Comprehensive (110 cases, ~10 min) - Full test suite

PROMPTS:
    Current Prompt   - Baseline performance
    V2 Prompt        - Improved prompt (shorter, better examples)

RESULTS:
    - Console output: Formatted metrics report
    - JSON files: tests/evals/results/results_*.json
    
For more info, see: tests/evals/README.md

EOF
}

check_openai_key() {
    print_header "Checking OpenAI API Key"
    
    # Check .env file
    if [ -f "$SCRIPT_DIR/.env" ]; then
        if grep -q "OPENAI_API_KEY=" "$SCRIPT_DIR/.env"; then
            print_success "Found OPENAI_API_KEY in .env file"
            # Export it
            export $(grep "OPENAI_API_KEY=" "$SCRIPT_DIR/.env" | xargs)
            return 0
        fi
    fi
    
    # Check environment
    if [ -n "$OPENAI_API_KEY" ]; then
        print_success "Found OPENAI_API_KEY in environment"
        return 0
    fi
    
    print_error "OPENAI_API_KEY not found!"
    echo ""
    echo "Please set your OpenAI API key:"
    echo "  1. Create a .env file in the project root:"
    echo "     echo 'OPENAI_API_KEY=your_key_here' > .env"
    echo ""
    echo "  2. Or export it in your shell:"
    echo "     export OPENAI_API_KEY=your_key_here"
    echo ""
    exit 1
}

setup_venv() {
    print_header "Setting Up Python Environment"
    
    if [ ! -d "$VENV_DIR" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        print_success "Virtual environment created"
    else
        print_success "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    print_success "Virtual environment activated"
}

install_dependencies() {
    print_header "Installing Dependencies"
    
    # Check if dependencies are already installed
    if python -c "import openai, pydantic" 2>/dev/null; then
        print_success "Dependencies already installed"
        return 0
    fi
    
    print_info "Installing required packages..."
    pip install -q --upgrade pip
    
    # Install from requirements.txt
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        pip install -q -r "$SCRIPT_DIR/requirements.txt"
        print_success "Dependencies installed from requirements.txt"
    else
        print_error "requirements.txt not found!"
        exit 1
    fi
}

modify_script_for_v2() {
    # Set environment variable to use V2 prompt
    # The test scripts will check this variable
    export USE_PROMPT_V2=1
    print_info "Configured to use EXTRACTION_PROMPT_V2 via environment variable"
}

run_evaluation() {
    local script_to_run="$1"
    local prompt_name="$2"
    
    print_header "Running Evaluation - $prompt_name"
    
    print_info "Testing conversation scenarios..."
    print_info "This will take a few minutes..."
    echo ""
    
    # Ensure virtual environment is activated
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        print_error "Virtual environment not found at $VENV_DIR"
        return 1
    fi
    
    # Change to project root (where the script should run from)
    cd "$SCRIPT_DIR"
    
    # Run the evaluation with the virtual environment's Python
    # Set PYTHONPATH to include project root
    PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH" "$VENV_DIR/bin/python" "$script_to_run"
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo ""
        print_success "Evaluation completed successfully!"
        echo ""
        print_info "Results saved to: tests/evals/results/"
        return 0
    else
        echo ""
        print_error "Evaluation failed with exit code $exit_code"
        return 1
    fi
}

################################################################################
# Main Script
################################################################################

show_menu() {
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo "                    🧪 AGENTIC MEMORIES - EVALUATION RUNNER"
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo ""
    echo "Select Test Suite:"
    echo "  1) Basic (20 cases, ~2 min) - Quick validation"
    echo "  2) Comprehensive (110 cases, ~10 min) - Full test suite"
    echo ""
    echo "  0) Exit"
    echo ""
}

show_prompt_menu() {
    echo ""
    echo "Select Prompt to Test:"
    echo "  1) Current Prompt (Baseline)"
    echo "  2) V2 Prompt (Improved)"
    echo ""
}

main() {
    # Parse arguments - only check for help
    for arg in "$@"; do
        case $arg in
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $arg"
                echo ""
                echo "Run with --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Change to script directory
    cd "$SCRIPT_DIR"
    
    # Run checks and setup first
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo "                    🧪 AGENTIC MEMORIES - EVALUATION RUNNER"
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo ""
    
    check_openai_key
    setup_venv
    install_dependencies
    
    # Show menu
    show_menu
    
    # Get test suite choice
    local suite_choice
    read -p "Enter choice [1-2, 0 to exit]: " suite_choice
    
    case $suite_choice in
        0)
            echo ""
            print_info "Exiting..."
            exit 0
            ;;
        1)
            local USE_COMPREHENSIVE=false
            local suite_name="Basic"
            ;;
        2)
            local USE_COMPREHENSIVE=true
            local suite_name="Comprehensive"
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
    
    # Show prompt menu
    show_prompt_menu
    
    # Get prompt choice
    local prompt_choice
    read -p "Enter choice [1-2]: " prompt_choice
    
    local USE_V2=false
    local prompt_name="Current Prompt"
    
    case $prompt_choice in
        1)
            USE_V2=false
            prompt_name="Current Prompt (Baseline)"
            ;;
        2)
            USE_V2=true
            prompt_name="V2 Prompt (Improved)"
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
    
    # Select script
    local SCRIPT_TO_RUN="$EVAL_SCRIPT"
    if [ "$USE_COMPREHENSIVE" = true ]; then
        SCRIPT_TO_RUN="$SCRIPT_DIR/tests/evals/test_comprehensive.py"
    fi
    
    # Set V2 flag if using V2
    if [ "$USE_V2" = true ]; then
        modify_script_for_v2
    fi
    
    local FULL_NAME="${suite_name} Suite with ${prompt_name}"
    
    # Run evaluation
    if run_evaluation "$SCRIPT_TO_RUN" "$FULL_NAME"; then
        # Success
        echo ""
        print_header "Next Steps"
        echo "  • Review detailed results: tests/evals/results/"
        echo "  • Read full guide: tests/evals/README.md"
        echo ""
        
        print_info "Want to test another configuration?"
        echo "  Run: ./run_evals.sh"
        echo ""
        
        exit 0
    else
        # Failure
        echo ""
        print_header "Troubleshooting"
        echo "  • Check logs above for errors"
        echo "  • Verify OPENAI_API_KEY is set correctly"
        echo "  • See troubleshooting guide: tests/evals/README.md"
        echo ""
        exit 1
    fi
}

# Run main function
main "$@"

