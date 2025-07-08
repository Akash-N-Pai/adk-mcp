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

1.  Create or use an existing [Google AI Studio](https://aistudio.google.com/) account.
2.  Get your Gemini API key from the [API Keys section](https://aistudio.google.com/app/apikeys).
3.  Set the API key as an environment variable. Create a `.env` file in the **root of the `adk-mcp` project**:

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
-   **Database Errors (e.g., "no such table")**:
    *   Ensure you have run `python3 local_mcp/create_db.py` to create the `database.db` file and its tables.
    *   Verify the `DATABASE_PATH` in `local_mcp/server.py` correctly points to `local_mcp/database.db`.
-   **API Key Issues**:
    *   Make sure your `GOOGLE_API_KEY` is correctly set in the `.env` file in the project root and that the file is being loaded.
-   **MCP Server Log**:
    *   Check `local_mcp/mcp_server_activity.log` for detailed logs from the MCP server, which can help diagnose issues with tool calls or database operations.
