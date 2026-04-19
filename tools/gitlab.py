import json
import os
import re
from pathlib import Path

import gitlab

SOURCE_EXTENSIONS = {".go", ".ts", ".tsx", ".js", ".jsx", ".py"}


def score_match(
    *,
    query: str,
    repo_name: str,
    file_path: str,
    snippet: str,
    question_type: str = "usage",
) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    query_lower = query.lower()
    repo_lower = repo_name.lower()
    path_lower = file_path.lower()
    snippet_lower = snippet.lower()
    ext = Path(file_path).suffix.lower()

    if query_lower in snippet_lower:
        score += 60
        reasons.append("exact query match in snippet")
    else:
        query_parts = [part for part in query_lower.replace("/", " ").replace(".", " ").split() if part]
        partial_hits = sum(1 for part in query_parts if part in snippet_lower)
        if partial_hits > 0:
            score += min(partial_hits * 10, 30)
            reasons.append(f"{partial_hits} partial query match(es) in snippet")

    if question_type == "ui_usage":
        if repo_lower == "frontend":
            score += 25
            reasons.append("frontend repo preferred for UI usage")
        elif repo_lower == "client":
            score += 15
            reasons.append("client repo also relevant for UI/API usage")
    elif question_type == "endpoint_definition":
        if repo_lower == "backend":
            score += 25
            reasons.append("backend repo preferred for endpoint definition")
    else:
        if repo_lower in {"frontend", "backend", "client"}:
            score += 10
            reasons.append("known application repo")

    if ext in SOURCE_EXTENSIONS:
        score += 15
        reasons.append(f"source file type {ext}")
    else:
        score -= 10
        reasons.append(f"less useful file type {ext or '[no extension]'}")

    noisy_path_tokens = ["test", "spec", "mock", "fixture", "snapshot", "docs", "dist", "build"]
    noisy_hits = [token for token in noisy_path_tokens if token in path_lower]
    if noisy_hits:
        score -= 15
        reasons.append(f"likely non-production path: {', '.join(noisy_hits)}")

    usage_patterns = ["(", "api.", "apiName.", "operationId", "fetch(", "axios.", "useQuery", "useMutation"]
    matched_patterns = [p for p in usage_patterns if p.lower() in snippet_lower]
    if matched_patterns:
        score += 15
        reasons.append("snippet looks like real code usage")

    return score, reasons


