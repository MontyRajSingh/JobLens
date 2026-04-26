import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { DollarSign, TrendingUp, Award, ArrowRight, Loader2, UploadCloud, Sparkles } from 'lucide-react';
import { predictSalary, predictFromResume } from '../api/client';

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
    experience_years: '',
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
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

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
    if (e) e.preventDefault();
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

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.type !== 'application/pdf') {
      setError('Please upload a PDF resume.');
      return;
    }

    setUploading(true);
    setError(null);
    
    try {
      const { extracted_data } = await predictFromResume(file);
      
      setForm(prev => {
        const newForm = { ...prev, ...extracted_data };
        
        if (extracted_data.skills && Array.isArray(extracted_data.skills)) {
          const matchedSkills = extracted_data.skills.filter(s => 
            SKILLS.some(preset => preset.toLowerCase() === s.toLowerCase())
          ).map(s => SKILLS.find(preset => preset.toLowerCase() === s.toLowerCase()));
          
          newForm.skills = matchedSkills;
        }
        
        return newForm;
      });
      
    } catch (err) {
      setError(err.message || 'Failed to parse resume.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <div className="mb-10 text-center">
        <h1 className="text-4xl md:text-5xl font-extrabold text-white mb-4 flex items-center justify-center gap-3">
          <Sparkles className="text-brand-400" /> Salary Predictor
        </h1>
        <p className="text-slate-400 max-w-2xl mx-auto">
          Our machine learning model analyzes your job title, location, skills, and experience to provide a real-time market value estimate.
        </p>
      </div>

      {/* Resume Upload - Sleek Version */}
      <div className="mb-12 glass rounded-2xl p-1 border-brand-500/20 overflow-hidden relative group">
        <div className="absolute inset-0 bg-gradient-to-r from-brand-500/5 to-violet-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
        <div className="relative p-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-brand-500/10 flex items-center justify-center text-brand-400">
              <UploadCloud size={24} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Auto-fill with Resume</h2>
              <p className="text-sm text-slate-400">Instantly extract your skills and experience using AI.</p>
            </div>
          </div>
          <input 
            type="file" 
            accept="application/pdf" 
            className="hidden" 
            ref={fileInputRef} 
            onChange={handleFileUpload}
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="bg-white/10 hover:bg-white/20 text-white font-semibold px-6 py-3 rounded-xl transition-all flex items-center gap-2 border border-white/10 disabled:opacity-50"
          >
            {uploading ? <Loader2 className="animate-spin" size={18} /> : <UploadCloud size={18} />} 
            {uploading ? 'Analyzing...' : 'Upload PDF Resume'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Job Title *</label>
            <input
              type="text"
              value={form.job_title}
              onChange={e => updateForm('job_title', e.target.value)}
              placeholder="e.g. Senior Machine Learning Engineer"
              required
              className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-500 outline-none transition-all"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">City *</label>
              <select
                value={form.city}
                onChange={e => updateForm('city', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none appearance-none"
              >
                {CITIES.map(c => <option key={c} value={c}>{c.split(',')[0]}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Seniority *</label>
              <select
                value={form.seniority_level}
                onChange={e => updateForm('seniority_level', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none appearance-none"
              >
                {SENIORITY.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Experience (yrs)</label>
              <input
                type="number"
                min="0" max="30"
                value={form.experience_years}
                onChange={e => updateForm('experience_years', e.target.value)}
                placeholder="0-30"
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Type</label>
              <select
                value={form.employment_type}
                onChange={e => updateForm('employment_type', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none appearance-none"
              >
                <option>Full-time</option>
                <option>Part-time</option>
                <option>Contract</option>
                <option>Internship</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Work</label>
              <select
                value={form.remote_type}
                onChange={e => updateForm('remote_type', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none appearance-none"
              >
                <option>On-site</option>
                <option>Remote</option>
                <option>Hybrid</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Education</label>
              <select
                value={form.education_required}
                onChange={e => updateForm('education_required', e.target.value)}
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-brand-500 outline-none appearance-none"
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
                placeholder="e.g. NVIDIA"
                className="w-full bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-500 outline-none transition-all"
              />
            </div>
          </div>

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

          <button
            type="submit"
            disabled={loading || !form.job_title.trim()}
            className="w-full py-4 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 text-white font-bold text-base hover:from-brand-500 hover:to-violet-500 transition-all shadow-lg shadow-brand-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? <><Loader2 size={18} className="animate-spin" /> Predicting...</> : 'Predict Salary'}
          </button>

          {error && <p className="text-rose-400 text-sm text-center font-medium">{error}</p>}
        </form>

        {/* Result Area */}
        <div className="relative">
          {result ? (
            <div className="space-y-4 sticky top-24">
              <div className="glass rounded-2xl p-8 border border-brand-500/20 shadow-xl shadow-brand-500/5">
                <p className="text-slate-400 text-sm mb-2 font-medium">Estimated Annual Salary</p>
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-5xl font-black text-white">
                    ${result.predicted_salary_usd?.toLocaleString()}
                  </span>
                  <span className="text-slate-500 font-medium">USD</span>
                </div>
                
                <div className="mt-8">
                  <div className="flex justify-between text-xs text-slate-500 mb-2 font-medium">
                    <span>${result.confidence_low?.toLocaleString()}</span>
                    <span className="text-slate-400">Confidence Range</span>
                    <span>${result.confidence_high?.toLocaleString()}</span>
                  </div>
                  <div className="h-2 bg-surface-800 rounded-full overflow-hidden relative border border-white/5">
                    <div 
                      className="absolute inset-y-0 bg-gradient-to-r from-brand-500 to-violet-500 rounded-full"
                      style={{
                        left: `${((result.confidence_low / result.predicted_salary_usd) * 0)}%`, // Simplified marker for sleek look
                        width: '100%' 
                      }}
                    />
                    <div 
                      className="absolute top-0 bottom-0 w-1 bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] z-10"
                      style={{
                        left: `${Math.min(95, Math.max(5, ((result.predicted_salary_usd - result.confidence_low) /
                          (result.confidence_high - result.confidence_low)) * 100))}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              <div className="glass rounded-2xl p-6 flex items-center gap-5">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-500 to-violet-600 flex items-center justify-center shrink-0 shadow-lg shadow-brand-500/20">
                  <span className="text-white font-black text-xl">{result.percentile}</span>
                </div>
                <div>
                  <p className="text-white font-bold text-lg">Top {100 - (result.percentile || 50)}%</p>
                  <p className="text-slate-400 text-sm">Competitiveness for this role and city</p>
                </div>
                <Award className="ml-auto text-amber-400" size={28} />
              </div>

              <button
                onClick={() => navigate(`/jobs?keyword=${encodeURIComponent(form.job_title)}&city=${encodeURIComponent(form.city)}`)}
                className="w-full py-4 rounded-xl glass border-white/10 text-white font-bold text-sm hover:bg-white/5 transition-all flex items-center justify-center gap-2"
              >
                Browse matching jobs <ArrowRight size={18} />
              </button>
              
              <div className="text-center">
                <p className="text-[10px] text-slate-600 uppercase tracking-widest font-bold">
                  Powered by {result.model_name} Model • RMSE: {result.model_rmse || 'N/A'}
                </p>
              </div>
            </div>
          ) : (
            <div className="glass rounded-2xl p-12 text-center sticky top-24 border-dashed border-white/10 flex flex-col items-center justify-center min-h-[400px]">
              <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center text-slate-500 mb-6">
                <DollarSign size={32} />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Awaiting Input</h3>
              <p className="text-slate-400 text-sm max-w-[200px] mx-auto">
                Fill in the job details or upload your resume to see salary insights.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
