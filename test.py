from dotenv import load_dotenv
from anthropic import AnthropicBedrock
import os

load_dotenv()
# Proof of .env
good_model_name = "anthropic.claude-3-5-sonnet-20240620-v1:0"
bad_model_name = "anthropic.claude-3-5-sonnet-20241022-v2:0"
#os.getenv("BEDROCK_MODEL_NAME")

client = AnthropicBedrock()

try:
    msg = client.messages.create(
        model=good_model_name,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hey, how are you?"}]
    )
    print(msg.content)
    print("Good model works")
except Exception as e:
    print(f"Error: {e}")

try:
    msg = client.messages.create(
        model=bad_model_name,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hey, how are you?"}]
    )
    print(msg.content)
    print("Bad model works")
except Exception as e:
    print(f"Error: {e}")