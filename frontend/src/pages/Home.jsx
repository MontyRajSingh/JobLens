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
      <section className="relative overflow-hidden py-20 md:py-28">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-950/50 via-surface-900 to-surface-950" />
        <div className="absolute top-20 left-1/4 w-72 h-72 bg-brand-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-10 right-1/4 w-96 h-96 bg-violet-500/5 rounded-full blur-3xl" />

        <div className="relative max-w-4xl mx-auto px-4 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-300 text-sm font-medium mb-6">
            <Sparkles size={14} /> AI-Powered Salary Intelligence
          </div>

          <h1 className="text-4xl md:text-6xl font-extrabold mb-6 leading-tight">
            Find out what your skills are{' '}
            <span className="gradient-text">worth globally</span>
          </h1>

          <p className="text-slate-400 text-lg md:text-xl mb-10 max-w-2xl mx-auto">
            Real-time salary data from LinkedIn, Indeed & Glassdoor across 17+ cities.
            ML-powered predictions for your next career move.
          </p>

          {/* Search bar */}
          <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Job title, e.g. Data Scientist"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-surface-800 border border-white/10 text-white placeholder-slate-500 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all text-sm"
                />
              </div>
              <div className="relative flex-shrink-0 w-full sm:w-48">
                <MapPin size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
                <select
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-surface-800 border border-white/10 text-white focus:border-brand-500 outline-none transition-all text-sm appearance-none"
                >
                  <option value="">All Cities</option>
                  <option value="New York, NY, USA">New York</option>
                  <option value="San Francisco, CA, USA">San Francisco</option>
                  <option value="London, UK">London</option>
                  <option value="Bangalore, India">Bangalore</option>
                  <option value="Toronto, Canada">Toronto</option>
                  <option value="Berlin, Germany">Berlin</option>
                  <option value="Singapore">Singapore</option>
                  <option value="Sydney, Australia">Sydney</option>
                </select>
              </div>
              <button
                type="submit"
                className="px-8 py-3.5 rounded-xl bg-gradient-to-r from-brand-600 to-brand-500 text-white font-semibold text-sm hover:from-brand-500 hover:to-brand-400 transition-all shadow-lg shadow-brand-500/25 hover:shadow-brand-500/40"
              >
                Search
              </button>
            </div>
          </form>
        </div>
      </section>

      {/* Stats */}
      <section className="max-w-6xl mx-auto px-4 -mt-8 mb-16">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((s, i) => (
            <div key={i} className="glass rounded-xl p-5 hover:border-brand-500/20 transition-all group">
              <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center mb-3 shadow-lg group-hover:scale-110 transition-transform`}>
                <s.icon size={20} className="text-white" />
              </div>
              {loading ? (
                <div className="skeleton h-8 w-24 mb-1" />
              ) : (
                <p className="text-2xl font-bold text-white">{s.value}</p>
              )}
              <p className="text-slate-500 text-sm">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Top Skills */}
      <section className="max-w-6xl mx-auto px-4 mb-16">
        <h2 className="text-2xl font-bold text-white mb-6">
          🔥 Top Skills by Salary Premium
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {loading ? (
            Array(5).fill(0).map((_, i) => <div key={i} className="skeleton h-24 rounded-xl" />)
          ) : topSkills.length > 0 ? (
            topSkills.map((skill, i) => (
              <div key={i} className="glass rounded-xl p-4 hover:border-brand-500/20 transition-all">
                <p className="text-white font-semibold text-sm mb-1">{skill.skill}</p>
                <p className={`text-lg font-bold ${skill.salary_premium_pct > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {skill.salary_premium_pct > 0 ? '+' : ''}{skill.salary_premium_pct}%
                </p>
                <p className="text-slate-500 text-xs">{skill.count} jobs</p>
              </div>
            ))
          ) : (
            <p className="text-slate-500 col-span-5">No skill data available yet</p>
          )}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-4xl mx-auto px-4 mb-20 text-center">
        <div className="glass rounded-2xl p-10 border border-brand-500/10">
          <h2 className="text-3xl font-bold text-white mb-4">Ready to know your market value?</h2>
          <p className="text-slate-400 mb-8 max-w-lg mx-auto">
            Our ML model predicts your salary based on title, skills, city, and experience.
          </p>
          <button
            onClick={() => navigate('/predict')}
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 text-white font-semibold hover:from-brand-500 hover:to-violet-500 transition-all shadow-lg shadow-brand-500/25 glow-pulse"
          >
            Predict My Salary <ArrowRight size={18} />
          </button>
        </div>
      </section>
    </div>
  );
}
