# OMA GitHub Actions

Reusable GitHub Actions for OMA development workflows.

## Available Actions

### 🤖 Claude Code Review
AI-powered code review using Claude 4 Sonnet with extended thinking.

```yaml
- uses: openmotionai/oma-github-actions/actions/claude-code-review@main
  with:
    anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

**Features:**
- High-priority security and bug detection
- Concise, actionable feedback
- Support for `@claude` comments on PRs
- Extended thinking for complex analysis

## Usage

### Quick Setup
1. Add `ANTHROPIC_API_KEY` to your repository secrets
2. Create `.github/workflows/claude-review.yml`:

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
        github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Comment-Based Reviews
- `@claude review this code` - General code review
- `@claude fix the bug` - Specific improvement suggestions
- `@claude check security` - Security-focused analysis

## Development

This repository contains multiple GitHub Actions for the OMA ecosystem. Each action is self-contained in the `actions/` directory.

## License

MIT License - Open Source