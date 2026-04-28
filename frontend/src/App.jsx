import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './auth/AuthProvider';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Jobs from './pages/Jobs';
import JobDetail from './pages/JobDetail';
import Predict from './pages/Predict';
import Insights from './pages/Insights';
import OfferAnalyzer from './pages/OfferAnalyzer';
import CompanyProfile from './pages/CompanyProfile';
import History from './pages/History';
import Login from './pages/Login';
import ParallaxStarsBackground from './components/ParallaxStarsBackground';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-transparent flex items-center justify-center font-bold tracking-widest text-2xl uppercase text-brand-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <div className="min-h-screen bg-transparent relative">
      <ParallaxStarsBackground speed={1.5} />
      <Navbar />
      <main className="relative z-10">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
          <Route path="/jobs" element={<ProtectedRoute><Jobs /></ProtectedRoute>} />
          <Route path="/jobs/:id" element={<ProtectedRoute><JobDetail /></ProtectedRoute>} />
          <Route path="/predict" element={<ProtectedRoute><Predict /></ProtectedRoute>} />
          <Route path="/offer" element={<ProtectedRoute><OfferAnalyzer /></ProtectedRoute>} />
          <Route path="/insights" element={<ProtectedRoute><Insights /></ProtectedRoute>} />
          <Route path="/companies/:companyName" element={<ProtectedRoute><CompanyProfile /></ProtectedRoute>} />
          <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
        </Routes>
      </main>
    </div>
  );
}
