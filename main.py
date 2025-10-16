from fastapi import FastAPI, Request
import os, json, base64, requests, tempfile
from github import Github
from dotenv import load_dotenv
import openai
import time


load_dotenv()
app = FastAPI()

# Load environment secrets
GITHUB_PAT = os.getenv("GITHUB_PAT")
LLM_API_KEY = os.getenv("LLM_API_KEY")
VERIFICATION_SECRET = os.getenv("VERIFICATION_SECRET")

openai.api_key = LLM_API_KEY

@app.post("/task")
async def handle_task(request: Request):
    data = await request.json()
    
    # 1️⃣ Verify secret
    if data.get("secret") != VERIFICATION_SECRET:
        return {"error": "Invalid secret!"}

    # Send immediate acknowledgment
    ack = {"status": "received"}
    
    # 2️⃣ Extract payload fields
    brief = data.get("brief")
    task = data.get("task")
    email = data.get("email")
    evaluation_url = data.get("evaluation_url")
    round_no = data.get("round")
    nonce = data.get("nonce")
    attachments = data.get("attachments", [])
    
    # 3️⃣ Generate app code via LLM
    prompt = f"Generate a minimal HTML/CSS/JS app for this brief:\n{brief}\nInclude README.md and MIT LICENSE."
    llm_response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    code = llm_response.choices[0].message["content"]
    
    # 4️⃣ Save to temp folder
    temp_dir = tempfile.mkdtemp()
    with open(f"{temp_dir}/index.html", "w") as f:
        f.write(code)
    with open(f"{temp_dir}/README.md", "w") as f:
        f.write(f"# {task}\n\nGenerated project.")
    with open(f"{temp_dir}/LICENSE", "w") as f:
        f.write("MIT License")

    # 5️⃣ Create GitHub repo
    g = Github(GITHUB_PAT)
    user = g.get_user()
    repo_name = f"llm-project-{task.lower().replace(' ', '-')}-{nonce}"
    repo = user.create_repo(repo_name, private=False)
    
    # Push files to repo
    repo.create_file("index.html", "initial commit", code)
    repo.create_file("README.md", "add readme", "Auto-generated")
    repo.create_file("LICENSE", "add license", "MIT License")
    
    repo_url = f"https://github.com/{user.login}/{repo_name}"
    pages_url = f"https://{user.login}.github.io/{repo_name}"

    # 6️⃣ Notify evaluation API
    payload = {
        "email": email,
        "task": task,
        "round": round_no,
        "nonce": nonce,
        "repo_url": repo_url,
        "pages_url": pages_url,
    }

    for i in range(5):  # retry mechanism
        r = requests.post(evaluation_url, json=payload)
        if r.status_code == 200:
            break
        time.sleep(2**i)
    
    return ack
