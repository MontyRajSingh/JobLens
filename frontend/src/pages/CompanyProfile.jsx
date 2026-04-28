import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Building2, MapPin } from 'lucide-react';
import { getCompanyProfile } from '../api/client';
import JobCard from '../components/JobCard';

export default function CompanyProfile() {
  const { companyName } = useParams();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        setProfile(await getCompanyProfile(companyName));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [companyName]);

  if (loading) {
    return <div className="max-w-6xl mx-auto px-4 py-10"><div className="skeleton h-64 rounded-xl" /></div>;
  }

  if (error || !profile) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <p className="text-red-400 font-bold uppercase">{error || 'Company not found'}</p>
        <Link to="/jobs" className="brutal-btn mt-6">Back to jobs</Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-10">
      <h1 className="display-text text-5xl md:text-7xl mb-4 flex items-center gap-4">
        <Building2 className="text-brand-500" size={46} strokeWidth={3} /> {profile.company_name}
      </h1>
      <p className="text-lg font-bold uppercase tracking-widest text-slate-400 mb-8 border-l-4 border-brand-500 pl-4">
        Compensation profile from scraped JobLens market data.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          ['Jobs', profile.job_count],
          ['Median salary', profile.median_salary ? `$${Math.round(profile.median_salary).toLocaleString()}` : 'N/A'],
          ['Equity mentions', `${profile.equity_frequency_pct}%`],
          ['Remote mentions', `${profile.remote_frequency_pct}%`],
        ].map(([label, value]) => (
          <div key={label} className="brutal-card p-5">
            <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">{label}</p>
            <p className="text-2xl font-bold text-white mt-2">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="brutal-card p-6">
          <h2 className="display-text text-2xl mb-4">Top Roles</h2>
          <div className="space-y-3">
            {profile.top_roles.map(role => (
              <div key={role.role} className="flex justify-between gap-4 border-b border-white/10 pb-2 font-bold uppercase text-sm">
                <span>{role.role}</span>
                <span className="text-brand-500">{role.count} jobs</span>
              </div>
            ))}
          </div>
        </div>

        <div className="brutal-card p-6">
          <h2 className="display-text text-2xl mb-4">Top Cities</h2>
          <div className="space-y-3">
            {profile.top_cities.map(city => (
              <div key={city.city} className="flex justify-between gap-4 border-b border-white/10 pb-2 font-bold uppercase text-sm">
                <span className="flex items-center gap-2"><MapPin size={14} /> {city.city}</span>
                <span className="text-brand-500">{city.count} jobs</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <h2 className="display-text text-3xl mb-4">Recent Jobs</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {profile.recent_jobs.map(job => <JobCard key={job.id} job={job} />)}
      </div>
    </div>
  );
}
