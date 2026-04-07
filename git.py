import gitlab
import os


class GitlabClientWrapper:
    def __init__(self):
        self.url = os.getenv("GITLAB_URL", "https://gitlab.dev.dyl.com")
        self.token = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "")
        self.client = gitlab.Gitlab(self.url, private_token=self.token)

    def get_project(self, project_id: int):
        """Fetch a single project by its numeric ID."""
        return self.client.projects.get(project_id)

    def list_projects(self, group_name: str | None = None):
        """List all projects. If group_name is provided, list only projects within that group."""
        if group_name:
            group = self.client.groups.get(group_name)
            return group.projects.list(iterator=True)
        return self.client.projects.list(iterator=True)

    def list_merge_requests(self, project_id: int):
        """List all open merge requests for a given project."""
        project = self.get_project(project_id)
        return project.mergerequests.list(state="opened", iterator=True)

    def list_merge_request_by_name(self, merge_rquest_name: str):
        """Search for merge requests by title across all accessible projects."""
        return self.client.mergerequests.list(search=merge_rquest_name, iterator=True)

    def get_merge_request(self, project_id: int, merge_request_id: int):
        """Fetch a single merge request and its code diffs by project ID and MR IID."""
        project = self.get_project(project_id)
        mr = project.mergerequests.get(merge_request_id)
        diffs = mr.diffs.list()
        return mr, diffs
