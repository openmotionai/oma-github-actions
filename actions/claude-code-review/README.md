# Claude Code Review Action

AI-powered code review using Claude 4 Sonnet with extended thinking capabilities.

## Features

- 🚨 **High-priority focus**: Security vulnerabilities, bugs, breaking changes
- 🧠 **Extended thinking**: Claude reasons through complex code patterns
- 💬 **Comment-driven**: Trigger reviews with `@claude` comments
- ⚡ **Fast responses**: Optimized for developer workflow
- 🔒 **Secure**: No code data stored, API keys protected

## Usage

### Basic Setup

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

### Advanced Configuration

```yaml
    - uses: openmotionai/oma-github-actions/actions/claude-code-review@main
      with:
        anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
        github-token: ${{ secrets.GITHUB_TOKEN }}
        model: 'claude-sonnet-4-20250514'
        max-tokens: '4000'
        thinking-budget: '2000'
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `anthropic-api-key` | Anthropic API key for Claude access | ✅ | - |
| `github-token` | GitHub token for API access | ❌ | `${{ github.token }}` |
| `model` | Claude model to use | ❌ | `claude-sonnet-4-20250514` |
| `max-tokens` | Maximum tokens for response | ❌ | `4000` |
| `thinking-budget` | Thinking budget for extended reasoning | ❌ | `2000` |

## Outputs

| Output | Description |
|--------|-------------|
| `review-posted` | Whether a review was posted |
| `has-changes` | Whether code changes were suggested |

## Comment Commands

### Review Mode
- `@claude review this code` - General code analysis
- `@claude check for security issues` - Security-focused review
- `@claude analyze the logic` - Logic and flow analysis

### Propose Changes Mode
- `@claude fix the bug` - Bug fix suggestions
- `@claude refactor this function` - Refactoring recommendations
- `@claude optimize performance` - Performance improvements

## Setup Requirements

1. **API Key**: Add `ANTHROPIC_API_KEY` to repository secrets
2. **Permissions**: Ensure workflow has `pull-requests: write` and `issues: write`
3. **Model Access**: Requires Claude 4 Sonnet access (included in Teams/Max plans)

## Security

- API keys stored securely in GitHub secrets
- No code data retained by Claude
- Temporary files cleaned up automatically
- All communications encrypted (HTTPS/TLS)

## Cost Considerations

- Uses Claude 4 Sonnet: ~$3 input / $15 output per million tokens
- Typical PR review: $0.10-$0.50 depending on code size
- Extended thinking adds reasoning cost but improves quality

## Troubleshooting

**Action not triggering:**
- Check workflow permissions include `pull-requests: write`
- Verify `ANTHROPIC_API_KEY` is set in repository secrets
- Ensure comment contains `@claude` mention

**API errors:**
- Check API key has sufficient credits
- Verify you're using a supported Claude model
- Check rate limits (10 requests/minute default)

**No response posted:**
- Check GitHub token permissions
- Verify PR number is correctly detected
- Look for errors in Action logs