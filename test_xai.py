from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ.get('XAI_API_KEY'),
    base_url="https://api.x.ai/v1"
)

response = client.chat.completions.create(
    model="grok-3-beta",
    messages=[{"role": "user", "content": "Cześć, czy działasz?"}],
    max_tokens=50
)

print(response.choices[0].message.content)