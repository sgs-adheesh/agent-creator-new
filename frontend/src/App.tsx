import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import CreateAgent from './pages/CreateAgent';
import AgentList from './pages/AgentList';
import ExecuteAgent from './pages/ExecuteAgent';
import EditAgent from './pages/EditAgent';
import { useState } from 'react';

function App() {
  const [activeTab, setActiveTab] = useState<'templates' | 'my-agents'>('templates');
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/templates" replace />} />
        <Route 
          path="/templates" 
          element={<AgentList activeTab={activeTab} setActiveTab={setActiveTab} />} 
        />
        <Route 
          path="/my-agents" 
          element={<AgentList activeTab={activeTab} setActiveTab={setActiveTab} />} 
        />        
        <Route path="/agents/create" element={<CreateAgent />} />
        <Route path="/agents/:id/execute" element={<ExecuteAgent />} />
        <Route path="/agents/:id/edit" element={<EditAgent />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
