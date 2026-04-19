from dotenv import load_dotenv
load_dotenv()  # must be first before any other imports that use env vars

import gradio as gr
from llm_client import chat, reset

SESSION_ID = "gradio-session"

def respond(message, history):
    reply = chat(SESSION_ID, message)
    return reply

def clear():
    reset(SESSION_ID)

app = gr.ChatInterface(
    fn=respond,
    title="Codebase Agent",
)

if __name__ == "__main__":
    app.launch()


# def main():

#     project_id = handle_list_projects({"source": "proxy", "group_name": "backend"})
#     id = 0
#     for p in project_id:
#         print(p)
#         # if p["name"] == "crm-api":
#         #     id = p["id"]
#         #     break   
    
#     # print(id)
#     # search = handle_search_code({
#     #     "project_id": id,
#     #     "search_term": "getpersons",
#     #     "source": "proxy",
#     # })

#     print(search)



# if __name__ == "__main__":
#     main()
