import { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, MapPin, Building2, Clock, Briefcase, GraduationCap, DollarSign, Star } from 'lucide-react';
import { getJob } from '../api/client';
import { useAuth } from '../auth/AuthProvider';
import { addFavoriteJob, getFavoriteJob, removeFavoriteJob } from '../api/userData';

export default function JobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { configured, user, signInWithGoogle } = useAuth();
  const [job, setJob] = useState(null);
  const [favorite, setFavorite] = useState(false);
  const [savingFavorite, setSavingFavorite] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await getJob(id);
        setJob(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  useEffect(() => {
    let active = true;
    if (!configured || !user || !job?.id) {
      setFavorite(false);
      return undefined;
    }
    getFavoriteJob(user.id, job.id)
      .then(row => {
        if (active) setFavorite(Boolean(row));
      })
      .catch(() => {
        if (active) setFavorite(false);
      });
    return () => {
      active = false;
    };
  }, [configured, user, job?.id]);

  const toggleFavorite = async () => {
    setSavingFavorite(true);
    try {
      if (!configured) throw new Error('Supabase is not configured.');
      if (!user) {
        await signInWithGoogle();
        return;
      }
      if (favorite) {
        await removeFavoriteJob(user.id, job.id);
        setFavorite(false);
      } else {
        await addFavoriteJob(user.id, job);
        setFavorite(true);
      }
    } catch (err) {
      alert(err.message);
    } finally {
      setSavingFavorite(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="skeleton h-8 w-48 mb-6" />
        <div className="skeleton h-64 rounded-xl mb-4" />
        <div className="skeleton h-96 rounded-xl" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <p className="text-red-400 text-lg mb-4">{error || 'Job not found'}</p>
        <button onClick={() => navigate('/jobs')} className="px-6 py-3 rounded-lg bg-brand-500/20 text-brand-300 font-medium">
          ← Back to Jobs
        </button>
      </div>
    );
  }

  const skills = job.skills_required?.split(',').map(s => s.trim()).filter(Boolean) || [];

  const details = [
    { icon: Building2, label: 'Company', value: job.company_name },
    { icon: MapPin, label: 'Location', value: job.city },
    { icon: Briefcase, label: 'Employment', value: job.employment_type },
    { icon: Clock, label: 'Experience', value: job.experience_required },
    { icon: GraduationCap, label: 'Education', value: job.education_required },
    { icon: DollarSign, label: 'Salary', value: job.salary || (job.salary_usd_numeric ? `$${job.salary_usd_numeric.toLocaleString()} USD/yr` : null) },
  ].filter(d => d.value);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-slate-400 hover:text-white text-sm font-medium mb-6 transition-colors"
      >
        <ArrowLeft size={16} /> Back to results
      </button>

      {/* Header */}
      <div className="glass rounded-xl p-6 mb-6">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-white mb-2">{job.job_title}</h1>
            {job.company_name ? (
              <Link to={`/companies/${encodeURIComponent(job.company_name)}`} className="text-slate-400 text-lg hover:text-brand-300">
                {job.company_name}
              </Link>
            ) : (
              <p className="text-slate-400 text-lg">Company not listed</p>
            )}
            <div className="flex items-center gap-2 mt-2 text-slate-500">
              <MapPin size={14} /> {job.city}
            </div>
          </div>

          {job.salary_usd_numeric && (
            <div className="text-right shrink-0">
              <p className="text-3xl font-bold text-brand-300">${job.salary_usd_numeric.toLocaleString()}</p>
              <p className="text-slate-500">USD / year</p>
            </div>
          )}
          {configured && (
            <button
              type="button"
              onClick={toggleFavorite}
              disabled={savingFavorite || !job.id}
              className={`shrink-0 border-2 px-4 py-3 font-bold uppercase tracking-widest flex items-center gap-2 ${favorite ? 'bg-brand-500 text-black border-brand-500' : 'bg-black text-white border-white'}`}
            >
              <Star size={18} fill={favorite ? 'currentColor' : 'none'} />
              {favorite ? 'Favorited' : 'Favorite'}
            </button>
          )}
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-2 mt-4">
          {job.remote_type && (
            <span className={`badge ${
              job.remote_type.toLowerCase().includes('remote') ? 'badge-remote' :
              job.remote_type.toLowerCase().includes('hybrid') ? 'badge-hybrid' : 'badge-onsite'
            }`}>
              {job.remote_type}
            </span>
          )}
          {job.seniority_level && <span className="badge badge-seniority">{job.seniority_level}</span>}
          {job.source_website && <span className="badge badge-source">{job.source_website}</span>}
          {job.has_equity && <span className="badge bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">💰 Equity</span>}
          {job.has_bonus && <span className="badge bg-amber-500/20 text-amber-300 border border-amber-500/30">🎯 Bonus</span>}
          {job.is_faang === 1 && <span className="badge bg-amber-500/20 text-amber-300 border border-amber-500/30">⭐ FAANG</span>}
        </div>

        {/* Apply button */}
        {job.job_link && (
          <a
            href={job.job_link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 mt-5 px-6 py-3 rounded-xl bg-gradient-to-r from-brand-600 to-brand-500 text-white font-semibold text-sm hover:from-brand-500 hover:to-brand-400 transition-all shadow-lg shadow-brand-500/20"
          >
            Apply on {job.source_website} <ExternalLink size={16} />
          </a>
        )}
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {details.map((d, i) => (
          <div key={i} className="glass rounded-xl p-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-brand-500/10 flex items-center justify-center shrink-0">
              <d.icon size={18} className="text-brand-400" />
            </div>
            <div>
              <p className="text-slate-500 text-xs">{d.label}</p>
              <p className="text-white text-sm font-medium">{d.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Skills */}
      {skills.length > 0 && (
        <div className="glass rounded-xl p-5 mb-6">
          <h3 className="text-white font-semibold mb-3">Skills Required</h3>
          <div className="flex flex-wrap gap-2">
            {skills.map(s => (
              <span key={s} className="badge badge-skill">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Description */}
      {job.job_description && (
        <div className="glass rounded-xl p-5">
          <h3 className="text-white font-semibold mb-3">Job Description</h3>
          <div className="max-h-96 overflow-y-auto pr-2 text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
            {job.job_description}
          </div>
        </div>
      )}
    </div>
  );
}
