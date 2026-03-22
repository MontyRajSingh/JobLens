import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DollarSign, TrendingUp, Award, ArrowRight, Loader2 } from 'lucide-react';
import { predictSalary } from '../api/client';

const CITIES = [
  'New York, NY, USA', 'San Francisco, CA, USA', 'Seattle, WA, USA',
  'Austin, TX, USA', 'Chicago, IL, USA', 'Boston, MA, USA',
  'London, UK', 'Berlin, Germany', 'Toronto, Canada',
  'Bangalore, India', 'Singapore', 'Sydney, Australia',
  'Dublin, Ireland', 'Amsterdam, Netherlands', 'Dubai, UAE', 'Tokyo, Japan',
];

const SENIORITY = [
  'Entry Level (0-2 years)', 'Associate (1-3 years)', 'Mid-Level (2-5 years)',
  'Senior (5+ years)', 'Staff (8+ years)', 'Director (8+ years)',
];

const SKILLS = [
  'Python', 'SQL', 'Machine Learning', 'AWS', 'JavaScript', 'React', 'Docker',
  'Kubernetes', 'TensorFlow', 'PyTorch', 'Java', 'Spark', 'Tableau', 'Power BI',
  'NLP', 'Deep Learning', 'Git', 'Azure', 'GCP', 'Scikit-learn', 'Pandas',
  'NoSQL', 'Linux', 'REST API', 'Agile', 'CI/CD', 'Airflow', 'Hadoop',
  'Scala', 'R', 'Excel', 'Kafka', 'Redis', 'GraphQL', 'TypeScript',
  'C++', 'Golang', 'Rust', 'Swift', 'Terraform',
];

