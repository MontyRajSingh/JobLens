import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { Mail, Lock, User, LogIn, UserPlus } from 'lucide-react';

export default function Login() {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  const { signInWithEmail, signUpWithEmail, signInWithGoogle, user } = useAuth();
  const navigate = useNavigate();

  // Redirect if already logged in
  if (user) {
    navigate('/', { replace: true });
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isSignUp) {
        if (!name) throw new Error("Name is required");
        await signUpWithEmail(email, password, name);
      } else {
        await signInWithEmail(email, password);
      }
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-80px)] flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md border-4 border-white bg-black p-8 shadow-[8px_8px_0px_0px_rgba(255,255,255,1)] relative z-20">
        <h1 className="text-4xl font-bold tracking-widest text-white mb-8 text-center uppercase">
          {isSignUp ? 'Create Account' : 'Welcome Back'}
        </h1>

        {error && (
          <div className="mb-6 border-2 border-red-500 bg-red-500/10 p-3 text-red-500 font-bold uppercase text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {isSignUp && (
            <div>
              <label className="block text-white font-bold tracking-wider mb-2 uppercase text-sm">Full Name</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <User size={20} className="text-slate-400" />
                </div>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 bg-black border-2 border-white text-white focus:border-brand-500 focus:outline-none transition-colors uppercase font-bold placeholder:text-slate-600"
                  placeholder="ENTER YOUR NAME"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-white font-bold tracking-wider mb-2 uppercase text-sm">Email Address</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Mail size={20} className="text-slate-400" />
              </div>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-4 py-3 bg-black border-2 border-white text-white focus:border-brand-500 focus:outline-none transition-colors uppercase font-bold placeholder:text-slate-600"
                placeholder="ENTER EMAIL"
              />
            </div>
          </div>

          <div>
            <label className="block text-white font-bold tracking-wider mb-2 uppercase text-sm">Password</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock size={20} className="text-slate-400" />
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-4 py-3 bg-black border-2 border-white text-white focus:border-brand-500 focus:outline-none transition-colors uppercase font-bold placeholder:text-slate-600"
                placeholder="ENTER PASSWORD"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-4 border-2 border-brand-500 bg-brand-500 text-black uppercase font-bold tracking-wider hover:bg-black hover:text-brand-500 hover:shadow-[4px_4px_0px_0px_rgba(202,255,38,1)] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? 'Processing...' : isSignUp ? (
              <><UserPlus size={20} /> Sign Up</>
            ) : (
              <><LogIn size={20} /> Sign In</>
            )}
          </button>
        </form>

        <div className="mt-8 pt-8 border-t-2 border-white/20">
          <button
            type="button"
            onClick={async () => {
              try {
                await signInWithGoogle();
              } catch (err) {
                setError(err.message);
              }
            }}
            className="w-full py-4 border-2 border-white text-white uppercase font-bold tracking-wider hover:bg-white hover:text-black transition-colors"
          >
            Continue with Google
          </button>
        </div>

        <div className="mt-6 text-center">
          <button
            onClick={() => setIsSignUp(!isSignUp)}
            className="text-slate-400 hover:text-brand-500 uppercase font-bold tracking-wider text-sm transition-colors"
          >
            {isSignUp ? 'Already have an account? Sign In' : 'Need an account? Sign Up'}
          </button>
        </div>
      </div>
    </div>
  );
}
