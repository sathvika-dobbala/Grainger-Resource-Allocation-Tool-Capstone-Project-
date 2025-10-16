import os, openai
from dotenv import load_dotenv
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

models = openai.Model.list()
print([m["id"] for m in models["data"]][:50])  # print first 50 ids
