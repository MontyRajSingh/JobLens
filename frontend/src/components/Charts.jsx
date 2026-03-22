import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Cell, Legend
} from 'recharts';
import { AlertCircle, RefreshCw } from 'lucide-react';

const COLORS = ['#818cf8', '#6366f1', '#a78bfa', '#c084fc', '#e879f9', '#f472b6',
  '#fb923c', '#fbbf24', '#34d399', '#22d3ee', '#38bdf8', '#60a5fa',
  '#f87171', '#a3e635', '#2dd4bf'];

function ChartSkeleton() {
  return (
    <div className="space-y-3 p-4">
      <div className="skeleton h-4 w-32" />
      <div className="skeleton h-48 w-full" />
    </div>
  );
}

function ChartError({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-slate-400">
      <AlertCircle size={32} className="mb-3 text-red-400" />
      <p className="text-sm mb-3">{message || 'Failed to load chart data'}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-500/20 text-brand-300 text-sm font-medium hover:bg-brand-500/30 transition-all"
        >
          <RefreshCw size={14} /> Retry
        </button>
      )}
    </div>
  );
}

function ChartWrapper({ title, loading, error, onRetry, children }) {
  return (
    <div className="glass rounded-xl p-5">
      <h3 className="text-white font-semibold text-base mb-4">{title}</h3>
      {loading ? <ChartSkeleton /> : error ? <ChartError message={error} onRetry={onRetry} /> : children}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label, prefix = '' }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-surface-800 border border-brand-500/20 rounded-lg px-3 py-2 shadow-xl text-sm">
      <p className="text-slate-300 font-medium mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-brand-300">
          {p.name}: {prefix}{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}
        </p>
      ))}
    </div>
  );
};

