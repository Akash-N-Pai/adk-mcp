# ADK Context Integration for HTCondor MCP System

This document explains how the [Google Agent Development Kit (ADK) Context system](https://google.github.io/adk-docs/context/) has been integrated into the HTCondor MCP system to provide enhanced session management, persistent memory, and cross-session context awareness.

## Overview

The ADK Context system provides a comprehensive framework for managing state, artifacts, memory, and authentication in agent-based systems. Our integration brings these capabilities to the HTCondor job management system, enabling:

- **Persistent Session State**: Remember user preferences and job history across sessions
- **Artifact Storage**: Save and retrieve job reports, configurations, and data
- **Memory Search**: Find relevant information from previous interactions
- **Cross-Session Context**: Maintain continuity across multiple user sessions
- **User Preferences**: Store and apply user-specific settings automatically

## Architecture

### Core Components

1. **ContextManager** (`local_mcp/context.py`)
   - Manages all context-related operations
   - Provides ToolContext, CallbackContext, and ReadonlyContext instances
   - Handles artifact storage and memory management

2. **HTCondorContext** (Data Class)
   - HTCondor-specific context data structure
   - Tracks current jobs, preferences, and job history
   - Maintains session-specific state

3. **Enhanced Agent** (`local_mcp/agent.py`)
   - HTCondorAgent class with context integration
   - Automatic context management in `_run_async_impl`
   - Memory logging and session tracking

4. **Context-Aware Tools** (`local_mcp/server.py`)
   - Tools that leverage ADK Context capabilities
   - Automatic session and user context extraction
   - Artifact storage and memory search integration

## Key Features

### 1. Session State Management

The system automatically manages session state using ADK's context framework:

```python
# Tools automatically receive context
def list_jobs(owner=None, status=None, limit=10, tool_context=None):
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        htcondor_ctx = tool_context.htcondor_context
        session_id = htcondor_ctx.session_id
        user_id = htcondor_ctx.user_id
        # Use user preferences from context
        if not limit and htcondor_ctx.preferences:
            limit = htcondor_ctx.preferences.get('default_job_limit', 10)
```

### 2. Artifact Storage

Save and retrieve job reports and data as artifacts:

```python
# Save a job report as an artifact
def save_job_report(cluster_id, report_name, tool_context=None):
    if tool_context and hasattr(tool_context, 'save_htcondor_artifact'):
        artifact_id = tool_context.save_htcondor_artifact(report_name, report_data)
        return {"success": True, "artifact_id": artifact_id}

# Load a previously saved report
def load_job_report(report_name, tool_context=None):
    if tool_context and hasattr(tool_context, 'load_htcondor_artifact'):
        artifact_data = tool_context.load_htcondor_artifact(report_name)
        return {"success": True, "artifact_data": artifact_data}
```

### 3. Memory Search

Search across user and global memory for relevant information:

```python
def search_job_memory(query, tool_context=None):
    if tool_context and hasattr(tool_context, 'search_htcondor_memory'):
        search_results = tool_context.search_htcondor_memory(query)
        return {
            "success": True,
            "results_count": len(search_results),
            "search_results": search_results
        }
```

### 4. Cross-Session Context

Maintain context across multiple sessions:

```python
def get_user_context_summary(tool_context=None):
    # Get comprehensive user context
    user_memory = context_manager.get_user_memory(user_id)
    current_context = tool_context.htcondor_context
    recent_jobs = current_context.job_history[-10:]
    preferences = current_context.preferences
    
    return {
        "user_id": user_id,
        "current_jobs": current_context.current_jobs,
        "recent_job_history": recent_jobs,
        "user_preferences": preferences,
        "memory_entries": len(user_memory)
    }
```

## New Context-Aware Tools

The integration adds several new tools that demonstrate ADK Context capabilities:

### 1. `save_job_report(cluster_id, report_name)`
- Saves a job status report as an artifact
- Uses ADK Context for persistent storage
- Returns artifact ID for future retrieval

### 2. `load_job_report(report_name)`
- Loads a previously saved job report
- Retrieves artifact data using ADK Context
- Provides full report history

### 3. `search_job_memory(query)`
- Searches user and global memory
- Finds relevant job information from past interactions
- Returns ranked search results

### 4. `get_user_context_summary()`
- Provides comprehensive user context overview
- Shows current jobs, preferences, and history
- Displays memory and session information

### 5. `add_to_memory(key, value, global_memory)`
- Adds information to user or global memory
- Supports persistent storage across sessions
- Enables future memory searches

## Usage Examples

### Basic Context Usage

```python
# The agent automatically uses context
user_message = "Show me my running jobs"
# Agent automatically:
# 1. Gets user context from session
# 2. Applies user preferences (e.g., default limit)
# 3. Tracks job references in context
# 4. Logs interaction to memory
```

### Advanced Context Features

```python
# Save a job report for later
save_job_report(cluster_id=1234567, report_name="my_analysis")

# Search for previous job information
search_job_memory("cluster 1234567")

# Get comprehensive user context
get_user_context_summary()

# Add user preference
add_to_memory("output_format", "table", global_memory=False)
```

## Implementation Details

### Context Flow

1. **Agent Initialization**: HTCondorAgent creates context-aware callbacks
2. **Tool Execution**: Tools receive ToolContext with HTCondor-specific methods
3. **State Persistence**: Context changes are automatically saved
4. **Memory Management**: Cross-session memory is maintained
5. **Artifact Storage**: Job reports and data are stored as artifacts

### Data Storage

- **All Data**: SQLite database (`sessions.db`) for complete compatibility
- **Session State**: SQLite database via SessionManager
- **Artifacts**: SQLite table for job reports and data files
- **Memory**: SQLite table for user and global memory
- **Context Data**: SQLite table for HTCondor-specific context
- **Cross-Session Data**: All stored in single SQLite database

### Error Handling

The system includes comprehensive error handling:

```python
try:
    # Context operations
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        # Use ADK Context
        pass
    else:
        # Fallback to legacy method
        pass
except Exception as e:
    logger.error(f"Context operation failed: {e}")
    # Graceful degradation
```

## Testing

Run the test script to verify the context integration:

```bash
python test_context.py
```

This will demonstrate:
- Session creation and management
- Memory storage and search
- Artifact save/load operations
- Context persistence
- Tool integration

## Benefits

### For Users
- **Persistent Preferences**: Settings remembered across sessions
- **Job History**: Automatic tracking of job interactions
- **Context Continuity**: Seamless experience across sessions
- **Personalized Responses**: Agent adapts to user preferences

### For Developers
- **Clean Architecture**: Separation of concerns with ADK Context
- **Extensible Design**: Easy to add new context-aware features
- **Robust State Management**: Automatic persistence and recovery
- **Standard Integration**: Follows ADK best practices
- **SQLite Compatibility**: Works in restricted environments

### For System Administrators
- **Audit Trail**: Complete history of user interactions
- **Resource Management**: Automatic cleanup of old data
- **Performance**: Efficient SQLite-based storage and retrieval
- **Scalability**: Designed for multi-user environments
- **Environment Compatibility**: Works with SQLite-only restrictions

## Future Enhancements

Potential improvements to the context system:

1. **Embedding-Based Search**: Use vector embeddings for better memory search
2. **Context Compression**: Compress old context data to save space
3. **Context Sharing**: Allow sharing context between users
4. **Advanced Analytics**: Context-aware usage analytics
5. **Integration with External Systems**: Connect to external memory systems

## References

- [ADK Context Documentation](https://google.github.io/adk-docs/context/)
- [ADK Tools Documentation](https://google.github.io/adk-docs/tools/)
- [ADK Agents Documentation](https://google.github.io/adk-docs/agents/)

## Conclusion

The ADK Context integration provides a robust foundation for stateful, context-aware HTCondor job management. By leveraging ADK's proven context framework, the system gains enterprise-grade session management, persistent memory, and cross-session continuity while maintaining clean, maintainable code architecture.

The integration demonstrates how ADK Context can be effectively applied to domain-specific systems, providing both immediate benefits and a foundation for future enhancements. 