# OMA GitHub Actions

A collection of reusable GitHub Actions for AI-powered development workflows.

## 🤖 Claude Code Review Action

Get intelligent code reviews and automated fixes from Claude 4 Sonnet by simply commenting on your pull requests. Claude can both review code and create fix PRs with proposed changes.

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
  contents: write
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

## 🔮 Future Directions

Based on research into AI code modification architectures in 2025, we've identified key improvements for automated code fixes:

• **Direct File Modification Architecture**: Move away from tool calling patterns to direct file modification approaches similar to Aider and Cursor IDE, which parse AI responses for changes and apply them programmatically rather than relying on AI tool calling for file operations

• **MCP Integration for Local Development**: Implement Model Context Protocol (MCP) integration for local development workflows, enabling real file system access and more reliable code modifications when working outside GitHub Actions constraints

• **Diff-Based Change Application**: Adopt diff-based approaches for more reliable file modifications, especially for large files, using git patch mechanisms rather than full file replacement to reduce conflicts and improve merge reliability

## 🛠️ Available Actions

| Action | Description | Status |
|--------|-------------|---------|
| `claude-code-review` | AI-powered code review and analysis with Claude 4 Sonnet | ✅ Available |

**Note**: Automated code fix PRs are currently in development. The action provides comprehensive code analysis and suggestions, with automated fix implementation planned for future releases.

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