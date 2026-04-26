import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Jobs from './pages/Jobs';
import JobDetail from './pages/JobDetail';
import Predict from './pages/Predict';
import Insights from './pages/Insights';

export default function App() {
  return (
    <div className="min-h-screen bg-surface-950">
      <Navbar />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/jobs/:id" element={<JobDetail />} />
          <Route path="/predict" element={<Predict />} />
          <Route path="/insights" element={<Insights />} />
        </Routes>
      </main>
    </div>
  );
}
