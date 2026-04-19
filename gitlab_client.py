import gitlab
import os


gl = gitlab.Gitlab(os.getenv("GITLAB_PROXY_URL"), private_token=os.getenv("GITLAB_PROXY_TOKEN"))
