# Development Plan: GitHub Issues Support for Claude Code Review Action

## Overview

Add standalone GitHub issues support to the Claude Code Review Action, enabling `@claude` commands in issue contexts for planning and discussion without requiring PR file analysis.

## Current State

### ✅ Working Features:
- **PR Comments**: `@claude` triggers in PR comment contexts
- **Case-insensitive Detection**: `@claude` or `@Claude` recognition
- **Auto-review**: Automatic analysis on PR open/update
- **Comment Formatting**: Proper markdown display (no ToolUseBlock issues)

### ❌ Missing Features:
- **Standalone Issues**: `@claude` commands in issue-only contexts
- **Issue Comments**: Comments on standalone issues (non-PR)
- **Planning Mode**: Discussion without file analysis requirements

## Technical Analysis

### Root Cause
The current action expects PR context and fails on issue events because:

1. **PR Dependency**: `self.pr = self.repo.get_pull(self.pr_number)` fails for issues
2. **File Analysis**: `get_changed_files()` expects PR file diffs
3. **Context Building**: `get_pr_context()` requires PR metadata
4. **Workflow Triggers**: Missing `issues` event type support

### Failed Test Cases
- **Issue Creation**: `@claude help me plan a refactoring strategy` (in issue body) ❌
- **Issue Comment**: `@claude review the current vis_server.py architecture` ❌
- **Planning Mode**: Discussion without code files ❌

## Implementation Plan

### Phase 1: Core Issue Detection

#### 1.1 Update Workflow Triggers
**File**: `actions/claude-code-review/action.yml`

Add issue event support:
```yaml
on:
  issues:
    types: [opened]
  issue_comment:
    types: [created]
  pull_request:
    types: [opened, synchronize]
```

Update trigger conditions:
```yaml
if: |
  github.event_name == 'pull_request' ||
  (github.event_name == 'issue_comment' && 
   (contains(github.event.comment.body, '@claude') || 
    contains(github.event.comment.body, '@Claude'))) ||
  (github.event_name == 'issues' &&
   (contains(github.event.issue.body, '@claude') ||
    contains(github.event.issue.body, '@Claude')))
```

#### 1.2 Environment Variable Updates
Add issue context detection:
```bash
GITHUB_EVENT_NAME=issues  # or issue_comment
GITHUB_REPOSITORY=openmotionai/oma-kineticos
PR_NUMBER=9  # Actually issue number in issue mode
COMMAND="help me plan a refactoring strategy"
ACTION_TYPE=plan
```

### Phase 2: Code Modifications

#### 2.1 Update ClaudeReviewer.__init__()
**File**: `actions/claude-code-review/claude_reviewer.py`

Add issue mode detection:
```python
def __init__(self):
    # Existing validation...
    
    # Add issue mode detection
    self.event_name = os.environ.get('GITHUB_EVENT_NAME')
    self.is_issue_mode = self.event_name in ['issues', 'issue_comment']
    
    try:
        # Initialize based on context
        if self.is_issue_mode:
            # For issues, pr_number is actually issue_number
            self.issue = self.repo.get_issue(self.pr_number)
            self.pr = None
            
            # Check if issue comment is on a PR-linked issue
            if self.event_name == 'issue_comment':
                # If issue has pull_request link, it's a PR comment
                if hasattr(self.issue, 'pull_request') and self.issue.pull_request:
                    self.is_issue_mode = False
                    self.pr = self.repo.get_pull(self.pr_number)
        else:
            # Existing PR logic
            self.pr = self.repo.get_pull(self.pr_number)
            self.issue = None
    except Exception as e:
        raise RuntimeError(f"Failed to initialize context: {e}")
```

#### 2.2 Update get_changed_files()
Handle issue mode with no files:
```python
def get_changed_files(self) -> List[Dict]:
    """Get list of files changed in the PR."""
    if self.is_issue_mode:
        return []  # No files to analyze in issue-only mode
    
    # Existing PR file logic...
```

