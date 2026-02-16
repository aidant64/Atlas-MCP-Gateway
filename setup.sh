#!/bin/bash

echo "=========================================="
echo "   ATLAS Governance Gateway Setup"
echo "=========================================="
echo ""

# 1. Ask for Atlas Brain Location (Modal Function)
read -p "Enter the Modal Function Name for the Atlas Brain [default: nislam-mics/ATLAS-NIST-Measure]: " MODAL_FUNC
MODAL_FUNC=${MODAL_FUNC:-"nislam-mics/ATLAS-NIST-Measure"}
echo "-> Using Modal Function: $MODAL_FUNC"
echo ""

# 2. Ask for Agent AI Configuration
echo "Choose your Agent AI Backend:"
echo "1) OpenAI (Requires API Key)"
echo "2) Local LLM (Ollama - Free/Private)"
read -p "Select [1/2]: " AI_CHOICE

if [ "$AI_CHOICE" == "1" ]; then
    read -s -p "Enter your OpenAI API Key: " OPENAI_KEY
    echo ""
    AI_ENV_VAR="OPENAI_API_KEY=$OPENAI_KEY"
    echo "-> Configured for OpenAI GPT-4."
else
    echo "-> Configured for Local LLM (Ollama)."
    echo "   Ensure you have run: ollama pull mistral-nemo"
    AI_ENV_VAR="OPENAI_API_KEY="
fi
echo ""

# 3. Inngest Configuration (Production vs Local)
echo "------------------------------------------"
echo "Inngest Configuration"
echo "------------------------------------------"
echo "To use Inngest Cloud (Production), you need your Event Key and Signing Key."
echo "Defaults provided from user request."
# User provided keys
DEFAULT_EVENT_KEY="e-aFf4PSmXY2ifCO0T-iYklR4B-Ptow_4ZacdCWfvgunDv4HjDR3o5JvFEfZ38KfQSCBQkzS_mKe9LTmPj9CUw"
DEFAULT_SIGNING_KEY="0V4B0RP-lCiyZFkuqLmqIjfhZjyBncXBO1flP41DPX7DRiBFR0-1ijapx5Qe7bsGH8IYp_l_Pr8-q11luIx-pw"

read -p "Inngest Event Key [default: provided]: " INNGEST_EVENT
INNGEST_EVENT=${INNGEST_EVENT:-$DEFAULT_EVENT_KEY}

read -p "Inngest Signing Key [default: provided]: " INNGEST_SIGNING
INNGEST_SIGNING=${INNGEST_SIGNING:-$DEFAULT_SIGNING_KEY}

if [ -n "$INNGEST_EVENT" ]; then
    INNGEST_VARS="INNGEST_EVENT_KEY=$INNGEST_EVENT\nINNGEST_SIGNING_KEY=$INNGEST_SIGNING"
    echo "-> Configured for Inngest Cloud."
else
    # Should not happen with defaults, but good fallback
    INNGEST_VARS="# INNGEST_EVENT_KEY (Set for Prod)\n# INNGEST_SIGNING_KEY (Set for Prod)"
    echo "-> Configured for Local Inngest Dev Server."
fi
echo ""

# 4. Modal Credentials
echo "------------------------------------------"
echo "Modal Credentials"
echo "------------------------------------------"
# User provided Modal Keys
DEFAULT_MODAL_TOKEN="ak-sPQFxWlQYiaThgPm8LNvpB"
DEFAULT_MODAL_SECRET="as-tmPvssFWxST5KwD5b2Wna5"

read -p "Modal Token ID [default: provided]: " MODAL_TOKEN_ID
MODAL_TOKEN_ID=${MODAL_TOKEN_ID:-$DEFAULT_MODAL_TOKEN}

read -s -p "Modal Token Secret [default: provided]: " MODAL_TOKEN_SECRET
MODAL_TOKEN_SECRET=${MODAL_TOKEN_SECRET:-$DEFAULT_MODAL_SECRET}
echo ""

# 5. Create .env file for Docker
echo "Creating .env file..."
echo -e "MODAL_FUNCTION_NAME=$MODAL_FUNC\nMODAL_TOKEN_ID=$MODAL_TOKEN_ID\nMODAL_TOKEN_SECRET=$MODAL_TOKEN_SECRET\n$AI_ENV_VAR\n$INNGEST_VARS" > .env
echo ".env file created."
echo ""

# 6. Docker Build & Run
read -p "Do you want to build and run the Docker container now? [y/N]: " RUN_DOCKER
if [[ "$RUN_DOCKER" =~ ^[Yy]$ ]]; then
    echo "Building Docker image (forcing fresh install)..."
    docker build --no-cache -t atlas-gateway .
    
    echo "Running Docker container..."
    # Connect with env file which includes all tokens
    docker run -it --rm --env-file .env atlas-gateway
else
    echo "Setup complete. To run manually:"
    echo "docker build -t atlas-gateway ."
    echo "docker run --env-file .env atlas-gateway"
fi
