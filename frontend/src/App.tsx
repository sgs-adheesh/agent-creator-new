import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import CreateAgent from './pages/CreateAgent';
import AgentList from './pages/AgentList';
import ExecuteAgent from './pages/ExecuteAgent';
import EditAgent from './pages/EditAgent';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<AgentList />} />
        <Route path="/agents/create" element={<CreateAgent />} />
        <Route path="/agents/:id/execute" element={<ExecuteAgent />} />
        <Route path="/agents/:id/edit" element={<EditAgent />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
