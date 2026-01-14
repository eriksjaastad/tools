#!/bin/bash

# Local AI Setup Script
# Installs Ollama and sets up initial models

echo "🚀 Setting up Local AI for cost savings..."
echo ""

# Check if Ollama already installed
if command -v ollama &> /dev/null; then
    echo "✅ Ollama already installed"
else
    echo "📦 Installing Ollama via Homebrew..."
    brew install ollama
fi

echo ""
echo "🔧 Starting Ollama service..."
brew services start ollama

# Wait for service to start
echo "⏳ Waiting for Ollama service to start..."
sleep 5

echo ""
echo "⬇️  Downloading Llama 3.2 3B (fast, good for filtering)..."
echo "   This may take a few minutes depending on your internet speed..."
ollama pull llama3.2:3b

echo ""
echo "✅ Testing installation..."
TEST_RESULT=$(ollama run llama3.2:3b "What is 2+2? Answer with just the number." --verbose=false)
echo "   Test query: What is 2+2?"
echo "   Response: $TEST_RESULT"

echo ""
echo "🎉 Local AI is ready!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Quick Start:"
echo ""
echo "  Test from command line:"
echo "    ollama run llama3.2:3b 'Your prompt here'"
echo ""
echo "  Use in Python (OpenAI-compatible):"
echo "    import openai"
echo "    openai.api_base = 'http://localhost:11434/v1'"
echo "    openai.api_key = 'not-needed'"
echo "    response = openai.ChatCompletion.create("
echo "        model='llama3.2:3b',"
echo "        messages=[{'role': 'user', 'content': 'Hello!'}]"
echo "    )"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Installed models:"
ollama list

echo ""
echo "💡 Next steps:"
echo "  1. Test quality: ollama run llama3.2:3b 'Your test prompt'"
echo "  2. Add to actionable-ai-intel for filtering (saves $15-30/month)"
echo "  3. See LOCAL_AI_GAMEPLAN.md for full integration guide"
echo ""
echo "💰 Estimated savings: $30-70/month ($360-840/year)"
echo ""

