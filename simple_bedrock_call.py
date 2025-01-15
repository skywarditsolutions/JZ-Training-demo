import os
from dotenv import load_dotenv
load_dotenv()
from anthropic import AnthropicBedrock

client = AnthropicBedrock()

message = client.messages.create(
    model="anthropic.claude-3-5-sonnet-20240620-v1:0",
    max_tokens=1024,
    messages=[
        {
            "role": "user", 
            "content": "Hey, tell me a joke"
        }
    ]
)
print(message.content)