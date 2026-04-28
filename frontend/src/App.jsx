import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Jobs from './pages/Jobs';
import JobDetail from './pages/JobDetail';
import Predict from './pages/Predict';
import Insights from './pages/Insights';
import OfferAnalyzer from './pages/OfferAnalyzer';
import CompanyProfile from './pages/CompanyProfile';
import ParallaxStarsBackground from './components/ParallaxStarsBackground';

export default function App() {
  return (
    <div className="min-h-screen bg-transparent relative">
      <ParallaxStarsBackground speed={1.5} />
      <Navbar />
      <main className="relative z-10">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/jobs/:id" element={<JobDetail />} />
          <Route path="/predict" element={<Predict />} />
          <Route path="/offer" element={<OfferAnalyzer />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/companies/:companyName" element={<CompanyProfile />} />
        </Routes>
      </main>
    </div>
  );
}
