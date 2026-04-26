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
    <nav className="sticky top-0 z-50 bg-black border-b-4 border-white shadow-brutal-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-20">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 bg-brand-500 border-2 border-white flex items-center justify-center shadow-brutal transition-transform group-hover:-translate-y-1 group-hover:-translate-x-1">
              <Search size={22} className="text-black stroke-[3]" />
            </div>
            <span className="text-2xl font-bold display-text tracking-widest text-white">JOBLENS</span>
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-4">
            {NAV_LINKS.map(({ path, label, icon: Icon }) => {
              const active = location.pathname === path;
              return (
                <Link
                  key={path}
                  to={path}
                  className={`flex items-center gap-2 px-4 py-2 border-2 transition-all duration-200 uppercase font-bold tracking-wider text-sm
                    ${active
                      ? 'bg-brand-500 text-black border-brand-500 shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]'
                      : 'text-white border-transparent hover:border-white hover:bg-surface-800'
                    }`}
                >
                  <Icon size={18} strokeWidth={active ? 3 : 2} />
                  {label}
                </Link>
              );
            })}
          </div>

          {/* Mobile toggle */}
          <button
            onClick={() => setOpen(!open)}
            className="md:hidden p-2 border-2 border-white bg-black text-white hover:bg-brand-500 hover:text-black transition-colors shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]"
          >
            {open ? <X size={24} strokeWidth={3} /> : <Menu size={24} strokeWidth={3} />}
          </button>
        </div>

        {/* Mobile menu */}
        {open && (
          <div className="md:hidden pb-6 pt-4 border-t-4 border-white mt-4 flex flex-col gap-3">
            {NAV_LINKS.map(({ path, label, icon: Icon }) => {
              const active = location.pathname === path;
              return (
                <Link
                  key={path}
                  to={path}
                  onClick={() => setOpen(false)}
                  className={`flex items-center gap-4 px-5 py-4 border-2 transition-all uppercase font-bold tracking-widest
                    ${active
                      ? 'bg-brand-500 text-black border-brand-500 shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]'
                      : 'text-white border-white bg-black hover:bg-surface-800 shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]'
                    }`}
                >
                  <Icon size={20} strokeWidth={active ? 3 : 2} />
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