def rank_matches(matches: list[dict], *, query: str, question_type: str) -> list[dict]:
    ranked = []
    for match in matches:
        score, reasons = score_match(
            query=query,
            repo_name=match.get("repo_name", ""),
            file_path=match.get("filename", ""),
            snippet=match.get("data", ""),
            question_type=question_type,
        )
        ranked.append({**match, "score": score, "reasons": reasons})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def load_project_definitions() -> list[dict]:
    path = os.getenv("PROJECT_DEFINITIONS_FILE", "config/project_definitions_example.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_PROJECT_DEFINITIONS = load_project_definitions()


def _normalize_tokens(text: str) -> list[str]:
    if not text:
        return []
    raw_parts = re.findall(r"[A-Za-z0-9_/-]+", text)
    tokens = set()
    for part in raw_parts:
        tokens.add(part.lower())
        for sub in re.split(r"[_/\-.]+", part):
            if sub:
                tokens.add(sub.lower())
        camel = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", part)
        for c in camel:
            if c:
                tokens.add(c.lower())
    return [t for t in tokens if t]


def _score_project(project: dict, query: str, endpoint_lookup: bool = False) -> int:
    score = 0
    q = query.lower()
    tokens = set(_normalize_tokens(query))
    name = (project.get("name") or "").lower()
    description = (project.get("description") or "").lower()
    keywords = [kw.lower() for kw in project.get("keywords", [])]
    if endpoint_lookup:
        if name.endswith("-api"):
            score += 10
        else:
            score -= 20
    for token in tokens:
        if token in name:
            score += 12
        if token in description:
            score += 4
    for kw in keywords:
        if kw in q:
            score += 15
        else:
            kw_tokens = set(_normalize_tokens(kw))
            overlap = len(tokens & kw_tokens)
            score += overlap * 5
    return score


_instances = {
    "proxy": gitlab.Gitlab(
        os.getenv("GITLAB_PROXY_URL", "https://gitlab.dev.dyl.com"),
        private_token=os.getenv("GITLAB_PROXY_TOKEN", ""),
    ),
    "client": gitlab.Gitlab(
        os.getenv("GITLAB_CLIENT_URL", ""),
        private_token=os.getenv("GITLAB_CLIENT_TOKEN", ""),
    ),
}

_SOURCE_PARAM = {
    "source": {
        "type": "string",
        "enum": ["proxy", "client"],
        "description": "Which GitLab to query — 'proxy' for BE/FE code, 'client' for client-side code",
    }
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_project",
            "description": "Find the most relevant GitLab projects by scoring against name, description, and keywords. Use this when the correct project_id is not obvious from the known project list. Set endpoint_lookup=true when searching for endpoint definitions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Feature, entity, operationId, or topic to search for"},
                    "endpoint_lookup": {"type": "boolean", "description": "Set true when looking for a project that defines backend endpoints — boosts -api projects"},
                    "limit": {"type": "integer", "description": "Max number of results to return (default 3)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project",
            "description": "Fetch a single GitLab project by its numeric ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "Numeric GitLab project ID"},
                    **_SOURCE_PARAM,
                },
                "required": ["project_id", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "List all accessible GitLab projects, optionally filtered by group name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_name": {"type": "string", "description": "Group name to filter projects (optional)"},
                    **_SOURCE_PARAM,
                },
                "required": ["source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_merge_requests",
            "description": "Search for merge requests by title across all accessible projects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Title or partial title to search for"},
                    **_SOURCE_PARAM,
                },
                "required": ["query", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_merge_requests",
            "description": "List all open merge requests for a given GitLab project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "Numeric GitLab project ID"},
                    **_SOURCE_PARAM,
                },
                "required": ["project_id", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_merge_request",
            "description": "Fetch a single merge request and its code diffs by project ID and MR IID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "Numeric GitLab project ID"},
                    "merge_request_iid": {"type": "integer", "description": "Merge request IID"},
                    **_SOURCE_PARAM,
                },
                "required": ["project_id", "merge_request_iid", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search code in a GitLab project using a query string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "Numeric GitLab project ID"},
                    "search_term": {"type": "string", "description": "Term to filter search results"},
                    "ref": {"type": "string", "description": "Branch, tag, or commit to search in. Optional; defaults to the project's default branch."},
                    "question_type": {"type": "string", "enum": ["usage", "ui_usage", "endpoint_definition"], "description": "Type of question — affects result ranking. Use 'ui_usage' for UI/frontend questions, 'endpoint_definition' for backend endpoint questions, 'usage' otherwise."},
                    **_SOURCE_PARAM,
                },
                "required": ["project_id", "search_term", "source"],
            },
        },

    },
    {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a text file from a GitLab repository. If ref is omitted, use the default branch.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "Numeric GitLab project ID"},
                "file_path": {"type": "string", "description": "Path to the file in the repository"},
                "ref": {"type": "string", "description": "Branch, tag, or commit. Optional; defaults to the project's HEAD"},
                **_SOURCE_PARAM,
            },
            "required": ["project_id", "file_path", "source"],
        },
    },
    },
    {
        "type": "function",
        "function": {
            "name": "list_repository_tree",
            "description": "List files and directories in a GitLab repository at a given path and ref.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "Numeric GitLab project ID"},
                    "path": {"type": "string", "description": "Directory path to list (optional; defaults to root)"},
                    "ref": {"type": "string", "description": "Branch, tag, or commit. Optional; defaults to the project's HEAD"},
                    "recursive": {"type": "boolean", "description": "Whether to list all subdirectories recursively (optional; defaults to false)"},
                    **_SOURCE_PARAM,
                },
                "required": ["project_id", "source"],
            },
        },
    }
]


