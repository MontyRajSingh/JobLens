import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, MapPin, TrendingUp, Globe2, DollarSign, BarChart3, ArrowRight, Sparkles } from 'lucide-react';
import { getMarketSummary, getTopSkills } from '../api/client';

export default function Home() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [city, setCity] = useState('');
  const [summary, setSummary] = useState(null);
  const [topSkills, setTopSkills] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, sk] = await Promise.all([getMarketSummary(), getTopSkills()]);
        setSummary(s);
        setTopSkills((sk || []).filter(s => s.salary_premium_pct != null).slice(0, 5));
      } catch (e) {
        console.error('Home data load error:', e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    const params = new URLSearchParams();
    if (keyword) params.set('keyword', keyword);
    if (city) params.set('city', city);
    navigate(`/jobs?${params.toString()}`);
  };

  const stats = [
    { label: 'Total Jobs', value: summary?.total_jobs?.toLocaleString() || '—', icon: BarChart3, color: 'from-brand-500 to-brand-700' },
    { label: 'Cities', value: summary?.cities_count || '—', icon: Globe2, color: 'from-emerald-500 to-emerald-700' },
    { label: 'Avg Salary', value: summary?.salary_avg ? `$${Math.round(summary.salary_avg).toLocaleString()}` : '—', icon: DollarSign, color: 'from-amber-500 to-amber-700' },
    { label: 'Salary Range', value: summary?.salary_min && summary?.salary_max ? `$${Math.round(summary.salary_min/1000)}k–$${Math.round(summary.salary_max/1000)}k` : '—', icon: TrendingUp, color: 'from-rose-500 to-rose-700' },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative overflow-hidden py-24 border-b-4 border-white">
        <div className="relative max-w-6xl mx-auto px-4">
          
          <div className="flex flex-col md:flex-row items-end justify-between gap-12 mb-16">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 border-2 border-brand-500 bg-brand-500 text-black text-sm font-bold uppercase tracking-wider mb-8 shadow-brutal-white">
                <Sparkles size={16} fill="black" /> AI-Powered Intelligence
              </div>

              <h1 className="display-text text-6xl md:text-8xl leading-[0.9] tracking-tight mb-6">
                KNOW YOUR <br />
                <span className="text-brand-500">MARKET VALUE.</span>
              </h1>

              <p className="text-lg md:text-xl font-medium border-l-4 border-brand-500 pl-6 text-slate-300 max-w-xl">
                Real-time salary data from LinkedIn, Indeed & Glassdoor across 17+ cities. 
                ML-powered predictions for your next career move.
              </p>
            </div>
          </div>

          {/* Search bar */}
          <form onSubmit={handleSearch} className="w-full">
            <div className="flex flex-col md:flex-row gap-4 p-4 border-4 border-white bg-transparent backdrop-blur-md shadow-brutal-white">
              <div className="relative flex-1">
                <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-white" />
                <input
                  type="text"
                  placeholder="JOB TITLE, E.G. DATA SCIENTIST"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  className="w-full pl-12 pr-4 py-4 bg-transparent border-2 border-white text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none transition-colors uppercase font-bold text-sm tracking-wider"
                />
              </div>
              <div className="relative flex-shrink-0 w-full md:w-64">
                <MapPin size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-white" />
                <select
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full pl-12 pr-4 py-4 bg-transparent border-2 border-white text-white focus:border-brand-500 focus:outline-none transition-colors uppercase font-bold text-sm tracking-wider appearance-none"
                >
                  <option className="bg-black" value="">ALL CITIES</option>
                  <option className="bg-black" value="New York, NY, USA">NEW YORK</option>
                  <option className="bg-black" value="San Francisco, CA, USA">SAN FRANCISCO</option>
                  <option className="bg-black" value="London, UK">LONDON</option>
                  <option className="bg-black" value="Bangalore, India">BANGALORE</option>
                  <option className="bg-black" value="Toronto, Canada">TORONTO</option>
                  <option className="bg-black" value="Berlin, Germany">BERLIN</option>
                  <option className="bg-black" value="Singapore">SINGAPORE</option>
                  <option className="bg-black" value="Sydney, Australia">SYDNEY</option>
                </select>
              </div>
              <button type="submit" className="brutal-btn w-full md:w-auto text-lg">
                SEARCH
              </button>
            </div>
          </form>
        </div>
      </section>

      {/* Stats */}
      <section className="max-w-6xl mx-auto px-4 py-16 border-b-4 border-white">
        <h2 className="display-text text-4xl mb-8">MARKET OVERVIEW</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((s, i) => (
            <div key={i} className="brutal-card p-6 flex flex-col justify-between h-40">
              <div className="flex justify-between items-start">
                <p className="text-slate-400 font-bold uppercase tracking-wider text-sm">{s.label}</p>
                <s.icon size={24} className="text-brand-500" strokeWidth={2} />
              </div>
              {loading ? (
                <div className="skeleton h-10 w-32" />
              ) : (
                <p className="display-text text-4xl md:text-5xl tracking-wide">{s.value}</p>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Top Skills */}
      <section className="max-w-6xl mx-auto px-4 py-16 border-b-4 border-white">
        <h2 className="display-text text-4xl mb-8">
          TOP SKILLS <span className="text-brand-500">PREMIUM</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
          {loading ? (
            Array(5).fill(0).map((_, i) => <div key={i} className="skeleton h-32 brutal-card" />)
          ) : topSkills.length > 0 ? (
            topSkills.map((skill, i) => (
              <div key={i} className="brutal-card p-5 flex flex-col justify-between h-32">
                <p className="text-white font-bold uppercase tracking-widest text-sm break-words">{skill.skill}</p>
                <div className="flex justify-between items-end">
                  <p className={`display-text text-3xl ${skill.salary_premium_pct > 0 ? 'text-brand-500' : 'text-brand-accent'}`}>
                    {skill.salary_premium_pct > 0 ? '+' : ''}{skill.salary_premium_pct}%
                  </p>
                  <p className="text-slate-500 text-xs font-bold uppercase">{skill.count} JOBS</p>
                </div>
              </div>
            ))
          ) : (
            <p className="text-slate-500 col-span-5 font-bold uppercase">NO SKILL DATA AVAILABLE YET</p>
          )}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-4 py-24 text-center">
        <div className="brutal-card-brand p-12 md:p-20 bg-transparent backdrop-blur-md flex flex-col items-center justify-center">
          <h2 className="display-text text-5xl md:text-7xl mb-6">READY TO PREDICT?</h2>
          <p className="text-lg font-medium text-slate-300 max-w-xl mx-auto mb-10 uppercase tracking-widest">
            OUR ML MODEL PREDICTS YOUR SALARY BASED ON TITLE, SKILLS, CITY, AND EXPERIENCE.
          </p>
          <button
            onClick={() => navigate('/predict')}
            className="brutal-btn text-xl px-12 py-6 glow-pulse"
          >
            PREDICT MY SALARY <ArrowRight size={24} strokeWidth={3} />
          </button>
        </div>
      </section>
    </div>
  );
}
