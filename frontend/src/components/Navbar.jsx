import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, TrendingUp, Briefcase, Search, BarChart3, DollarSign } from 'lucide-react';

const NAV_LINKS = [
  { path: '/', label: 'Home', icon: TrendingUp },
  { path: '/jobs', label: 'Jobs', icon: Briefcase },
  { path: '/predict', label: 'Predict', icon: DollarSign },
  { path: '/insights', label: 'Insights', icon: BarChart3 },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  return (
    <nav className="sticky top-0 z-50 glass border-b border-brand-500/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 group">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-lg shadow-brand-500/20 group-hover:shadow-brand-500/40 transition-shadow">
              <Search size={18} className="text-white" />
            </div>
            <span className="text-xl font-bold gradient-text">JobLens</span>
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-1">
            {NAV_LINKS.map(({ path, label, icon: Icon }) => {
              const active = location.pathname === path;
              return (
                <Link
                  key={path}
                  to={path}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                    ${active
                      ? 'bg-brand-500/20 text-brand-300 shadow-inner'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                    }`}
                >
                  <Icon size={16} />
                  {label}
                </Link>
              );
            })}
          </div>

          {/* Mobile toggle */}
          <button
            onClick={() => setOpen(!open)}
            className="md:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5"
          >
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>

        {/* Mobile menu */}
        {open && (
          <div className="md:hidden pb-4 border-t border-white/5 mt-2 pt-3">
            {NAV_LINKS.map(({ path, label, icon: Icon }) => {
              const active = location.pathname === path;
              return (
                <Link
                  key={path}
                  to={path}
                  onClick={() => setOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all
                    ${active
                      ? 'bg-brand-500/20 text-brand-300'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                    }`}
                >
                  <Icon size={18} />
                  {label}
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </nav>
  );
}
