#!/usr/bin/env python3
"""
Claude Code Reviewer Script
Integrates with GitHub Actions to provide AI-powered code reviews and fixes.
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import anthropic
    from github import Github
except ImportError as e:
    print(f"Error: Required package not installed: {e}")
    print("Please ensure anthropic and PyGithub are installed in the workflow environment")
    sys.exit(1)


class ClaudeReviewer:
    def __init__(self):
        # Validate required environment variables
        required_vars = [
            'ANTHROPIC_API_KEY', 'GITHUB_TOKEN', 'GITHUB_REPOSITORY',
            'PR_NUMBER', 'COMMAND', 'ACTION_TYPE', 'HEAD_REF', 'BASE_REF'
        ]
        missing = [var for var in required_vars if not os.environ.get(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
        
        try:
            self.anthropic_client = anthropic.Anthropic(
                api_key=os.environ['ANTHROPIC_API_KEY']
            )
            self.github_client = Github(os.environ['GITHUB_TOKEN'])
            self.repo_name = os.environ['GITHUB_REPOSITORY']
            self.pr_number = int(os.environ['PR_NUMBER'])
            self.command = os.environ['COMMAND']
            self.action_type = os.environ['ACTION_TYPE']
            self.head_ref = os.environ['HEAD_REF']
            self.base_ref = os.environ['BASE_REF']
            
            self.repo = self.github_client.get_repo(self.repo_name)
            self.pr = self.repo.get_pull(self.pr_number)
        except ValueError as e:
            if "invalid literal for int()" in str(e):
                raise ValueError(f"PR_NUMBER must be a valid integer: {os.environ.get('PR_NUMBER')}")
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ClaudeReviewer: {e}")
    
    def get_changed_files(self) -> List[Dict]:
        """Get list of files changed in the PR."""
        changed_files = []
        files = self.pr.get_files()
        
        for file in files:
            if file.status != 'removed':  # Skip removed files
                try:
                    # Read current file content
                    content = self.repo.get_contents(file.filename, ref=self.head_ref)
                    file_content = content.decoded_content.decode('utf-8')
                    
                    changed_files.append({
                        'filename': file.filename,
                        'status': file.status,
                        'additions': file.additions,
                        'deletions': file.deletions,
                        'content': file_content,
                        'patch': file.patch if hasattr(file, 'patch') else None
                    })
                except Exception as e:
                    print(f"Warning: Could not read {file.filename}: {e}")
                    
        return changed_files
    
    def get_pr_context(self) -> str:
        """Build context about the PR for Claude."""
        context = f"""
# Pull Request Context

**PR #{self.pr_number}**: {self.pr.title}
**Branch**: {self.head_ref} → {self.base_ref}
**Description**: {self.pr.body or 'No description provided'}

## Files Changed:
"""
        
        changed_files = self.get_changed_files()
        for file in changed_files:
            context += f"- `{file['filename']}` ({file['status']}, +{file['additions']}/-{file['deletions']})\n"
        
        context += f"\n## User Request:\n{self.command}\n"
        
        return context, changed_files
    
    def analyze_with_claude(self, context: str, changed_files: List[Dict]) -> Tuple[str, List[Dict]]:
        """Send code to Claude for analysis."""
        
        # Build the prompt based on action type
        if self.action_type == 'propose':
            system_prompt = """You are a senior software engineer conducting a code review. The user has requested specific changes, improvements, or modifications to the code. This could include:

- 🔧 **Bug fixes**: Correcting errors and issues
- ♻️ **Refactoring**: Improving code structure and organization  
- ⚡ **Performance**: Optimizing for speed and efficiency
- 🎨 **Style**: Improving code formatting and readability
- ✨ **Enhancement**: Adding features or improving functionality
- 🧹 **Cleanup**: Simplifying and cleaning up code

Analyze the code and provide:
1. A detailed analysis of the requested changes
2. Specific code modifications that address the request
3. Implementation rationale and benefits
4. Any potential risks or considerations

If you can propose specific code changes, provide them in this JSON format at the end:

```json
{
  "has_changes": true,
  "files": [
    {
      "path": "file/path.py",
      "action": "modify",
      "content": "full file content with proposed changes"
    }
  ]
}
```

If no concrete changes can be proposed (e.g., the request is too vague or no improvements are needed), respond with:
```json
{
  "has_changes": false
}
```

Be thoughtful and conservative - only propose changes when they genuinely improve the code."""
        else:
            system_prompt = """You are a senior software engineer conducting a code review. Focus on HIGH-PRIORITY issues only by default:

🚨 **Critical Issues** (always mention):
- Security vulnerabilities 
- Bugs or logical errors
- Breaking changes or API issues

⚠️ **Important Issues** (mention if significant):
- Performance bottlenecks
- Poor error handling
- Architectural concerns

📝 **Style/Minor** (only if explicitly requested):
- Code formatting, naming conventions, minor refactoring

