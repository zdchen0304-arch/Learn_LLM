"""OpenAI function-calling tool definitions for Task Agent."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ReadArtifact",
            "description": "Read output artifact from a dependency task. Use when you need the output of another task that this task depends on.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID whose output to read (e.g. from dependencies)",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ReadFile",
            "description": "Read a file. Use 'sandbox/...' for files in this task's sandbox (e.g. sandbox/result.txt).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path under sandbox, e.g. sandbox/result.txt or sandbox/data/output.json",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ListFiles",
            "description": "List files/directories under a path. Use 'sandbox/' to discover available files before ReadFile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list. Prefer sandbox paths (e.g. sandbox/ or sandbox/data).",
                        "default": "sandbox/",
                    },
                    "max_entries": {
                        "type": "integer",
                        "description": "Maximum entries to return (default 200, max 500)",
                        "default": 200,
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum traversal depth (default 3, max 8)",
                        "default": 3,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "WriteFile",
            "description": "Write content to a file in this task's sandbox. Path must be under sandbox (e.g. sandbox/notes.txt). Use for intermediate results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path under sandbox, e.g. sandbox/data.json or sandbox/notes.txt",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "RunCommand",
            "description": "Run a shell command inside the local Docker execution container using the current task sandbox as the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run inside Docker, e.g. 'python script.py' or 'ls -la'",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Optional timeout in seconds (default 120)",
                        "default": 120,
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Finish",
            "description": "Submit the final output and complete the task. Call this when output satisfies the output spec. For JSON format pass an object; for Markdown pass a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "output": {
                        "type": "string",
                        "description": "Final output: JSON string or Markdown content. For JSON format, pass a valid JSON string.",
                    },
                },
                "required": ["output"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ListSkills",
            "description": "List available Agent Skills (name and description). Use to discover skills before loading one with LoadSkill.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "LoadSkill",
            "description": "Load a skill's SKILL.md full content into context. Call after ListSkills to get the skill name. The content will be available in the next turn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name (directory name under skills root, e.g. from ListSkills)",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ReadSkillFile",
            "description": "Read a file from a skill's directory (scripts/, references/, assets/). Use after LoadSkill when you need to read a specific file from the skill.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill": {
                        "type": "string",
                        "description": "Skill name (e.g. docx, pptx)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Path relative to skill dir, e.g. scripts/office/unpack.py or references/example.md",
                    },
                },
                "required": ["skill", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "RunSkillScript",
            "description": "Execute a script from a skill. Use for docx/pptx/xlsx validation, conversion, etc. Script runs from skill dir. Use [[sandbox]]/filename in args for sandbox file paths (e.g. [[sandbox]]/output.docx).",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill": {
                        "type": "string",
                        "description": "Skill name (e.g. docx, pptx, xlsx)",
                    },
                    "script": {
                        "type": "string",
                        "description": "Path to script relative to skill dir, e.g. scripts/office/validate.py",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command-line args. Use [[sandbox]]/file.docx for sandbox file paths.",
                    },
                },
                "required": ["skill", "script"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "WebSearch",
            "description": "Search the web for information. Use for research tasks when you need current data, benchmarks, or official documentation. Returns title, URL, and snippet for each result. Prefer WebSearch then WebFetch for key URLs to cite sources.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'FastAPI performance benchmark RPS', 'Django vs Flask comparison 2024')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results to return (default 5, max 10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "WebFetch",
            "description": "Fetch content from a URL. Use after WebSearch to get full page content for citations. Only http/https URLs; no localhost.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL to fetch (e.g. https://fastapi.tiangolo.com)",
                    },
                },
                "required": ["url"],
            },
        },
    },
]