export default function Predict() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    job_title: '',
    city: 'New York, NY, USA',
    seniority_level: 'Mid-Level (2-5 years)',
    experience_years: null,
    skills: [],
    employment_type: 'Full-time',
    remote_type: 'On-site',
    education_required: '',
    company_name: '',
    has_equity: false,
    has_bonus: false,
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const updateForm = (key, value) => setForm(prev => ({ ...prev, [key]: value }));

  const toggleSkill = (skill) => {
    setForm(prev => ({
      ...prev,
      skills: prev.skills.includes(skill)
        ? prev.skills.filter(s => s !== skill)
        : [...prev.skills, skill],
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.job_title.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const payload = {
        ...form,
        experience_years: form.experience_years ? parseFloat(form.experience_years) : undefined,
      };
      const data = await predictSalary(payload);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
        <DollarSign className="text-brand-400" size={28} /> Salary Predictor
      </h1>
      <p className="text-slate-400 mb-8">Enter your job details to get an AI-powered salary prediction</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Job Title */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Job Title *</label>
            <input
              type="text"
              value={form.job_title}
              onChange={e => updateForm('job_title', e.target.value)}
              placeholder="e.g. Senior Data Scientist"
              required
              className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
            />
          </div>

          {/* City + Seniority */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">City *</label>
              <select
                value={form.city}
                onChange={e => updateForm('city', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none"
              >
                {CITIES.map(c => <option key={c} value={c}>{c.split(',')[0]}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Seniority *</label>
              <select
                value={form.seniority_level}
                onChange={e => updateForm('seniority_level', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none"
              >
                {SENIORITY.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* Experience + Employment + Remote */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Experience (yrs)</label>
              <input
                type="number"
                min="0" max="30"
                value={form.experience_years || ''}
                onChange={e => updateForm('experience_years', e.target.value)}
                placeholder="0-30"
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Employment</label>
              <select
                value={form.employment_type}
                onChange={e => updateForm('employment_type', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none"
              >
                <option>Full-time</option>
                <option>Part-time</option>
                <option>Contract</option>
                <option>Internship</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Work Type</label>
              <select
                value={form.remote_type}
                onChange={e => updateForm('remote_type', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none"
              >
                <option>On-site</option>
                <option>Remote</option>
                <option>Hybrid</option>
              </select>
            </div>
          </div>

          {/* Education + Company */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Education</label>
              <select
                value={form.education_required}
                onChange={e => updateForm('education_required', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none"
              >
                <option value="">Not specified</option>
                <option>Bachelor's</option>
                <option>Master's</option>
                <option>PhD</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Company</label>
              <input
                type="text"
                value={form.company_name}
                onChange={e => updateForm('company_name', e.target.value)}
                placeholder="e.g. Google"
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-500 outline-none"
              />
            </div>
          </div>

          {/* Toggles */}
          <div className="flex gap-4">
            {[
              { key: 'has_equity', label: '💰 Has Equity' },
              { key: 'has_bonus', label: '🎯 Has Bonus' },
            ].map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => updateForm(key, !form[key])}
                className={`flex-1 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                  form[key]
                    ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30'
                    : 'bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Skills */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Skills ({form.skills.length} selected)
            </label>
            <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto p-3 bg-surface-900 rounded-xl border border-white/5">
              {SKILLS.map(skill => (
                <button
                  key={skill}
                  type="button"
                  onClick={() => toggleSkill(skill)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                    form.skills.includes(skill)
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                      : 'bg-white/5 text-slate-500 hover:text-slate-300 border border-transparent hover:bg-white/10'
                  }`}
                >
                  {skill}
                </button>
              ))}
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || !form.job_title.trim()}
            className="w-full py-4 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 text-white font-bold text-base hover:from-brand-500 hover:to-violet-500 transition-all shadow-lg shadow-brand-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? <><Loader2 size={18} className="animate-spin" /> Predicting...</> : 'Predict Salary'}
          </button>

          {error && <p className="text-red-400 text-sm text-center">{error}</p>}
        </form>

        {/* Result */}
        <div>
          {result ? (
            <div className="space-y-4 sticky top-24">
              {/* Main prediction */}
              <div className="glass rounded-xl p-6 border border-brand-500/20">
                <p className="text-slate-400 text-sm mb-2">Predicted Salary</p>
                <p className="text-5xl font-extrabold gradient-text mb-1">
                  ${result.predicted_salary_usd?.toLocaleString()}
                </p>
                <p className="text-slate-500">USD / year</p>

                {/* Confidence bar */}
                <div className="mt-6">
                  <div className="flex justify-between text-xs text-slate-500 mb-2">
                    <span>${result.confidence_low?.toLocaleString()}</span>
                    <span className="text-slate-400">Confidence Range</span>
                    <span>${result.confidence_high?.toLocaleString()}</span>
                  </div>
                  <div className="confidence-bar h-3">
                    <div
                      className="confidence-marker"
                      style={{
                        left: `${Math.min(95, Math.max(5, ((result.predicted_salary_usd - result.confidence_low) /
                          (result.confidence_high - result.confidence_low)) * 100))}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Percentile */}
              <div className="glass rounded-xl p-5 flex items-center gap-4">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-brand-500 to-violet-600 flex items-center justify-center shrink-0">
                  <span className="text-white font-bold text-lg">{result.percentile}</span>
                </div>
                <div>
                  <p className="text-white font-semibold">Top {100 - (result.percentile || 50)}%</p>
                  <p className="text-slate-400 text-sm">for this role and city</p>
                </div>
                <Award className="ml-auto text-amber-400" size={24} />
              </div>

              {/* Top features */}
              {result.top_features?.length > 0 && (
                <div className="glass rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <TrendingUp size={16} className="text-brand-400" /> Top Impact Factors
                  </h3>
                  <div className="space-y-2">
                    {result.top_features.map((f, i) => (
                      <div key={i} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                        <div>
                          <p className="text-sm text-white">{f.feature?.replace(/_/g, ' ')}</p>
                          <p className="text-xs text-slate-500">value: {f.value}</p>
                        </div>
                        <span className={`text-sm font-bold ${
                          String(f.impact).startsWith('+') ? 'text-emerald-400' : 'text-red-400'
                        }`}>
                          {f.impact}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Model info */}
              <div className="flex items-center justify-between text-xs text-slate-500 px-1">
                <span>Model: {result.model_name}</span>
                <span>Similar jobs: {result.similar_jobs_count}</span>
              </div>

              {/* Browse similar */}
              <button
                onClick={() => navigate(`/jobs?keyword=${encodeURIComponent(form.job_title)}&city=${encodeURIComponent(form.city)}`)}
                className="w-full py-3 rounded-xl glass text-brand-300 font-medium text-sm hover:bg-brand-500/10 transition-all flex items-center justify-center gap-2"
              >
                Browse similar jobs <ArrowRight size={16} />
              </button>
            </div>
          ) : (
            <div className="glass rounded-xl p-10 text-center sticky top-24">
              <DollarSign size={48} className="text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 text-lg font-medium">Your prediction will appear here</p>
              <p className="text-slate-500 text-sm mt-2">Fill in the form and click "Predict Salary"</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
