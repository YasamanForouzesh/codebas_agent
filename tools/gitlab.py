import os

import gitlab

_url = os.getenv("GITLAB_URL", "https://gitlab.dev.dyl.com")
_token = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "")
_gl = gitlab.Gitlab(_url, private_token=_token)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_project",
            "description": "Fetch a single GitLab project by its numeric ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "Numeric GitLab project ID"},
                },
                "required": ["project_id"],
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
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_merge_request_by_name",
            "description": "Search for merge requests by title across all accessible projects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "merge_request_name": {"type": "string", "description": "Title or partial title to search for"},
                },
                "required": ["merge_request_name"],
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
                },
                "required": ["project_id"],
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
                    "merge_request_id": {"type": "integer", "description": "Merge request IID"},
                },
                "required": ["project_id", "merge_request_id"],
            },
        },
    },
]


def handle_get_project(input: dict) -> dict:
    project = _gl.projects.get(input["project_id"])
    return {"id": project.id, "name": project.name, "web_url": project.web_url}


def handle_list_projects(input: dict) -> list:
    if group_name := input.get("group_name"):
        group = _gl.groups.get(group_name)
        projects = group.projects.list(iterator=True)
    else:
        projects = _gl.projects.list(iterator=True)
    return [{"id": p.id, "name": p.name, "url": p.web_url} for p in projects]


def handle_list_merge_request_by_name(input: dict) -> list:
    mrs = _gl.mergerequests.list(search=input["merge_request_name"], iterator=True)
    return [{"iid": mr.iid, "title": mr.title, "project_id": mr.project_id} for mr in mrs]


def handle_list_merge_requests(input: dict) -> list:
    project = _gl.projects.get(input["project_id"])
    mrs = project.mergerequests.list(state="opened", iterator=True)
    return [{"iid": mr.iid, "title": mr.title, "state": mr.state} for mr in mrs]


def handle_get_merge_request(input: dict) -> dict:
    project = _gl.projects.get(input["project_id"])
    mr = project.mergerequests.get(input["merge_request_id"])
    diffs = mr.diffs.list()
    return {
        "iid": mr.iid,
        "title": mr.title,
        "description": mr.description,
        "diffs": [{"old_path": d.old_path, "new_path": d.new_path, "diff": d.diff} for d in diffs],
    }


TOOL_HANDLERS = {
    "get_project": handle_get_project,
    "list_projects": handle_list_projects,
    "list_merge_request_by_name": handle_list_merge_request_by_name,
    "list_merge_requests": handle_list_merge_requests,
    "get_merge_request": handle_get_merge_request,
}
