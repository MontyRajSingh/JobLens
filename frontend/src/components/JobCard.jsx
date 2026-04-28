import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Building2, ExternalLink, Star } from 'lucide-react';
import { useAuth } from '../auth/AuthProvider';
import { addFavoriteJob, getFavoriteJob, removeFavoriteJob } from '../api/userData';

function remoteBadge(type) {
  if (!type) return null;
  const t = type.toLowerCase();
  if (t.includes('remote')) return <span className="badge badge-remote">Remote</span>;
  if (t.includes('hybrid')) return <span className="badge badge-hybrid">Hybrid</span>;
  return <span className="badge badge-onsite">On-site</span>;
}

export default function JobCard({ job }) {
  const { configured, user, signInWithGoogle } = useAuth();
  const [favorite, setFavorite] = useState(false);
  const [savingFavorite, setSavingFavorite] = useState(false);
  const skills = job.skills_required
    ? job.skills_required.split(',').map(s => s.trim()).filter(Boolean).slice(0, 4)
    : [];

  useEffect(() => {
    let active = true;
    if (!configured || !user || !job.id) {
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
  }, [configured, user, job.id]);

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

  return (
    <div className="glass rounded-xl p-5 hover:border-brand-500/30 transition-all duration-300 group hover:-translate-y-0.5 hover:shadow-lg hover:shadow-brand-500/5">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold text-base truncate group-hover:text-brand-300 transition-colors">
            {job.job_title}
          </h3>
          <div className="flex items-center gap-2 mt-1 text-slate-400 text-sm">
            <Building2 size={14} className="shrink-0" />
            {job.company_name ? (
              <Link to={`/companies/${encodeURIComponent(job.company_name)}`} className="truncate hover:text-brand-300">
                {job.company_name}
              </Link>
            ) : (
              <span className="truncate">Company not listed</span>
            )}
          </div>
        </div>
        {job.salary_usd_numeric ? (
          <div className="text-right shrink-0">
            <p className="text-brand-300 font-bold text-lg">${job.salary_usd_numeric.toLocaleString()}</p>
            <p className="text-slate-500 text-xs">USD/yr</p>
          </div>
        ) : (
          <div className="shrink-0">
            <span className="text-slate-500 text-sm italic">Not disclosed</span>
          </div>
        )}
        {configured && (
          <button
            type="button"
            onClick={toggleFavorite}
            disabled={savingFavorite || !job.id}
            className={`shrink-0 border-2 p-2 ${favorite ? 'bg-brand-500 text-black border-brand-500' : 'bg-black text-white border-white'}`}
            title={favorite ? 'Remove favorite' : 'Favorite job'}
          >
            <Star size={16} fill={favorite ? 'currentColor' : 'none'} />
          </button>
        )}
      </div>

      <div className="flex items-center gap-2 text-slate-400 text-sm mb-3">
        <MapPin size={14} className="shrink-0" />
        <span className="truncate">{job.city}</span>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {remoteBadge(job.remote_type)}
        {job.seniority_level && (
          <span className="badge badge-seniority">{job.seniority_level.split('(')[0].trim()}</span>
        )}
        {job.source_website && (
          <span className="badge badge-source">{job.source_website}</span>
        )}
        {job.is_faang === 1 && (
          <span className="badge bg-amber-500/20 text-amber-300 border border-amber-500/30">⭐ FAANG</span>
        )}
      </div>

      {/* Skills */}
      {skills.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {skills.map(s => (
            <span key={s} className="badge badge-skill text-[11px]">{s}</span>
          ))}
          {job.skills_required && job.skills_required.split(',').length > 4 && (
            <span className="text-slate-500 text-xs self-center">+{job.skills_required.split(',').length - 4} more</span>
          )}
        </div>
      )}

      <Link
        to={`/jobs/${job.id}`}
        className="flex items-center gap-1.5 text-brand-400 text-sm font-medium hover:text-brand-300 transition-colors"
      >
        View Details <ExternalLink size={14} />
      </Link>
    </div>
  );
}
