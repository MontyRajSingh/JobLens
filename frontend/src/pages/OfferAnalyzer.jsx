import { useState } from 'react';
import { BriefcaseBusiness, Loader2 } from 'lucide-react';
import { analyzeOffer } from '../api/client';
import { useAuth } from '../auth/AuthProvider';
import { saveOffer } from '../api/userData';

const CITIES = [
  'New York, NY, USA', 'San Francisco, CA, USA', 'Seattle, WA, USA',
  'London, UK', 'Berlin, Germany', 'Toronto, Canada', 'Singapore',
  'Sydney, Australia', 'Dubai, UAE', 'Bengaluru, India', 'Gurugram, India',
];

const SENIORITY = [
  'Entry Level (0-2 years)', 'Associate (1-3 years)', 'Mid-Level (2-5 years)',
  'Senior (5+ years)', 'Staff (8+ years)', 'Director (8+ years)',
];

export default function OfferAnalyzer() {
  const { configured, user, signInWithGoogle } = useAuth();
  const [form, setForm] = useState({
    job_title: '',
    city: 'New York, NY, USA',
    seniority_level: 'Mid-Level (2-5 years)',
    skills: '',
    experience_years: 0,
    employment_type: 'Full-time',
    remote_type: 'On-site',
    company_name: '',
    education_required: '',
    has_equity: false,
    has_bonus: false,
    base_salary_usd: '',
    annual_bonus_usd: '',
    annual_equity_usd: '',
  });
  const [result, setResult] = useState(null);
  const [lastPayload, setLastPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState(null);
  const [error, setError] = useState(null);

  const update = (key, value) => setForm(prev => ({ ...prev, [key]: value }));

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload = {
        ...form,
        skills: form.skills ? form.skills.split(',').map(s => s.trim()).filter(Boolean) : [],
        experience_years: parseFloat(form.experience_years || 0),
        base_salary_usd: parseInt(form.base_salary_usd || 0, 10),
        annual_bonus_usd: parseInt(form.annual_bonus_usd || 0, 10),
        annual_equity_usd: parseInt(form.annual_equity_usd || 0, 10),
        has_bonus: Number(form.annual_bonus_usd || 0) > 0,
        has_equity: Number(form.annual_equity_usd || 0) > 0,
      };
      const data = await analyzeOffer(payload);
      setLastPayload(payload);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const saveCurrentOffer = async () => {
    setSaving(true);
    setSaveMessage(null);
    try {
      if (!configured) throw new Error('Supabase is not configured.');
      if (!user) {
        await signInWithGoogle();
        return;
      }
      await saveOffer(user.id, lastPayload, result);
      setSaveMessage('Offer analysis saved.');
    } catch (err) {
      setSaveMessage(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      <h1 className="display-text text-5xl md:text-7xl mb-4 flex items-center gap-4">
        <BriefcaseBusiness className="text-brand-500" size={46} strokeWidth={3} /> OFFER ANALYZER
      </h1>
      <p className="text-lg font-bold uppercase tracking-widest text-slate-400 mb-8 border-l-4 border-brand-500 pl-4">
        Compare a compensation offer against market evidence and the salary model.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        <form onSubmit={submit} className="space-y-5">
          <input required value={form.job_title} onChange={e => update('job_title', e.target.value)} placeholder="JOB TITLE" className="w-full bg-black border-2 border-white px-4 py-4 text-white font-bold uppercase" />
          <input value={form.company_name} onChange={e => update('company_name', e.target.value)} placeholder="COMPANY" className="w-full bg-black border-2 border-white px-4 py-4 text-white font-bold uppercase" />

          <div className="grid grid-cols-2 gap-4">
            <select value={form.city} onChange={e => update('city', e.target.value)} className="bg-black border-2 border-white px-4 py-4 text-white font-bold uppercase">
              {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={form.seniority_level} onChange={e => update('seniority_level', e.target.value)} className="bg-black border-2 border-white px-4 py-4 text-white font-bold uppercase">
              {SENIORITY.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <input required type="number" min="0" value={form.base_salary_usd} onChange={e => update('base_salary_usd', e.target.value)} placeholder="BASE $" className="bg-black border-2 border-white px-4 py-4 text-white font-bold" />
            <input type="number" min="0" value={form.annual_bonus_usd} onChange={e => update('annual_bonus_usd', e.target.value)} placeholder="BONUS $" className="bg-black border-2 border-white px-4 py-4 text-white font-bold" />
            <input type="number" min="0" value={form.annual_equity_usd} onChange={e => update('annual_equity_usd', e.target.value)} placeholder="EQUITY $" className="bg-black border-2 border-white px-4 py-4 text-white font-bold" />
          </div>

          <input value={form.skills} onChange={e => update('skills', e.target.value)} placeholder="SKILLS, COMMA SEPARATED" className="w-full bg-black border-2 border-white px-4 py-4 text-white font-bold uppercase" />

          <button disabled={loading} className="brutal-btn w-full disabled:opacity-50">
            {loading ? <><Loader2 className="animate-spin" size={20} /> ANALYZING...</> : 'ANALYZE OFFER'}
          </button>
          {error && <p className="text-brand-accent font-bold uppercase">{error}</p>}
        </form>

        <div className="sticky top-28 h-fit">
          {result ? (
            <div className="brutal-card p-8">
              <p className="text-slate-400 font-bold uppercase tracking-widest mb-3">Verdict</p>
              <p className="display-text text-6xl text-brand-500 mb-6">{result.verdict}</p>
              <div className="space-y-3 font-bold uppercase">
                <div className="flex justify-between"><span className="text-slate-400">Total comp</span><span>${result.total_comp_usd.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Market reference</span><span>${result.market_reference_usd.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Difference</span><span>{result.difference_usd >= 0 ? '+' : ''}${result.difference_usd.toLocaleString()} ({result.difference_pct}%)</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Evidence jobs</span><span>{result.evidence_count}</span></div>
              </div>
              <p className="mt-6 text-slate-300 font-bold uppercase tracking-wider">{result.recommendation}</p>
              <button
                type="button"
                onClick={saveCurrentOffer}
                disabled={saving || !result || !configured}
                className="mt-6 w-full py-3 border-2 border-brand-500 text-brand-500 hover:bg-brand-500 hover:text-black transition-colors font-bold uppercase tracking-widest disabled:opacity-50"
              >
                {saving ? 'SAVING...' : !configured ? 'SUPABASE NOT CONFIGURED' : user ? 'SAVE OFFER ANALYSIS' : 'SIGN IN TO SAVE'}
              </button>
              {saveMessage && (
                <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mt-3">{saveMessage}</p>
              )}
            </div>
          ) : (
            <div className="border-4 border-white border-dashed p-12 text-center bg-black/50">
              <p className="display-text text-3xl text-slate-300">ENTER OFFER DETAILS</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