def _gl(input: dict) -> gitlab.Gitlab:
    return _instances[input.get("source", "proxy")]


def handle_get_project(input: dict) -> dict:
    project = _gl(input).projects.get(input["project_id"])
    return {"id": project.id, "name": project.name, "web_url": project.web_url}


def handle_list_projects(input: dict) -> list:
    if group_name := input.get("group_name"):
        group = _gl(input).groups.get(group_name)
        projects = group.projects.list(iterator=True)
    else:
        projects = _gl(input).projects.list(iterator=True)
    return [{"id": p.id, "name": p.name, "url": p.web_url, "description": p.description} for p in projects]


def handle_search_merge_requests(input: dict) -> list:
    mrs = _gl(input).mergerequests.list(search=input["query"], iterator=True)
    return [{"iid": mr.iid, "title": mr.title, "project_id": mr.project_id} for mr in mrs]


def handle_list_merge_requests(input: dict) -> list:
    project = _gl(input).projects.get(input["project_id"])
    mrs = project.mergerequests.list(state="opened", iterator=True)
    return [{"iid": mr.iid, "title": mr.title, "state": mr.state} for mr in mrs]


def handle_get_merge_request(input: dict) -> dict:
    project = _gl(input).projects.get(input["project_id"])
    mr = project.mergerequests.get(input["merge_request_iid"])
    diffs = mr.diffs.list()
    return {
        "iid": mr.iid,
        "title": mr.title,
        "description": mr.description,
        "diffs": [{"old_path": d.old_path, "new_path": d.new_path, "diff": d.diff} for d in diffs],
    }


def handle_search_code(input: dict) -> list:
    project = _gl(input).projects.get(input["project_id"])
    search_kwargs = {"scope": "blobs", "search": input["search_term"]}
    if input.get("ref"):
        search_kwargs["ref"] = input["ref"]
    results = project.search(**search_kwargs)
    matches = [{"filename": r["filename"], "ref": r["ref"], "data": r["data"], "repo_name": project.name} for r in results]
    question_type = input.get("question_type", "usage")
    ranked = rank_matches(matches, query=input["search_term"], question_type=question_type)
    return ranked[:10]


def handle_read_file(input: dict) -> str:
    project = _gl(input).projects.get(input["project_id"])
    kwargs = {"file_path": input["file_path"]}
    if input.get("ref"):
        kwargs["ref"] = input["ref"]
    raw_content = project.files.raw(**kwargs)
    try:
        return raw_content.decode("utf-8")
    except UnicodeDecodeError:
        return f"[binary or non-UTF-8 file: {input['file_path']}]"

def list_repository_tree(input: dict) -> list:
    project = _gl(input).projects.get(input["project_id"])

    tree = project.repository_tree(
        path=input.get("path"),
        ref=input.get("ref", "HEAD"),
        recursive=input.get("recursive", False),
    )

    return [
        {
            "path": item["path"],
            "type": item["type"],
        }
        for item in tree
    ]

def handle_lookup_project(input: dict) -> list:
    query = input["query"]
    endpoint_lookup = input.get("endpoint_lookup", False)
    limit = input.get("limit", 3)
    scored = []
    for p in _PROJECT_DEFINITIONS:
        score = _score_project(p, query, endpoint_lookup=endpoint_lookup)
        if score > 0:
            scored.append({
                "score": score,
                "project_id": p["project_id"],
                "name": p["name"],
                "source": p["source"],
                "description": p.get("description"),
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


TOOL_HANDLERS = {
    "lookup_project": handle_lookup_project,
    "get_project": handle_get_project,
    "list_projects": handle_list_projects,
    "search_merge_requests": handle_search_merge_requests,
    "list_merge_requests": handle_list_merge_requests,
    "list_repository_tree": list_repository_tree,
    "get_merge_request": handle_get_merge_request,
    "search_code": handle_search_code,
    "read_file": handle_read_file
}