#### 2.3 Update get_pr_context()
Add issue context support:
```python
def get_pr_context(self) -> str:
    """Build context about the PR/Issue for Claude."""
    if self.is_issue_mode:
        return self.get_issue_context()
    
    # Existing PR context logic...

def get_issue_context(self) -> Tuple[str, List[Dict]]:
    """Build context for issue-only scenarios."""
    context = f"""
# Issue Context
**Issue #{self.issue.number}**: {self.issue.title}
**Description**: {self.issue.body or 'No description provided'}
**State**: {self.issue.state}
**Created**: {self.issue.created_at}

## Current Request:
{self.command}

## Context:
This is a planning/discussion request without specific code files to analyze.
Focus on strategic thinking, architectural guidance, and actionable recommendations.
"""
    return context, []
```

#### 2.4 Update analyze_with_claude()
Handle issue-only scenarios:
```python
def analyze_with_claude(self, context: str, changed_files: List[Dict]) -> Tuple[str, List[Dict]]:
    """Send context to Claude for analysis."""
    
    # Update system prompt based on mode
    if self.is_issue_mode:
        if self.action_type == 'plan':
            system_prompt = """You are a senior software engineer helping with strategic planning.
This is a PLANNING session for an issue discussion - do NOT implement any changes.

Focus on:
- 🎯 **Strategic thinking**: What are the key considerations?
- 📋 **Planning**: What approach would be most effective?
- ⚖️ **Prioritization**: What should be tackled first?
- 🤔 **Discussion**: Ask clarifying questions if needed
- 📝 **Documentation**: Outline the approach and next steps

Provide thoughtful guidance without code implementations."""
        else:
            system_prompt = """You are a senior software engineer providing guidance on an issue.
This is a DISCUSSION context - provide strategic advice and recommendations.

Focus on architectural guidance, best practices, and actionable next steps.
Ask clarifying questions if more context is needed."""
    else:
        # Existing PR system prompts...
    
    # Build message content
    if self.is_issue_mode:
        message_content = context  # No file contents for issues
    else:
        # Existing PR message building with file contents...
```

### Phase 3: Testing Strategy

#### 3.1 Test Cases
**Repository**: `openmotionai/oma-kineticos`
**Test Issue**: #9 (already created)

1. **Issue Creation Test**:
   ```
   Title: "Test Claude integration for standalone issues"
   Body: "@claude help me plan a refactoring strategy for the visualization server components"
   Expected: Planning response without file analysis
   ```

2. **Issue Comment Test**:
   ```
   Comment: "@claude discuss architecture improvements for better testability"
   Expected: Strategic guidance response
   ```

3. **Case Sensitivity Test**:
   ```
   Comment: "@Claude plan modular visualization components"
   Expected: Proper trigger detection and response
   ```

#### 3.2 Validation Criteria
✅ Issue creation with `@claude` triggers workflow
✅ Issue comments with `@claude` get responses
✅ Planning mode works without file requirements
✅ Proper error handling for edge cases
✅ Backward compatibility with PR functionality
✅ No ToolUseBlock formatting issues

### Phase 4: Error Handling

#### 4.1 Edge Cases
- Issues without `@claude` commands (should not trigger)
- Malformed issue content
- API rate limiting
- Missing permissions

#### 4.2 Graceful Degradation
```python
def handle_issue_mode_errors(self):
    """Handle common issue mode errors gracefully."""
    try:
        if not self.issue:
            return "Error: Could not access issue context"
        
        if not self.command:
            return "Error: No @claude command detected in issue"
            
        # Continue with analysis...
    except Exception as e:
        return f"Issue analysis failed: {str(e)}"
```

## Implementation Priority

1. **High Priority**: Issue mode detection and basic context handling
2. **Medium Priority**: Planning mode system prompts and responses
3. **Low Priority**: Advanced error handling and edge cases

## Success Metrics

- ✅ Issue #9 in oma-kineticos responds to `@claude` commands
- ✅ Planning discussions work without file analysis
- ✅ No regression in existing PR functionality
- ✅ Proper error messages for unsupported scenario
