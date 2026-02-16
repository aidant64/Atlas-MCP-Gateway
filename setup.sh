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
echo "Press Enter to skip if using local dev server (default)."
read -s -p "Inngest Event Key: " INNGEST_EVENT
echo ""
read -s -p "Inngest Signing Key: " INNGEST_SIGNING
echo ""

if [ -n "$INNGEST_EVENT" ]; then
    INNGEST_VARS="INNGEST_EVENT_KEY=$INNGEST_EVENT\nINNGEST_SIGNING_KEY=$INNGEST_SIGNING"
    echo "-> Configured for Inngest Cloud."
else
    INNGEST_VARS="# INNGEST_EVENT_KEY (Set for Prod)\n# INNGEST_SIGNING_KEY (Set for Prod)"
    echo "-> Configured for Local Inngest Dev Server."
fi
echo ""

# 4. Create .env file for Docker
echo "Creating .env file..."
echo -e "MODAL_FUNCTION_NAME=$MODAL_FUNC\n$AI_ENV_VAR\n$INNGEST_VARS" > .env
echo ".env file created."
echo ""

# 4. Docker Build & Run
read -p "Do you want to build and run the Docker container now? [y/N]: " RUN_DOCKER
if [[ "$RUN_DOCKER" =~ ^[Yy]$ ]]; then
    echo "Building Docker image..."
    docker build -t atlas-gateway .
    
    echo "Running Docker container..."
    # Note: For Modal to work inside Docker, we need to pass credentials.
    # We assume 'modal token new' has been run locally or tokens are passed.
    # For this script, we'll ask for them if not found in env.
    
    if [ -z "$MODAL_TOKEN_ID" ]; then
        echo "⚠️  Modal credentials not detected in environment."
        echo "To run inside Docker, we need your Modal credentials."
        read -s -p "Modal Token ID: " M_ID
        echo ""
        read -s -p "Modal Token Secret: " M_SECRET
        echo ""
        MODAL_ARGS="-e MODAL_TOKEN_ID=$M_ID -e MODAL_TOKEN_SECRET=$M_SECRET"
    else
        MODAL_ARGS="-e MODAL_TOKEN_ID=$MODAL_TOKEN_ID -e MODAL_TOKEN_SECRET=$MODAL_TOKEN_SECRET"
    fi
    
    docker run -it --rm --env-file .env $MODAL_ARGS atlas-gateway
else
    echo "Setup complete. To run manually:"
    echo "docker build -t atlas-gateway ."
    echo "docker run --env-file .env -e MODAL_TOKEN_ID=... -e MODAL_TOKEN_SECRET=... atlas-gateway"
fi
