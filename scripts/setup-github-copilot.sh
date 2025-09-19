#!/bin/bash

# Setup script for GitHub Copilot CLI in devcontainer
# This script installs GitHub CLI and the Copilot CLI extension
# Note: This is different from the GitHub Copilot VS Code extension
# Usage: ./scripts/setup-github-copilot.sh

set -e  # Exit on any error

echo "🔧 Setting up GitHub Copilot CLI for terminal AI assistance..."
echo "============================================================="
echo
echo "📝 Note: This installs the CLI version of GitHub Copilot for terminal use."
echo "   It's separate from the VS Code extension that provides code completions."
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in a devcontainer
if [ ! -f /.dockerenv ] && [ "$DEVCONTAINER" != "true" ]; then
    print_warning "This script is designed for devcontainer environments."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if GitHub Copilot CLI is already installed
if gh extension list 2>/dev/null | grep -q "gh-copilot"; then
    print_warning "GitHub Copilot CLI extension is already installed"
    read -p "Reinstall? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "GitHub Copilot CLI is ready to use!"
        print_status "Run 'gh auth login' if you need to authenticate with GitHub."
        exit 0
    fi
fi

# GitHub Copilot CLI doesn't require Node.js - it's a GitHub CLI extension
print_status "GitHub Copilot CLI doesn't require Node.js - proceeding with GitHub CLI setup..."

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    print_status "Installing GitHub CLI..."
    # Install GitHub CLI
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
    sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt update
    sudo apt install gh -y
    print_success "GitHub CLI installed: $(gh --version)"
else
    print_success "GitHub CLI already installed: $(gh --version | head -n1)"
fi

# Install GitHub Copilot CLI extension
print_status "Installing GitHub Copilot CLI extension..."
gh extension install github/gh-copilot

# Verify installation
if gh extension list | grep -q "gh-copilot"; then
    print_success "GitHub Copilot CLI extension installed successfully!"
else
    print_error "GitHub Copilot CLI extension installation failed."
    exit 1
fi

# Setup instructions
echo
echo "🎉 Setup Complete!"
echo "=================="
echo
print_status "Next steps:"
echo "1. Authenticate with GitHub:"
echo -e "   ${BLUE}gh auth login${NC}"
echo
echo "2. Test Copilot CLI:"
echo -e "   ${BLUE}gh copilot suggest \"create a python function to sort a list\"${NC}"
echo -e "   ${BLUE}gh copilot explain \"git rebase -i HEAD~3\"${NC}"
echo
print_status "Common commands:"
echo -e "• ${BLUE}gh copilot suggest${NC} - Get command suggestions"
echo -e "• ${BLUE}gh copilot explain${NC} - Explain commands"
echo
print_status "For more information, visit: https://docs.github.com/en/copilot/github-copilot-in-the-cli"
echo
print_warning "Note: Requires GitHub Copilot subscription and authentication."
echo