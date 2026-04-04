import gitlab
import os


gl = gitlab.Gitlab(os.getenv("GITLAB_URL"), private_token=os.getenv("PRIVATE-TOKEN"))
