#!/usr/bin/env python3
"""
Claude Code Reviewer Script
Integrates with GitHub Actions to provide AI-powered code reviews and fixes.
"""

import os
import sys
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import anthropic
    from github import Github
    import httpx
except ImportError as e:
    print(f"Error: Required package not installed: {e}")
    print("Please ensure anthropic, PyGithub, and httpx are installed in the workflow environment")
    sys.exit(1)


class ClaudeReviewer:
    def __init__(self):
        # Validate required environment variables
        required_vars = [
            'ANTHROPIC_API_KEY', 'GITHUB_TOKEN', 'GITHUB_REPOSITORY',
            'PR_NUMBER', 'COMMAND', 'ACTION_TYPE'
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
            self.mcp_server_url = os.environ.get('MCP_SERVER_URL', 'http://localhost:3000')

            # Add issue mode detection
            self.event_name = os.environ.get('GITHUB_EVENT_NAME')
            self.is_issue_mode = self.event_name in ['issues', 'issue_comment']

            self.repo = self.github_client.get_repo(self.repo_name)

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
                        self.issue = None
            else:
                # Existing PR logic
                self.head_ref = os.environ.get('HEAD_REF', 'main')
                self.base_ref = os.environ.get('BASE_REF', 'main')
                self.pr = self.repo.get_pull(self.pr_number)
                self.issue = None

        except ValueError as e:
            if "invalid literal for int()" in str(e):
                raise ValueError(f"PR_NUMBER must be a valid integer: {os.environ.get('PR_NUMBER')}")
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ClaudeReviewer: {e}")

    def get_github_tools(self) -> List[Dict]:
        """Define GitHub tools for Claude to use via tool calling."""
        tools = [
            {
                "name": "get_pr_comments",
                "description": "Get all comments on the current PR for conversation context",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_pr_files",
                "description": "Get files changed in the current PR",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "create_pr_comment",
                "description": "Create a comment on the current PR",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "body": {
                            "type": "string",
                            "description": "The comment body"
                        }
                    },
                    "required": ["body"]
                }
            }
        ]

        # Add file modification tools for fix mode
        if self.action_type == 'fix':
            tools.append({
                "name": "modify_file",
                "description": "Modify a file with new content to fix issues",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to modify"
                        },
                        "new_content": {
                            "type": "string",
                            "description": "The complete new content for the file"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of what was fixed"
                        }
                    },
                    "required": ["file_path", "new_content", "description"]
                }
            })

        return tools

    def handle_tool_call(self, tool_name: str, tool_input: Dict) -> Dict:
        """Handle tool calls from Claude."""
        try:
            if tool_name == "get_pr_comments":
                comments = []
                for comment in self.pr.get_issue_comments():
                    comments.append({
                        "id": comment.id,
                        "user": comment.user.login,
                        "body": comment.body,
                        "created_at": comment.created_at.isoformat(),
                        "updated_at": comment.updated_at.isoformat()
                    })
                return {"comments": comments}

            elif tool_name == "get_pr_files":
                return {"files": self.get_changed_files()}

            elif tool_name == "create_pr_comment":
                comment = self.pr.create_issue_comment(tool_input["body"])
                return {
                    "success": True,
                    "comment_id": comment.id,
                    "url": comment.html_url
                }

            elif tool_name == "modify_file":
                # Store file modifications for later application
                if not hasattr(self, 'file_modifications'):
                    self.file_modifications = []

                self.file_modifications.append({
                    "path": tool_input["file_path"],
                    "content": tool_input["new_content"],
                    "description": tool_input["description"]
                })

                return {
                    "success": True,
                    "message": f"File modification queued: {tool_input['file_path']}",
                    "description": tool_input["description"]
                }

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    def get_changed_files(self) -> List[Dict]:
        """Get list of files changed in the PR."""
        if self.is_issue_mode:
            return []  # No files to analyze in issue-only mode

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
    
    def get_previous_claude_comments(self) -> List[Dict]:
        """Get all previous @claude comments from this PR for conversation context."""
        comments = []
        try:
            # Get all comments on the PR
            pr_comments = self.pr.get_issue_comments()

            for comment in pr_comments:
                comment_body = comment.body
                # Check if this is a Claude comment (contains @claude or @Claude)
                if '@claude' in comment_body.lower() or '@Claude' in comment_body:
                    # Extract the command after @claude
                    import re
                    claude_match = re.search(r'@[Cc]laude\s+(.+)', comment_body)
                    if claude_match:
                        command = claude_match.group(1).strip()
                        comments.append({
                            'created_at': comment.created_at,
                            'user': comment.user.login,
                            'command': command,
                            'full_body': comment_body
                        })
        except Exception as e:
            print(f"Warning: Could not fetch previous comments: {e}")

        # Sort by creation time
        comments.sort(key=lambda x: x['created_at'])
        return comments

    def get_pr_context(self) -> Tuple[str, List[Dict]]:
        """Build context about the PR/Issue for Claude, including conversation history."""
        if self.is_issue_mode:
            return self.get_issue_context()

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

        # Add conversation history for fix actions
        if self.action_type == 'fix':
            previous_comments = self.get_previous_claude_comments()
            if previous_comments:
                context += f"\n## Previous Conversation History:\n"
                for i, comment in enumerate(previous_comments[:-1], 1):  # Exclude current comment
                    context += f"{i}. **{comment['user']}**: @claude {comment['command']}\n"
                context += f"\n*This conversation history should inform your implementation decisions.*\n"

        context += f"\n## Current Request:\n{self.command}\n"

        return context, changed_files

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
    
    def analyze_with_claude(self, context: str, changed_files: List[Dict]) -> Tuple[str, List[Dict]]:
        """Send code to Claude for analysis."""
        
        # Build the prompt based on action type
        if self.action_type == 'fix':
            system_prompt = """You are a senior software engineer implementing code fixes based on a conversation history.

IMPORTANT: You have been having a conversation about this PR. Based on the conversation history and current request:

1. **Prioritize HIGH-IMPACT issues**: Security vulnerabilities, bugs, breaking changes
2. **Only implement changes that were specifically discussed or requested**
3. **Reference the conversation context** in your implementation decisions
4. **Be selective** - don't implement everything, focus on what was actually requested

Your workflow:
1. Use get_pr_files tool to examine the current code
2. For each file that needs fixing, use modify_file tool with the complete corrected content
3. Use create_pr_comment tool to create a summary of what was fixed

Focus on implementing the specific fixes mentioned in the conversation. Be precise and only change what's necessary to address the identified issues.

After making all file modifications, create a summary comment explaining what was fixed."""

        elif self.action_type == 'plan':
            if self.is_issue_mode:
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
                system_prompt = """You are a senior software engineer helping to plan code improvements. This is a PLANNING session - do NOT implement any changes.

Focus on:
- 🎯 **Strategic thinking**: What are the key issues and opportunities?
- 📋 **Planning**: What changes would be most beneficial?
- ⚖️ **Prioritization**: What should be tackled first?
- 🤔 **Discussion**: Ask clarifying questions if needed
- 📝 **Documentation**: Outline the approach and considerations

This is a conversation - engage with the user to understand their goals and help them think through the best approach. Do NOT provide code implementations in planning mode."""
        else:
            if self.is_issue_mode:
                system_prompt = """You are a senior software engineer providing guidance on an issue.
This is a DISCUSSION context - provide strategic advice and recommendations.

Focus on architectural guidance, best practices, and actionable next steps.
Ask clarifying questions if more context is needed."""
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

        # Build message content
        if self.is_issue_mode:
            message_content = context  # No file contents for issues
        else:
            # Include file contents in the message for PRs
            message_content = context + "\n\n## File Contents:\n\n"

            for file in changed_files:
                message_content += f"### {file['filename']}\n\n"
                if file['patch']:
                    message_content += f"**Diff:**\n```diff\n{file['patch']}\n```\n\n"
                message_content += f"**Full Content:**\n```{self.get_file_extension(file['filename'])}\n{file['content']}\n```\n\n"
        
        try:
            # Get configuration from environment
            model = os.environ.get('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
            max_tokens = int(os.environ.get('MAX_TOKENS', '4000'))

            # Create message with tool support
            messages = [{
                "role": "user",
                "content": message_content
            }]

            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0.1,
                system=system_prompt,
                messages=messages,
                tools=self.get_github_tools()
            )

            # Handle tool calls if present
            if response.stop_reason == "tool_use":
                print("Claude made tool calls, processing...")
                # Process tool calls
                tool_results = []

                for content_block in response.content:
                    if content_block.type == "tool_use":
                        print(f"Processing tool call: {content_block.name}")
                        tool_result = self.handle_tool_call(
                            content_block.name,
                            content_block.input
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": json.dumps(tool_result)
                        })

                # Continue conversation with tool results
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                print("Getting Claude's final response after tool calls...")
                # Get final response with explicit prompt for analysis
                final_response = self.anthropic_client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=0.1,
                    system=system_prompt,
                    messages=messages,
                    tools=self.get_github_tools()
                )

                # Handle potential additional tool calls in final response
                if final_response.stop_reason == "tool_use":
                    print("Claude made additional tool calls in final response, processing...")
                    # Process additional tool calls if needed
                    additional_tool_results = []
                    for content_block in final_response.content:
                        if content_block.type == "tool_use":
                            print(f"Processing additional tool call: {content_block.name}")
                            tool_result = self.handle_tool_call(
                                content_block.name,
                                content_block.input
                            )
                            additional_tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps(tool_result)
                            })

                    # Get truly final response
                    messages.append({"role": "assistant", "content": final_response.content})
                    messages.append({"role": "user", "content": additional_tool_results})

                    final_response = self.anthropic_client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=0.1,
                        system=system_prompt,
                        messages=messages
                    )

                # Use the final response for text extraction
                response = final_response
                print(f"Final response stop reason: {response.stop_reason}")

            # Extract text content from response (handles thinking mode)
            text_content = ""
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'text':
                    text_content = block.text
                    break

            print(f"Extracted text content length: {len(text_content) if text_content else 0}")

            # Handle case where no text content was extracted
            if not text_content and response.content:
                print("No text content found, analyzing response structure...")

                # Debug: print response structure
                for i, block in enumerate(response.content):
                    print(f"Block {i}: type={getattr(block, 'type', 'unknown')}")

                # Check if response contains only tool use blocks
                has_only_tool_blocks = all(
                    hasattr(block, 'type') and block.type == 'tool_use'
                    for block in response.content
                )

                if has_only_tool_blocks:
                    # This shouldn't happen after tool call completion, but handle gracefully
                    print("Warning: Final response contains only tool blocks")
                    if self.is_issue_mode:
                        text_content = "I've gathered information about your request. Please let me know if you need more specific analysis or have additional questions."
                    else:
                        text_content = "I've analyzed the code changes. Please let me know if you need more specific feedback or have questions."
                else:
                    # Try to extract text from first block as fallback
                    first_block = response.content[0] if response.content else None
                    if first_block and hasattr(first_block, 'text'):
                        text_content = first_block.text
                    else:
                        text_content = "Analysis completed. Please let me know if you need more specific information."
            
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
        
        # Get PR/Issue context and changed files
        context, changed_files = self.get_pr_context()

        if not changed_files and not self.is_issue_mode:
            print("No changed files found in PR")
            self.save_review_output("No files to review in this PR.")
            return
        
        if self.is_issue_mode:
            print("Analyzing issue context for planning/discussion...")
        else:
            print(f"Analyzing {len(changed_files)} changed files...")

        # Analyze with Claude
        claude_response, _ = self.analyze_with_claude(context, changed_files)
        
        # Save the review for comment posting
        self.save_review_output(claude_response)
        
        # Handle different action types
        if self.action_type == 'fix':
            # Check if Claude made file modifications via tool calls
            if hasattr(self, 'file_modifications') and self.file_modifications:
                print(f"Claude made {len(self.file_modifications)} file modifications via tool calls")
                files_changed = False

                for modification in self.file_modifications:
                    try:
                        # Write the new content
                        with open(modification['path'], 'w', encoding='utf-8') as f:
                            f.write(modification['content'])

                        print(f"Modified: {modification['path']} - {modification['description']}")
                        files_changed = True

                    except Exception as e:
                        print(f"Error modifying {modification['path']}: {e}")

                if files_changed:
                    self.set_github_output('has_changes', 'true')
                    print("✅ Changes applied successfully via tool calls")
                    print("Files will be committed and PR will be created by workflow")
                else:
                    self.set_github_output('has_changes', 'false')
                    print("❌ No changes were applied")
            else:
                # Fallback to old JSON parsing method
                changes = self.extract_file_changes(claude_response)

                if changes and changes.get('has_changes', False):
                    print("Claude suggested changes via JSON, applying them...")
                    files_changed = self.apply_file_changes(changes)

                    if files_changed:
                        self.set_github_output('has_changes', 'true')
                        print("✅ Changes applied successfully via JSON")
                        print("Files will be committed and PR will be created by workflow")
                    else:
                        self.set_github_output('has_changes', 'false')
                        print("❌ No changes were applied")
                else:
                    self.set_github_output('has_changes', 'false')
                    print("Claude did not suggest any specific file changes")

        elif self.action_type in ['plan', 'review']:
            # For planning and review, never create PRs - just provide analysis
            self.set_github_output('has_changes', 'false')
            print(f"✅ {self.action_type.title()} completed - no changes applied")

        else:
            # Fallback for unknown action types
            self.set_github_output('has_changes', 'false')
            print(f"Unknown action type: {self.action_type}")
        
        print("Claude Reviewer completed")


if __name__ == "__main__":
    try:
        reviewer = ClaudeReviewer()
        reviewer.run()
    except Exception as e:
        print(f"Error in Claude Reviewer: {e}")
        sys.exit(1)