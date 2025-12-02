"""Agentic code analysis for repository exploration."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from config import get_settings


class CodeAnalysisAgent:
    """Agent for analyzing code repositories with tool use."""

    SYSTEM_PROMPT = """You are a code analysis agent. You have access to a cloned repository and can use tools to explore it.

Your goal is to answer questions about the codebase by:
1. Searching for relevant code patterns using ripgrep
2. Reading specific files to understand implementation details
3. Listing directories to understand project structure
4. Finding function/class definitions

Available tools:
- search_code: Search for patterns in code using ripgrep
- read_file: Read contents of a specific file
- list_directory: List files and directories
- find_definitions: Find function/class definitions matching a pattern

When you have gathered enough information, provide your final answer with:
- Clear explanation of what you found
- Specific file paths and line numbers when referencing code
- Code snippets when relevant

If you cannot find relevant information, say so clearly."""

    def __init__(self, repos_base_path: Optional[str] = None):
        settings = get_settings()
        self.repos_path = Path(repos_base_path or settings.repos_path)
        self.repos_path.mkdir(parents=True, exist_ok=True)
        # Only pass base_url if it's actually set (not empty string)
        base_url = settings.openai_base_url if settings.openai_base_url else None
        self.openai = OpenAI(api_key=settings.openai_api_key, base_url=base_url)
        self.model = settings.openai_model
        self.gitlab_pat = settings.gitlab_pat

    def get_repo_path(self, project_id: int) -> Path:
        """Get the local path for a project repository."""
        return self.repos_path / str(project_id)

    async def ensure_repo_cloned(self, project: Dict) -> Path:
        """Clone or update repository."""
        repo_path = self.get_repo_path(project["gitlab_id"])

        if repo_path.exists():
            # Pull latest changes
            try:
                result = subprocess.run(
                    ["git", "pull", "--ff-only"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired:
                pass
        else:
            # Clone with PAT authentication
            clone_url = project["http_url_to_repo"]
            if clone_url and self.gitlab_pat:
                clone_url = clone_url.replace(
                    "https://", f"https://oauth2:{self.gitlab_pat}@"
                )

            try:
                subprocess.run(
                    ["git", "clone", "--depth=1", clone_url, str(repo_path)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                pass

        return repo_path

    def _validate_path(self, repo_path: Path, file_path: str) -> Optional[Path]:
        """Validate and resolve file path within repo."""
        # Resolve the path
        try:
            full_path = (repo_path / file_path).resolve()
            # Ensure it's within the repo
            if repo_path.resolve() in full_path.parents or full_path == repo_path.resolve():
                return full_path
            # Check if full_path starts with repo_path
            if str(full_path).startswith(str(repo_path.resolve())):
                return full_path
        except Exception:
            pass
        return None

    def _search_code(
        self, repo_path: Path, pattern: str, file_type: Optional[str] = None
    ) -> str:
        """Search code using ripgrep."""
        cmd = ["rg", "--json", "-C", "2", "-m", "20", pattern]

        if file_type:
            type_map = {
                "python": "py",
                "javascript": "js",
                "typescript": "ts",
                "go": "go",
                "rust": "rust",
                "java": "java",
            }
            rg_type = type_map.get(file_type, file_type)
            cmd.extend(["-t", rg_type])

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Parse JSON output for readability
            lines = result.stdout.strip().split("\n")
            matches = []
            current_file = None

            for line in lines:
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        file_path = data["data"]["path"]["text"]
                        line_num = data["data"]["line_number"]
                        text = data["data"]["lines"]["text"].strip()
                        if file_path != current_file:
                            current_file = file_path
                            matches.append(f"\n--- {file_path} ---")
                        matches.append(f"  {line_num}: {text}")
                except json.JSONDecodeError:
                    continue

            return "\n".join(matches) if matches else "No matches found."
        except subprocess.TimeoutExpired:
            return "Search timed out."
        except Exception as e:
            return f"Search error: {str(e)}"

    def _read_file(self, repo_path: Path, file_path: str) -> str:
        """Read file contents."""
        full_path = self._validate_path(repo_path, file_path)
        if not full_path:
            return f"Error: Invalid path - {file_path}"

        if not full_path.exists():
            return f"Error: File not found - {file_path}"

        if not full_path.is_file():
            return f"Error: Not a file - {file_path}"

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            # Limit output size
            if len(content) > 10000:
                content = content[:10000] + "\n... (truncated)"
            return content
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def _list_directory(self, repo_path: Path, dir_path: str = ".") -> str:
        """List directory contents."""
        full_path = self._validate_path(repo_path, dir_path)
        if not full_path:
            return f"Error: Invalid path - {dir_path}"

        if not full_path.exists():
            return f"Error: Directory not found - {dir_path}"

        if not full_path.is_dir():
            return f"Error: Not a directory - {dir_path}"

        try:
            items = []
            for item in sorted(full_path.iterdir()):
                if item.name.startswith("."):
                    continue
                prefix = "[DIR] " if item.is_dir() else "[FILE]"
                items.append(f"{prefix} {item.name}")

            return "\n".join(items) if items else "Empty directory."
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    def _find_definitions(
        self, repo_path: Path, pattern: str, language: Optional[str] = None
    ) -> str:
        """Find function/class definitions."""
        # Build pattern based on language
        search_patterns = [
            f"def {pattern}",
            f"class {pattern}",
            f"function {pattern}",
            f"const {pattern}",
            f"async def {pattern}",
            f"async function {pattern}",
        ]

        all_results = []
        for search_pattern in search_patterns:
            result = self._search_code(repo_path, search_pattern, language)
            if result and "No matches found" not in result:
                all_results.append(result)

        return "\n".join(all_results) if all_results else f"No definitions found for '{pattern}'."

    def _get_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions for OpenAI function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search for patterns in code using ripgrep. Returns matching lines with context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "The search pattern (regex supported)",
                            },
                            "file_type": {
                                "type": "string",
                                "description": "Optional: filter by file type (python, javascript, typescript, go, rust, java)",
                            },
                        },
                        "required": ["pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a specific file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file relative to repository root",
                            },
                        },
                        "required": ["file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List files and directories in a path",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dir_path": {
                                "type": "string",
                                "description": "Directory path relative to repository root (use '.' for root)",
                            },
                        },
                        "required": ["dir_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_definitions",
                    "description": "Find function or class definitions matching a pattern",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Name pattern to search for (partial matches work)",
                            },
                            "language": {
                                "type": "string",
                                "description": "Optional: filter by language",
                            },
                        },
                        "required": ["pattern"],
                    },
                },
            },
        ]

    def _execute_tool(
        self, repo_path: Path, tool_name: str, arguments: Dict[str, Any]
    ) -> str:
        """Execute a tool and return the result."""
        if tool_name == "search_code":
            return self._search_code(
                repo_path, arguments["pattern"], arguments.get("file_type")
            )
        elif tool_name == "read_file":
            return self._read_file(repo_path, arguments["file_path"])
        elif tool_name == "list_directory":
            return self._list_directory(repo_path, arguments.get("dir_path", "."))
        elif tool_name == "find_definitions":
            return self._find_definitions(
                repo_path, arguments["pattern"], arguments.get("language")
            )
        else:
            return f"Unknown tool: {tool_name}"

    async def analyze(self, query: str, project_id: int) -> Dict[str, Any]:
        """Analyze code repository to answer a query."""
        repo_path = self.get_repo_path(project_id)

        if not repo_path.exists():
            return {
                "answer": "Repository has not been cloned. Please index the project first.",
                "tool_calls": [],
            }

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Repository: {repo_path}\n\nQuestion: {query}",
            },
        ]

        tool_calls_made = []
        max_iterations = 10

        for _ in range(max_iterations):
            response = self.openai.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self._get_tools(),
                tool_choice="auto",
            )

            message = response.choices[0].message

            # Check if done (no tool calls)
            if not message.tool_calls:
                return {
                    "answer": message.content or "Unable to find relevant information.",
                    "tool_calls": tool_calls_made,
                }

            # Execute tool calls
            messages.append(message)

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                tool_calls_made.append(
                    {"tool": tool_name, "arguments": arguments}
                )

                result = self._execute_tool(repo_path, tool_name, arguments)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

        return {
            "answer": "Analysis reached maximum iterations. Please try a more specific query.",
            "tool_calls": tool_calls_made,
        }
