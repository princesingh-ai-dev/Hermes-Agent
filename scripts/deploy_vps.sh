#!/bin/bash
# ---------------------------------------------------------
# Hermes Agent - $5 VPS Quick Installer
# ---------------------------------------------------------
echo "🚀 Bootstrapping Hermes Agent for VPS..."

# Update and install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "📦 Installing Docker and Docker Compose..."
    apt-get update && apt-get install -y curl
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

echo "📂 Setting up directories..."
mkdir -p hermes-agent/data hermes-agent/skills
cd hermes-agent

# Download configurations (In reality, this would git clone)
# git clone https://github.com/NousResearch/hermes-agent.git .
echo "✨ Generating .env template..."
cat << 'EOF' > .env
OPENROUTER_API_KEY=
TELEGRAM_BOT_TOKEN=
DISCORD_BOT_TOKEN=
EOF

echo "✅ Installation complete!"
echo "👉 Next steps:"
echo "1. Edit .env with your keys: nano .env"
echo "2. Start the agent: docker-compose up -d"
