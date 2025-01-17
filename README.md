# Model Context Protocol Examples

This repository demonstrates the use of Anthropic's Model Context Protocol (MCP) with two examples: one using stdio and another using independent client and server connected via Server-Sent Events (SSE).

## Prerequisites

- Ubuntu operating system or wsl
- Python 3.x
- pip (Python package installer)

## Setup

1. Clone this repository:

  ```
  git clone https://github.com/skywarditsolutions/JZ-Training-demo.git
```

  ```
  cd JZ-Training-demo
```

2. Install the required dependencies:

  ```
  pip install -r requirements.txt
```

3. Set up your environment variables:

```
cp env.example .env
```

Open the `.env` file and add your Bedrock API keys.

## Example 1: stdio

This example demonstrates the MCP using standard input/output.

To run:

```
python client.py server.py
```

## Example 2: Independent Client and Server

This example shows the MCP using independent client and server processes connected via Server-Sent Events.

1. In one terminal, start the server:

```
python independent_server.py
```

2. In another terminal, start the client:

```
python independent_client.py
```

The client and server are configured to connect over `localhost:5553`.

## How it Works

These examples illustrate the Model Context Protocol from Anthropic. The MCP client runs a chatbot loop that can utilize tools from the MCP server. This allows for dynamic interaction between the language model and external tools or data sources. After each user message, the LLM will determine whether to call a tool (in this example, a document summarizer) or respond normally.
