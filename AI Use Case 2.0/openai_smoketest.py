from dotenv import load_dotenv
load_dotenv()

import os
print('OPENAI key set?', bool(os.getenv('OPENAI_API_KEY')))

from openai import OpenAI
client = OpenAI()

resp = client.chat.completions.create(
    model='gpt-4o-mini',
    messages=[
        {'role':'system','content':'You are concise.'},
        {'role':'user','content':'Reply with ok in one word.'}
    ],
    temperature=0.0,
)
print('Response:', resp.choices[0].message.content)
