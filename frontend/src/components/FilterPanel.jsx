import { useState } from 'react';
import { SlidersHorizontal, X } from 'lucide-react';

const CITIES = [
  'New York, NY, USA', 'San Francisco, CA, USA', 'Seattle, WA, USA',
  'Austin, TX, USA', 'Chicago, IL, USA', 'Boston, MA, USA',
  'London, UK', 'Berlin, Germany', 'Toronto, Canada',
  'Bangalore, India', 'Singapore', 'Sydney, Australia',
  'Dublin, Ireland', 'Amsterdam, Netherlands', 'Dubai, UAE',
  'Tokyo, Japan', 'Remote',
];

const SENIORITY_LEVELS = [
  'Entry Level (0-2 years)', 'Associate (1-3 years)', 'Mid-Level (2-5 years)',
  'Senior (5+ years)', 'Staff (8+ years)', 'Director (8+ years)',
];

const TOP_SKILLS = [
  'Python', 'SQL', 'Machine Learning', 'AWS', 'JavaScript', 'React',
  'Docker', 'Kubernetes', 'TensorFlow', 'PyTorch', 'Java', 'Spark',
  'Tableau', 'Power BI', 'NLP', 'Deep Learning', 'Git', 'Azure',
];

export default function FilterPanel({ filters, onChange, onReset }) {
  const [showMobile, setShowMobile] = useState(false);

  const updateFilter = (key, value) => {
    onChange({ ...filters, [key]: value });
  };

  const toggleSkill = (skill) => {
    const current = filters.skills ? filters.skills.split(',').map(s => s.trim()).filter(Boolean) : [];
    const updated = current.includes(skill)
      ? current.filter(s => s !== skill)
      : [...current, skill];
    updateFilter('skills', updated.join(','));
  };

  const activeSkills = filters.skills ? filters.skills.split(',').map(s => s.trim()).filter(Boolean) : [];

  const filterContent = (
    <div className="space-y-5">
      {/* City */}
      <div>
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">City</label>
        <select
          value={filters.city || ''}
          onChange={(e) => updateFilter('city', e.target.value || undefined)}
          className="w-full bg-surface-900 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 outline-none transition-all"
        >
          <option value="">All Cities</option>
          {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Remote type */}
      <div>
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Work Type</label>
        <div className="grid grid-cols-2 gap-1.5">
          {['All', 'Remote', 'Hybrid', 'On-site'].map(type => (
            <button
              key={type}
              onClick={() => updateFilter('remote_type', type === 'All' ? undefined : type)}
              className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                (type === 'All' && !filters.remote_type) || filters.remote_type === type
                  ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30'
                  : 'bg-white/5 text-slate-400 border border-transparent hover:bg-white/10'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Seniority */}
      <div>
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Seniority</label>
        <select
          value={filters.seniority_level || ''}
          onChange={(e) => updateFilter('seniority_level', e.target.value || undefined)}
          className="w-full bg-surface-900 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 outline-none transition-all"
        >
          <option value="">All Levels</option>
          {SENIORITY_LEVELS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Salary range */}
      <div>
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Salary Range (USD)</label>
        <div className="flex gap-2">
          <input
            type="number"
            placeholder="Min"
            value={filters.min_salary || ''}
            onChange={(e) => updateFilter('min_salary', e.target.value ? parseInt(e.target.value) : undefined)}
            className="w-1/2 bg-surface-900 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:border-brand-500 outline-none"
          />
          <input
            type="number"
            placeholder="Max"
            value={filters.max_salary || ''}
            onChange={(e) => updateFilter('max_salary', e.target.value ? parseInt(e.target.value) : undefined)}
            className="w-1/2 bg-surface-900 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:border-brand-500 outline-none"
          />
        </div>
      </div>

      {/* Skills */}
      <div>
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Skills</label>
        <div className="flex flex-wrap gap-1.5">
          {TOP_SKILLS.map(skill => (
            <button
              key={skill}
              onClick={() => toggleSkill(skill)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                activeSkills.includes(skill)
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'bg-white/5 text-slate-400 border border-transparent hover:bg-white/10'
              }`}
            >
              {skill}
            </button>
          ))}
        </div>
      </div>

      {/* Source */}
      <div>
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Source</label>
        <div className="flex gap-2">
          {['LinkedIn', 'Indeed', 'Glassdoor'].map(source => (
            <button
              key={source}
              onClick={() => updateFilter('source', filters.source === source ? undefined : source)}
              className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                filters.source === source
                  ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30'
                  : 'bg-white/5 text-slate-400 border border-transparent hover:bg-white/10'
              }`}
            >
              {source}
            </button>
          ))}
        </div>
      </div>

      {/* Reset */}
      <button
        onClick={onReset}
        className="w-full py-2.5 rounded-lg text-sm font-medium text-slate-400 border border-white/10 hover:bg-white/5 transition-all"
      >
        Reset Filters
      </button>
    </div>
  );

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setShowMobile(!showMobile)}
        className="lg:hidden flex items-center gap-2 px-4 py-2.5 rounded-lg glass text-sm font-medium text-slate-300 mb-4"
      >
        <SlidersHorizontal size={16} /> Filters
      </button>

      {/* Mobile overlay */}
      {showMobile && (
        <div className="lg:hidden fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" onClick={() => setShowMobile(false)}>
          <div className="absolute right-0 top-0 h-full w-80 bg-surface-900 p-5 overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-white font-semibold">Filters</h3>
              <button onClick={() => setShowMobile(false)} className="text-slate-400 hover:text-white">
                <X size={20} />
              </button>
            </div>
            {filterContent}
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <div className="hidden lg:block w-72 shrink-0">
        <div className="glass rounded-xl p-5 sticky top-24">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <SlidersHorizontal size={16} className="text-brand-400" /> Filters
          </h3>
          {filterContent}
        </div>
      </div>
    </>
  );
}
