import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Clock, Star } from 'lucide-react';
import { useAuth } from '../auth/AuthProvider';
import {
  listFavoriteJobs,
  listSavedOffers,
  listSavedPredictions,
  listSavedResumes,
} from '../api/userData';

export default function History() {
  const { configured, user, signInWithGoogle } = useAuth();
  const [data, setData] = useState({ predictions: [], offers: [], resumes: [], favorites: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!configured || !user) return;
    setLoading(true);
    setError(null);
    Promise.all([
      listSavedPredictions(user.id),
      listSavedOffers(user.id),
      listSavedResumes(user.id),
      listFavoriteJobs(user.id),
    ])
      .then(([predictions, offers, resumes, favorites]) => {
        setData({ predictions, offers, resumes, favorites });
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [configured, user]);

  if (!configured) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <p className="display-text text-4xl text-white">SUPABASE NOT CONFIGURED</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <Clock size={48} className="text-brand-500 mx-auto mb-5" />
        <p className="display-text text-4xl text-white mb-6">SIGN IN TO VIEW HISTORY</p>
        <button onClick={signInWithGoogle} className="brutal-btn">Sign in with Google</button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-10">
      <h1 className="display-text text-5xl md:text-7xl mb-4 flex items-center gap-4">
        <Clock className="text-brand-500" size={46} strokeWidth={3} /> SAVED HISTORY
      </h1>
      <p className="text-lg font-bold uppercase tracking-widest text-slate-400 mb-8 border-l-4 border-brand-500 pl-4">
        Your saved predictions, resume analyses, offers, and favorite jobs.
      </p>
      {loading && <p className="text-slate-400 font-bold uppercase">Loading...</p>}
      {error && <p className="text-brand-accent font-bold uppercase">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <HistorySection title="Predictions" items={data.predictions} render={(item) => (
          <>
            <p className="font-bold uppercase">{item.input?.job_title || 'Prediction'}</p>
            <p className="text-brand-500 font-bold">${item.result?.predicted_salary_usd?.toLocaleString?.() || 'N/A'}</p>
          </>
        )} />

        <HistorySection title="Offers" items={data.offers} render={(item) => (
          <>
            <p className="font-bold uppercase">{item.input?.job_title || 'Offer'}</p>
            <p className="text-brand-500 font-bold">{item.result?.verdict || 'N/A'} · ${item.result?.total_comp_usd?.toLocaleString?.() || 'N/A'}</p>
          </>
        )} />

        <HistorySection title="Resumes" items={data.resumes} render={(item) => (
          <>
            <p className="font-bold uppercase">{item.extracted_data?.job_title || 'Resume analysis'}</p>
            <p className="text-brand-500 font-bold">{item.extracted_data?.experience_years ?? 0} yrs · {item.gap_analysis?.missing_high_value_skills?.length || 0} gaps</p>
          </>
        )} />

        <HistorySection title="Favorite Jobs" items={data.favorites} render={(item) => (
          <>
            <p className="font-bold uppercase">{item.job_snapshot?.job_title || `Job ${item.job_id}`}</p>
            <Link to={`/jobs/${item.job_id}`} className="text-brand-500 font-bold hover:underline inline-flex items-center gap-2">
              <Star size={14} /> View job
            </Link>
          </>
        )} />
      </div>
    </div>
  );
}

function HistorySection({ title, items, render }) {
  return (
    <div className="brutal-card p-6">
      <h2 className="display-text text-2xl mb-4">{title}</h2>
      {items.length === 0 ? (
        <p className="text-slate-500 font-bold uppercase text-sm">Nothing saved yet.</p>
      ) : (
        <div className="space-y-3">
          {items.map(item => (
            <div key={item.id} className="border-b border-white/10 pb-3 last:border-0">
              {render(item)}
              <p className="text-slate-500 text-xs font-bold uppercase mt-1">
                {new Date(item.created_at).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