Keep reviews CONCISE - highlight only the most important items unless asked for comprehensive analysis. Be specific and actionable."""

        # Include file contents in the message
        message_content = context + "\n\n## File Contents:\n\n"
        
        for file in changed_files:
            message_content += f"### {file['filename']}\n\n"
            if file['patch']:
                message_content += f"**Diff:**\n```diff\n{file['patch']}\n```\n\n"
            message_content += f"**Full Content:**\n```{self.get_file_extension(file['filename'])}\n{file['content']}\n```\n\n"
        
        try:
            # Get configuration from environment
            model = os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
            max_tokens = int(os.environ.get('MAX_TOKENS', '4000'))
            thinking_budget = int(os.environ.get('THINKING_BUDGET', '2000'))
            
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=1,  # Required to be 1 when thinking is enabled
                thinking={
                    "type": "enabled",
                    "budget_tokens": thinking_budget
                },
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": message_content
                }]
            )
            
            # Extract text content from response (handles thinking mode)
            text_content = ""
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'text':
                    text_content = block.text
                    break
            
            # Fallback to first block if no text block found
            if not text_content and response.content:
                text_content = getattr(response.content[0], 'text', str(response.content[0]))
            
            return text_content, changed_files
            
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return f"Error analyzing code: {e}", []
    
    def get_file_extension(self, filename: str) -> str:
        """Get appropriate language identifier for code blocks."""
        ext = Path(filename).suffix.lower()
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.sh': 'bash',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sql': 'sql',
            '.md': 'markdown',
        }
        return lang_map.get(ext, '')
    
    def extract_file_changes(self, claude_response: str) -> Optional[Dict]:
        """Extract file changes from Claude's response."""
        try:
            # Look for JSON block in response
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', claude_response, re.DOTALL)
            if json_match:
                changes_data = json.loads(json_match.group(1))
                return changes_data
        except Exception as e:
            print(f"Error parsing changes from Claude response: {e}")
        
        return None
    
    def apply_file_changes(self, changes: Dict) -> bool:
        """Apply file changes to the local repository."""
        if not changes.get('has_changes', False):
            return False
        
        files_changed = False
        for file_change in changes.get('files', []):
            file_path = file_change['path']
            
            if file_change['action'] == 'modify':
                try:
                    # Write the new content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(file_change['content'])
                    
                    print(f"Modified: {file_path}")
                    files_changed = True
                    
                except Exception as e:
                    print(f"Error modifying {file_path}: {e}")
            
            elif file_change['action'] == 'create':
                try:
                    # Create directories if needed
                    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write the new file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(file_change['content'])
                    
                    print(f"Created: {file_path}")
                    files_changed = True
                    
                except Exception as e:
                    print(f"Error creating {file_path}: {e}")
        
        return files_changed
    
    def save_review_output(self, claude_response: str):
        """Save Claude's review to a file for GitHub Actions to use."""
        review_content = f"""## 🤖 Claude Code Review

{claude_response}

---
*Claude Code Review Action*"""
        
        # Write review to file accessible by workflow
        # Use process ID to avoid conflicts in concurrent runs
        review_file = f"/tmp/claude_review_{os.getpid()}.md"
        with open(review_file, 'w', encoding='utf-8') as f:
            f.write(review_content)
        
        # Set output for workflow to access
        self.set_github_output('review_file', review_file)
        print(f"Review written to: {review_file}")
    
    def set_github_output(self, key: str, value: str):
        """Set GitHub Actions output variable."""
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/stdout'), 'a') as f:
            f.write(f"{key}={value}\n")
    
    def run(self):
        """Main execution function."""
        print(f"Claude Reviewer starting...")
        print(f"Command: {self.command}")
        print(f"Action type: {self.action_type}")
        
        # Get PR context and changed files
        context, changed_files = self.get_pr_context()
        
        if not changed_files:
            print("No changed files found in PR")
            self.save_review_output("No files to review in this PR.")
            return
        
        print(f"Analyzing {len(changed_files)} changed files...")
        
        # Analyze with Claude
        claude_response, _ = self.analyze_with_claude(context, changed_files)
        
        # Save the review for comment posting
        self.save_review_output(claude_response)
        
        # If this is a propose changes request, try to extract and apply changes
        if self.action_type == 'propose':
            changes = self.extract_file_changes(claude_response)

            if changes and changes.get('has_changes', False):
                print("Claude suggested changes, applying them...")
                files_changed = self.apply_file_changes(changes)

                if files_changed:
                    self.set_github_output('has_changes', 'true')
                    print("✅ Changes applied successfully")
                    print("Files will be committed and PR will be created by workflow")
                else:
                    self.set_github_output('has_changes', 'false')
                    print("❌ No changes were applied")
            else:
                self.set_github_output('has_changes', 'false')
                print("Claude did not suggest any specific file changes")
        else:
            self.set_github_output('has_changes', 'false')
        
        print("Claude Reviewer completed")


if __name__ == "__main__":
    try:
        reviewer = ClaudeReviewer()
        reviewer.run()
    except Exception as e:
        print(f"Error in Claude Reviewer: {e}")
        sys.exit(1)