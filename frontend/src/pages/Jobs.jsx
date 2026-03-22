import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Briefcase, ChevronLeft, ChevronRight } from 'lucide-react';
import { searchJobs } from '../api/client';
import JobCard from '../components/JobCard';
import FilterPanel from '../components/FilterPanel';

export default function Jobs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState({
    keyword: searchParams.get('keyword') || undefined,
    city: searchParams.get('city') || undefined,
    page: parseInt(searchParams.get('page') || '1'),
    page_size: 20,
  });
  const [data, setData] = useState({ results: [], total: 0, page: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        // Clean undefined values
        const params = {};
        Object.entries(filters).forEach(([k, v]) => {
          if (v !== undefined && v !== '' && v !== null) params[k] = v;
        });
        const result = await searchJobs(params);
        setData(result);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [filters]);

  const handleFilterChange = (newFilters) => {
    setFilters({ ...newFilters, page: 1, page_size: 20 });
  };

  const handleReset = () => {
    setFilters({ page: 1, page_size: 20 });
    setSearchParams({});
  };

  const totalPages = Math.ceil(data.total / (filters.page_size || 20));

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Briefcase className="text-brand-400" size={28} /> Jobs
        </h1>
        <p className="text-slate-400 mt-1">
          {loading ? 'Searching...' : `Showing ${data.results.length} of ${data.total} jobs`}
        </p>
      </div>

      {/* Keyword search */}
      <div className="mb-6">
        <input
          type="text"
          placeholder="Search by job title or company..."
          value={filters.keyword || ''}
          onChange={(e) => handleFilterChange({ ...filters, keyword: e.target.value || undefined })}
          className="w-full max-w-md bg-surface-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all"
        />
      </div>

      <div className="flex gap-6">
        <FilterPanel filters={filters} onChange={handleFilterChange} onReset={handleReset} />

        {/* Results */}
        <div className="flex-1 min-w-0">
          {error ? (
            <div className="glass rounded-xl p-10 text-center">
              <p className="text-red-400 mb-4">{error}</p>
              <button
                onClick={() => setFilters({ ...filters })}
                className="px-6 py-2.5 rounded-lg bg-brand-500/20 text-brand-300 text-sm font-medium hover:bg-brand-500/30 transition-all"
              >
                Retry
              </button>
            </div>
          ) : loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array(6).fill(0).map((_, i) => (
                <div key={i} className="skeleton h-48 rounded-xl" />
              ))}
            </div>
          ) : data.results.length === 0 ? (
            <div className="glass rounded-xl p-10 text-center">
              <Briefcase size={40} className="text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 text-lg">No jobs found</p>
              <p className="text-slate-500 text-sm mt-1">Try adjusting your filters</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.results.map((job) => (
                  <JobCard key={job.id} job={job} />
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-3 mt-8">
                  <button
                    onClick={() => setFilters({ ...filters, page: Math.max(1, filters.page - 1) })}
                    disabled={filters.page <= 1}
                    className="p-2.5 rounded-lg glass text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <div className="flex gap-1">
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      const start = Math.max(1, Math.min(filters.page - 2, totalPages - 4));
                      const pageNum = start + i;
                      if (pageNum > totalPages) return null;
                      return (
                        <button
                          key={pageNum}
                          onClick={() => setFilters({ ...filters, page: pageNum })}
                          className={`w-10 h-10 rounded-lg text-sm font-medium transition-all ${
                            filters.page === pageNum
                              ? 'bg-brand-500 text-white'
                              : 'glass text-slate-400 hover:text-white'
                          }`}
                        >
                          {pageNum}
                        </button>
                      );
                    })}
                  </div>
                  <button
                    onClick={() => setFilters({ ...filters, page: Math.min(totalPages, filters.page + 1) })}
                    disabled={filters.page >= totalPages}
                    className="p-2.5 rounded-lg glass text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  >
                    <ChevronRight size={18} />
                  </button>
                  <span className="text-slate-500 text-sm ml-2">
                    Page {filters.page} of {totalPages}
                  </span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
