import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './Dashboard';
import KiteCallback from './KiteCallback';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/kite-callback" element={<KiteCallback />} />
      </Routes>
    </Router>
  );
}

export default App;
