# ADK Agent MCP Server

This project demonstrates an Agent Development Kit (ADK) agent that interacts with a local SQLite database via a local Model Context Protocol (MCP) server. The MCP server exposes tools to query and modify the database, and the agent uses these tools to fulfill user requests.

## Project Structure

```
adk-mcp/
├── local_mcp/
│   ├── agent.py             # The ADK agent for the local SQLite DB
│   ├── server.py            # The MCP server exposing database tools
│   ├── create_db.py         # Script to initialize the SQLite database
│   ├── database.db          # The SQLite database file
│   ├── prompt.py            # Prompt instructions for the agent
│   ├── mcp_server_activity.log # Log file for MCP server activity
│   └── __init__.py
├── .env                   # For GOOGLE_API_KEY (ensure it's in .gitignore if repo is public)
├── requirements.txt       # Python dependencies
├── .gitignore             # Git ignore rules
└── readme.md              # This file
```

## Setup Instructions

### 1. Prerequisites
- Python 3.8 or newer
- Access to a terminal or command prompt

### 2. Create and Activate Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies.

```bash
python3 -m venv .venv
```

Activate the virtual environment:

On macOS/Linux:
```bash
source .venv/bin/activate
```

On Windows:
```bash
.venv\Scripts\activate
```

### 3. Install Dependencies

Install all required Python packages using pip:

```bash
pip install -r requirements.txt
```

### 4. Set Up Gemini API Key (for the ADK Agent)


  Set the API key as an environment variable. Create a `.env` file

    ```env
    GOOGLE_API_KEY=your_gemini_api_key_here
    ```

### 5. Create the SQLite Database and Tables

Navigate to the `local_mcp` directory and run the script:
```bash
cd local_mcp
python3 create_db.py
cd ..
```
This will create `local_mcp/database.db` if it doesn't already exist.

## Running the Agent and MCP Server

To run the agent:

1.  Ensure your virtual environment is active and you are in the root directory `adk-mcp`.
2.  Execute the agent script:

    ```bash
    adk web
    ```

This will:
- Start the `agent.py` script.
- The agent, upon initializing the `MCPToolset`, will execute the `python3 local_mcp/server.py` command.
- The `server.py` (MCP server) will start and listen for tool calls from the agent via stdio.
- The agent will then be ready to process your instructions (which you would typically provide in a client application or test environment that uses this agent).

You should see log output from both the agent (if any) and the MCP server (in `local_mcp/mcp_server_activity.log`, and potentially to the console if you uncomment the stream handler in `server.py`).

## Demo Conversation

Below is an example of how you might interact with the agent (via a client or test harness) to use the local MCP tools:

**User:**
```
List all tables in the database.
```
**Agent:**
```
Tables listed successfully: users, todos
```

**User:**
```
Show me all users.
```
**Agent:**
```
[
  {"id": 1, "username": "alice", "email": "alice@example.com"},
  {"id": 2, "username": "bob", "email": "bob@example.com"},
  {"id": 3, "username": "charlie", "email": "charlie@example.com"}
]
```

**User:**
```
Add a new user with username 'dave' and email 'dave@example.com'.
```
**Agent:**
```
Data inserted successfully. Row ID: 4
```

**User:**
```
Show me all users.
```
**Agent:**
```
[
  {"id": 1, "username": "alice", "email": "alice@example.com"},
  {"id": 2, "username": "bob", "email": "bob@example.com"},
  {"id": 3, "username": "charlie", "email": "charlie@example.com"},
  {"id": 4, "username": "dave", "email": "dave@example.com"}
]
```

## Available Database Tools (Exposed by MCP Server)

The `local_mcp/server.py` exposes the following tools for the ADK agent to use:

-   **`list_db_tables(dummy_param: str) -> dict`**: Lists all tables in the database.
    *   *Note*: Requires a `dummy_param` string due to current ADK schema generation behavior; the agent's instructions guide it to provide a default.
-   **`get_table_schema(table_name: str) -> dict`**: Retrieves the schema (column names and types) for a specified table.
-   **`query_db_table(table_name: str, columns: str, condition: str) -> list[dict]`**: Queries a table.
    *   `columns`: Comma-separated list of columns (e.g., "id, username") or "*" for all.
    *   `condition`: SQL WHERE clause (e.g., "email LIKE '%@example.com'"). The agent is instructed to use "1=1" if no condition is implied.
-   **`insert_data(table_name: str, data: dict) -> dict`**: Inserts a new row into a table.
    *   `data`: A dictionary where keys are column names and values are the corresponding data for the new row.
-   **`delete_data(table_name: str, condition: str) -> dict`**: Deletes rows from a table based on a condition.
    *   *Note*: The condition cannot be empty as a safety measure.

## Troubleshooting

-   **`No module named 'deprecated'`**:
    *   Run `pip install deprecated` to install the missing dependency.
-   **`No such file or directory` for `server.py`**:
    *   Ensure `PATH_TO_YOUR_MCP_SERVER_SCRIPT` in `local_mcp/agent.py` correctly points to `local_mcp/server.py`.

## Acknowledgements

This project was structured and the prompts were designed with the help of AI assistance to ensure clarity, efficiency, and best practices.
