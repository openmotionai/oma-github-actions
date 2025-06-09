# OMA GitHub Actions

A collection of reusable GitHub Actions for AI-powered development workflows.

## 🤖 Claude Code Review Action

Get intelligent code reviews and suggestions from Claude 4 Sonnet by simply commenting on your pull requests.

### ⚡ Quick Start

Add this workflow to your repository at `.github/workflows/claude-review.yml`:

```yaml
name: Claude Code Review

on:
  issue_comment:
    types: [created]
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  claude-review:
    if: |
      github.event.issue.pull_request || 
      github.event.pull_request ||
      (github.event.comment && (contains(github.event.comment.body, '@claude') || contains(github.event.comment.body, '@Claude')))
    runs-on: ubuntu-latest
    
    steps:
    - uses: openmotionai/oma-github-actions/actions/claude-code-review@main
      with:
        anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### 🔑 Setup

1. **Get Anthropic API Key**:
   - Sign up at [claude.ai](https://claude.ai) if you don't have an account
   - Go to [console.anthropic.com](https://console.anthropic.com/settings/keys)
   - Create a new API key

2. **Add to Repository Secrets**:
   ```bash
   # Using GitHub CLI
   gh secret set ANTHROPIC_API_KEY --body "your-api-key-here"
   
   # Or via web interface:
   # Settings → Secrets and variables → Actions → New repository secret
   ```

### 🚀 Usage

Comment on any PR with Claude commands:

**Review Mode** (analysis only):
- `@claude review this code`
- `@claude check for security issues`
- `@claude analyze the logic in main.py`

**Propose Changes Mode** (suggests improvements):
- `@claude fix the bug in error handling`
- `@claude refactor this function for clarity`
- `@claude optimize the database queries`
- `@claude add error handling to the API calls`

### 💰 Cost

- Uses Claude 4 Sonnet: ~$3 input / $15 output per million tokens
- Typical PR review: $0.10-$0.50 depending on code size
- Only charges when you use it (no monthly fees)

## 📚 Documentation

- [Claude Code Review Action](actions/claude-code-review/README.md) - Detailed documentation
- [Advanced Configuration Examples](docs/) - Complex setups and customizations

## 🛠️ Available Actions

| Action | Description | Status |
|--------|-------------|---------|
| `claude-code-review` | AI-powered code review with Claude 4 Sonnet | ✅ Available |

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines for more information.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔒 Security

- API keys are stored securely in GitHub secrets
- No code data is retained by Claude
- All communications are encrypted (HTTPS/TLS)
- Temporary files are automatically cleaned up

## 🆘 Support

- Check the [troubleshooting guide](actions/claude-code-review/README.md#troubleshooting)
- Open an issue for bugs or feature requests
- Discussions for questions and community support