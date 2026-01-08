# Agent Generator Application

A full-stack application for creating and executing AI agents with custom tools. Users can create agents via prompts, and agents can execute actions like database queries and API calls.

## Features

- **Agent Creation**: Create AI agents from natural language prompts
- **Custom Tools**: Built-in tools for PostgreSQL (read-only) and QuickBooks Online (placeholder)
- **Local AI Model**: Uses local Ollama instance with 'gpt-oss' model
- **Web UI**: Modern React + TailwindCSS interface
- **Agent Persistence**: Agents are saved to files for reuse

## Architecture

- **Backend**: Python FastAPI with LangChain for agent orchestration
- **Frontend**: Vite + React + TypeScript + TailwindCSS
- **AI Model**: Local Ollama instance
- **Storage**: File-based JSON storage

## Prerequisites

- Python 3.8+
- Node.js 18+
- Ollama installed and running locally with 'gpt-oss' model
- PostgreSQL (optional, for database queries)

## Setup

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the backend directory (optional):
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=your_database
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
AGENTS_STORAGE_DIR=agents
```

5. Start the backend server:
```bash
python -m uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Usage

1. **Create an Agent**:
   - Navigate to the home page
   - Click "Create New Agent"
   - Enter a prompt describing what the agent should do
   - Optionally provide a name for the agent
   - Click "Create Agent"

2. **Execute an Agent**:
   - Click on an agent from the list
   - Enter your query in the execution interface
   - Click "Execute" to run the agent
   - View results and intermediate steps

3. **Manage Agents**:
   - View all agents on the home page
   - Delete agents by clicking the "Delete" button
   - Navigate to agent execution by clicking on an agent card

## API Endpoints

- `POST /api/agents/create` - Create a new agent
- `GET /api/agents` - List all agents
- `GET /api/agents/{id}` - Get agent details
- `POST /api/agents/{id}/execute` - Execute an agent
- `DELETE /api/agents/{id}` - Delete an agent

## Project Structure

```
agent-generator/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration settings
│   ├── services/
│   │   └── agent_service.py    # Agent creation and execution
│   ├── tools/
│   │   ├── base_tool.py        # Base tool interface
│   │   ├── postgres_connector.py  # PostgreSQL tool
│   │   └── qbo_connector.py    # QBO placeholder
│   ├── storage/
│   │   └── agent_storage.py    # File-based storage
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Main app with routing
│   │   ├── pages/              # Page components
│   │   ├── services/           # API service
│   │   └── components/         # Reusable components
│   └── package.json
└── agents/                     # Agent storage directory
```

## Custom Tools

### PostgreSQL Connector
- Read-only SQL queries
- Only SELECT statements allowed
- Returns query results as JSON

### QBO Connector
- Placeholder implementation
- Ready for QuickBooks Online integration

## Development

### Backend Development
- The backend uses FastAPI with automatic API documentation
- Visit `http://localhost:8000/docs` for Swagger UI
- Visit `http://localhost:8000/redoc` for ReDoc
- Logging is configured and logs are written to `backend/logs/app.log`
- Environment variables are validated on startup

### Frontend Development
- Hot module replacement enabled
- TypeScript for type safety
- TailwindCSS for styling

### Testing
- Unit tests are located in `backend/tests/`
- Run tests with: `pytest` from the backend directory
- Test coverage can be generated with: `pytest --cov=. tests/`

### Code Quality
- Input validation and sanitization implemented
- Proper logging instead of debug print statements
- Error handling with detailed error messages
- Environment variable validation on startup

## Notes

- Ensure Ollama is running before starting the backend
- The 'gpt-oss' model must be available in your Ollama instance
- PostgreSQL connection is optional - agents will work without it
- Agents are stored as JSON files in the `agents/` directory
- Logs are stored in `backend/logs/app.log` (created automatically)

## Recent Improvements

### ✅ Completed Enhancements
1. **Logging System**: Replaced debug print statements with proper logging
2. **Input Validation**: Added validation for SQL queries, agent names, UUIDs, and workflow configs
3. **Error Handling**: Improved error handling with detailed logging and user-friendly messages
4. **Environment Validation**: Automatic validation of environment variables on startup
5. **Unit Tests**: Added test suite for validation utilities and PostgreSQL connector
6. **Code Cleanup**: Removed backup files and cleaned up codebase
7. **Security**: Added SQL injection detection and input sanitization

## License

MIT

