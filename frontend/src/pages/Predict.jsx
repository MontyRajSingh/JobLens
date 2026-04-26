import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { DollarSign, TrendingUp, Award, ArrowRight, Loader2, UploadCloud } from 'lucide-react';
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
      
      // Update form state with extracted values
      setForm(prev => {
        const newForm = { ...prev, ...extracted_data };
        
        // Ensure skills are proper array
        if (extracted_data.skills && Array.isArray(extracted_data.skills)) {
          // Keep only skills that match our preset list to avoid random text
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
      // Reset input so same file can be selected again
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <h1 className="display-text text-5xl md:text-7xl mb-4 flex items-center gap-4">
        <DollarSign className="text-brand-500" size={48} strokeWidth={3} /> SALARY PREDICTOR
      </h1>
      <p className="text-xl font-bold uppercase tracking-widest text-slate-400 mb-8 border-l-4 border-brand-500 pl-4">
        AI-powered salary prediction based on real market data.
      </p>

      {/* Resume Upload CTA */}
      <div className="mb-12 border-4 border-brand-500 bg-brand-500/10 p-6 flex flex-col md:flex-row items-center justify-between gap-6 shadow-brutal">
        <div>
          <h2 className="display-text text-3xl text-brand-500 mb-2">AUTO-FILL WITH RESUME</h2>
          <p className="font-bold text-white uppercase tracking-wider text-sm">
            Upload your PDF resume to instantly extract your skills, experience, and role using Nemotron 3 AI.
          </p>
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
          className="brutal-btn whitespace-nowrap disabled:opacity-50"
        >
          {uploading ? <Loader2 className="animate-spin" size={20} /> : <UploadCloud size={20} />} 
          {uploading ? 'PARSING...' : 'UPLOAD RESUME (PDF)'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Job Title */}
          <div>
            <label className="block text-sm font-bold text-white uppercase tracking-wider mb-2">Job Title *</label>
            <input
              type="text"
              value={form.job_title}
              onChange={e => updateForm('job_title', e.target.value)}
              placeholder="E.G. SENIOR DATA SCIENTIST"
              required
              className="w-full bg-black border-2 border-white px-4 py-4 text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none uppercase font-bold tracking-wider"
            />
          </div>

          {/* City + Seniority */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-bold text-white uppercase tracking-wider mb-2">City *</label>
              <select
                value={form.city}
                onChange={e => updateForm('city', e.target.value)}
                className="w-full bg-black border-2 border-white px-4 py-4 text-white focus:border-brand-500 outline-none uppercase font-bold tracking-wider appearance-none"
              >
                {CITIES.map(c => <option key={c} value={c}>{c.split(',')[0]}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-bold text-white uppercase tracking-wider mb-2">Seniority *</label>
              <select
                value={form.seniority_level}
                onChange={e => updateForm('seniority_level', e.target.value)}
                className="w-full bg-black border-2 border-white px-4 py-4 text-white focus:border-brand-500 outline-none uppercase font-bold tracking-wider appearance-none"
              >
                {SENIORITY.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* Experience + Employment + Remote */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-bold text-white uppercase tracking-wider mb-2">Exp (yrs)</label>
              <input
                type="number"
                min="0" max="30"
                value={form.experience_years || ''}
                onChange={e => updateForm('experience_years', e.target.value)}
                placeholder="0-30"
                className="w-full bg-black border-2 border-white px-4 py-4 text-white placeholder-slate-500 focus:border-brand-500 outline-none font-bold"
              />
            </div>
            <div>
              <label className="block text-sm font-bold text-white uppercase tracking-wider mb-2">Type</label>
              <select
                value={form.employment_type}
                onChange={e => updateForm('employment_type', e.target.value)}
                className="w-full bg-black border-2 border-white px-4 py-4 text-white focus:border-brand-500 outline-none uppercase font-bold appearance-none"
              >
                <option>Full-time</option>
                <option>Part-time</option>
                <option>Contract</option>
                <option>Internship</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-bold text-white uppercase tracking-wider mb-2">Work</label>
              <select
                value={form.remote_type}
                onChange={e => updateForm('remote_type', e.target.value)}
                className="w-full bg-black border-2 border-white px-4 py-4 text-white focus:border-brand-500 outline-none uppercase font-bold appearance-none"
              >
                <option>On-site</option>
                <option>Remote</option>
                <option>Hybrid</option>
              </select>
            </div>
          </div>

          {/* Education + Company */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-bold text-white uppercase tracking-wider mb-2">Education</label>
              <select
                value={form.education_required}
                onChange={e => updateForm('education_required', e.target.value)}
                className="w-full bg-black border-2 border-white px-4 py-4 text-white focus:border-brand-500 outline-none uppercase font-bold appearance-none"
              >
                <option value="">Not specified</option>
                <option>Bachelor's</option>
                <option>Master's</option>
                <option>PhD</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-bold text-white uppercase tracking-wider mb-2">Company</label>
              <input
                type="text"
                value={form.company_name}
                onChange={e => updateForm('company_name', e.target.value)}
                placeholder="E.G. GOOGLE"
                className="w-full bg-black border-2 border-white px-4 py-4 text-white placeholder-slate-500 focus:border-brand-500 outline-none uppercase font-bold tracking-wider"
              />
            </div>
          </div>

          {/* Toggles */}
          <div className="flex gap-4">
            {[
              { key: 'has_equity', label: '💰 EQUITY' },
              { key: 'has_bonus', label: '🎯 BONUS' },
            ].map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => updateForm(key, !form[key])}
                className={`flex-1 px-4 py-4 border-2 font-bold uppercase tracking-widest transition-all ${
                  form[key]
                    ? 'bg-brand-500 text-black border-brand-500 shadow-brutal'
                    : 'bg-black text-white border-white hover:bg-surface-800'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Skills */}
          <div>
            <label className="block text-sm font-bold text-white uppercase tracking-wider mb-2">
              Skills ({form.skills.length})
            </label>
            <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto p-4 bg-black border-2 border-white">
              {SKILLS.map(skill => (
                <button
                  key={skill}
                  type="button"
                  onClick={() => toggleSkill(skill)}
                  className={`px-3 py-1 font-bold uppercase text-xs border-2 transition-all ${
                    form.skills.includes(skill)
                      ? 'bg-white text-black border-white'
                      : 'bg-black text-slate-500 border-slate-500 hover:text-white hover:border-white'
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
            className="brutal-btn w-full text-lg mt-4 disabled:opacity-50 disabled:shadow-none"
          >
            {loading ? <><Loader2 size={20} className="animate-spin" /> PREDICTING...</> : 'PREDICT SALARY'}
          </button>

          {error && <p className="text-brand-accent font-bold mt-2 uppercase">{error}</p>}
        </form>

        {/* Result */}
        <div>
          {result ? (
            <div className="space-y-6 sticky top-28">
              {/* Main prediction */}
              <div className="brutal-card p-8">
                <p className="text-slate-400 font-bold uppercase tracking-widest mb-4">PREDICTED SALARY</p>
                <p className="display-text text-7xl md:text-8xl text-brand-500 mb-2 leading-none">
                  ${result.predicted_salary_usd?.toLocaleString()}
                </p>
                <p className="font-bold text-white uppercase tracking-widest">USD / YEAR</p>

                {/* Confidence bar */}
                <div className="mt-8">
                  <div className="flex justify-between font-bold text-sm uppercase text-slate-400 mb-2">
                    <span>${result.confidence_low?.toLocaleString()}</span>
                    <span className="text-white">RANGE</span>
                    <span>${result.confidence_high?.toLocaleString()}</span>
                  </div>
                  <div className="confidence-bar">
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
              <div className="brutal-card p-6 flex items-center gap-6">
                <div className="w-16 h-16 bg-white border-2 border-black shadow-brutal-pink flex items-center justify-center shrink-0">
                  <span className="text-black font-bold display-text text-3xl">{result.percentile}</span>
                </div>
                <div>
                  <p className="text-brand-500 font-bold uppercase tracking-widest text-lg">TOP {100 - (result.percentile || 50)}%</p>
                  <p className="text-slate-400 font-bold uppercase">FOR THIS ROLE & CITY</p>
                </div>
                <Award className="ml-auto text-brand-accent" size={32} />
              </div>

              {/* Model info */}
              <div className="flex items-center justify-between font-bold text-xs uppercase text-slate-500 border-t-2 border-white/20 pt-4">
                <span>MODEL: {result.model_name} v{result.model_version}</span>
              </div>

              {/* Browse similar */}
              <button
                onClick={() => navigate(`/jobs?keyword=${encodeURIComponent(form.job_title)}&city=${encodeURIComponent(form.city)}`)}
                className="w-full py-4 border-2 border-white bg-black hover:bg-white hover:text-black transition-colors font-bold uppercase tracking-widest flex items-center justify-center gap-3 mt-4"
              >
                BROWSE SIMILAR JOBS <ArrowRight size={20} strokeWidth={3} />
              </button>
            </div>
          ) : (
            <div className="border-4 border-white border-dashed p-12 text-center sticky top-28 h-96 flex flex-col items-center justify-center bg-black/50">
              <DollarSign size={64} className="text-white mb-6" strokeWidth={1} />
              <p className="display-text text-3xl text-slate-300">AWAITING INPUT</p>
              <p className="font-bold text-slate-500 uppercase tracking-widest mt-4">FILL OUT THE FORM TO SEE PREDICTIONS</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