// ── Chart 1: Salary by City (Horizontal Bar) ──
export function SalaryByCityChart({ data, loading, error, onRetry }) {
  const chartData = (data || []).slice(0, 15).map(d => ({
    city: d.city?.split(',')[0] || d.city,
    avg_salary: Math.round(d.avg_salary),
    median_salary: Math.round(d.median_salary),
  }));

  return (
    <ChartWrapper title="💰 Average Salary by City" loading={loading} error={error} onRetry={onRetry}>
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis type="number" tickFormatter={v => `$${(v/1000).toFixed(0)}k`} stroke="#64748b" />
          <YAxis type="category" dataKey="city" width={110} tick={{ fontSize: 12, fill: '#94a3b8' }} />
          <Tooltip content={<CustomTooltip prefix="$" />} />
          <Bar dataKey="avg_salary" name="Avg Salary" radius={[0, 6, 6, 0]}>
            {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}

// ── Chart 2: Top Skills by Premium (Vertical Bar) ──
export function TopSkillsChart({ data, loading, error, onRetry }) {
  const chartData = (data || [])
    .filter(d => d.salary_premium_pct != null && d.count >= 3)
    .slice(0, 15)
    .map(d => ({
      skill: d.skill,
      premium: Math.round(d.salary_premium_pct * 10) / 10,
    }));

  return (
    <ChartWrapper title="🛠 Top Skills by Salary Premium" loading={loading} error={error} onRetry={onRetry}>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={chartData} margin={{ bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="skill" tick={{ fontSize: 11, fill: '#94a3b8' }} angle={-35} textAnchor="end" />
          <YAxis tickFormatter={v => `${v}%`} stroke="#64748b" />
          <Tooltip content={<CustomTooltip prefix="" />} />
          <Bar dataKey="premium" name="Premium %" radius={[6, 6, 0, 0]}>
            {chartData.map((d, i) => (
              <Cell key={i} fill={d.premium > 0 ? '#34d399' : '#f87171'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}

// ── Chart 3: Remote vs Onsite (Grouped Bar) ──
export function RemoteVsOnsiteChart({ data, loading, error, onRetry }) {
  const chartData = data ? [
    { type: 'Remote', salary: Math.round(data.remote_avg || 0), count: data.remote_count || 0 },
    { type: 'Hybrid', salary: Math.round(data.hybrid_avg || 0), count: data.hybrid_count || 0 },
    { type: 'On-site', salary: Math.round(data.onsite_avg || 0), count: data.onsite_count || 0 },
  ] : [];

  return (
    <ChartWrapper title="🏠 Remote vs On-site Salary" loading={loading} error={error} onRetry={onRetry}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="type" tick={{ fill: '#94a3b8' }} />
          <YAxis tickFormatter={v => `$${(v/1000).toFixed(0)}k`} stroke="#64748b" />
          <Tooltip content={<CustomTooltip prefix="$" />} />
          <Bar dataKey="salary" name="Avg Salary" radius={[6, 6, 0, 0]}>
            <Cell fill="#34d399" />
            <Cell fill="#fbbf24" />
            <Cell fill="#818cf8" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {data && (
        <div className="flex justify-center gap-6 mt-3 text-xs text-slate-400">
          {data.remote_premium_pct != null && (
            <span>Remote premium: <span className={data.remote_premium_pct > 0 ? 'text-emerald-400' : 'text-red-400'}>
              {data.remote_premium_pct > 0 ? '+' : ''}{data.remote_premium_pct}%
            </span></span>
          )}
          {data.hybrid_premium_pct != null && (
            <span>Hybrid premium: <span className={data.hybrid_premium_pct > 0 ? 'text-emerald-400' : 'text-red-400'}>
              {data.hybrid_premium_pct > 0 ? '+' : ''}{data.hybrid_premium_pct}%
            </span></span>
          )}
        </div>
      )}
    </ChartWrapper>
  );
}

// ── Chart 4: Seniority Salary Ladder (Line) ──
export function SeniorityLadderChart({ data, loading, error, onRetry }) {
  const chartData = (data || []).map(d => ({
    level: d.seniority_level?.split('(')[0]?.trim() || d.seniority_level,
    avg_salary: Math.round(d.avg_salary),
    median_salary: Math.round(d.median_salary),
    count: d.count,
  }));

  return (
    <ChartWrapper title="📈 Seniority Salary Ladder" loading={loading} error={error} onRetry={onRetry}>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="level" tick={{ fontSize: 11, fill: '#94a3b8' }} />
          <YAxis tickFormatter={v => `$${(v/1000).toFixed(0)}k`} stroke="#64748b" />
          <Tooltip content={<CustomTooltip prefix="$" />} />
          <Legend />
          <Line type="monotone" dataKey="avg_salary" name="Average" stroke="#818cf8" strokeWidth={3} dot={{ r: 5, fill: '#818cf8' }} />
          <Line type="monotone" dataKey="median_salary" name="Median" stroke="#34d399" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 4, fill: '#34d399' }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}

// ── Chart 5: Salary Distribution (Histogram) ──
export function SalaryDistributionChart({ jobs, loading, error, onRetry }) {
  const salaries = (jobs || [])
    .map(j => j.salary_usd_numeric)
    .filter(s => s != null && s > 0);

  const bins = [];
  if (salaries.length > 0) {
    const minS = Math.floor(Math.min(...salaries) / 20000) * 20000;
    const maxS = Math.ceil(Math.max(...salaries) / 20000) * 20000;
    for (let b = minS; b < maxS; b += 20000) {
      const count = salaries.filter(s => s >= b && s < b + 20000).length;
      bins.push({ range: `$${b/1000}k-${(b+20000)/1000}k`, count });
    }
  }

  return (
    <ChartWrapper title="📊 Salary Distribution" loading={loading} error={error} onRetry={onRetry}>
      {bins.length === 0 ? (
        <p className="text-slate-500 text-sm text-center py-8">No salary data available</p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={bins} margin={{ bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="range" tick={{ fontSize: 10, fill: '#94a3b8' }} angle={-30} textAnchor="end" />
            <YAxis stroke="#64748b" />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="count" name="Jobs" radius={[6, 6, 0, 0]} fill="#6366f1" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartWrapper>
  );
}
