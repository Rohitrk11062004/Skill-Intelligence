import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setError('');
      setIsLoading(true);
      await login(identifier, password);
      navigate('/');
    } catch (err) {
      setError('Invalid username/email or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* HEADER */}
      
      {/* MAIN */}
      
      {/* Left Side: Neural Background & Branding (55%) */}
      <div className="hidden lg:flex lg:w-[55%] h-screen sticky top-0 relative overflow-hidden bg-surface-dim items-center justify-center">
      {/* Abstract Neural Constellation Background Simulation */}
      <div className="absolute inset-0 z-0">
      {/* Simulated nodes and glows using gradients */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/20 rounded-full blur-[100px] mix-blend-screen"></div>
      <div className="absolute bottom-1/3 right-1/4 w-80 h-80 bg-tertiary/20 rounded-full blur-[80px] mix-blend-screen"></div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-[radial-gradient(ellipse_at_center,rgba(67,136,253,0.1)_0%,rgba(12,14,20,1)_70%)]"></div>
      <img alt="Abstract neural network" className="w-full h-full object-cover opacity-10 mix-blend-luminosity" data-alt="abstract dark background with glowing interconnected teal and blue nodes resembling a neural network in deep space" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCq4Axa5AXOXNYb5kka2ACSLI_iY_cQpxBsxkadngo5yg2RskRvgoZc493xp61ONMmz3fvEkq0Ng0_CmHm9h2tT1fr1BgkaMSc1UnzYvZOtQuVPtdKmNPgcIpXR_qDFZBownUBAyOljR03au7GcTYTfXenbFNcDUBYWuO_oyAdkZbWT7W2Ak60E7bBpuaC-Z46Kp1jvcbLYc_V4hZDWZ28HeWYEMgzXsYdHkJFnsfVv6WpZGK7xIp-YabYul87ge0Pxxa0ffy9xKr_Z"/>
      </div>
      {/* Branding Content */}
      <div className="relative z-10 text-center max-w-2xl px-8">
      <h1 className="font-display text-[3.5rem] leading-tight font-extrabold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-primary to-tertiary mb-6">
                      Elevate AI
                  </h1>
      <p className="font-headline text-[1.5rem] font-medium text-on-surface-variant tracking-tight">
                      AI learning and development by ParadigmIT
                  </p>
      </div>
      </div>
      {/* Right Side: Login Form */}
      <div className="w-full lg:w-[45%] h-screen overflow-y-auto flex items-start justify-center p-6 sm:p-12 bg-surface-dim relative">
      {/* Ambient glow for form */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3/4 h-3/4 bg-primary-container/5 blur-[120px] rounded-full pointer-events-none"></div>
      <div className="w-full max-w-md relative z-10">
      {/* Mobile Brand Header (Visible only on small screens) */}
      <div className="flex lg:hidden items-center justify-center gap-2 mb-10">
      <span className="material-symbols-outlined text-3xl text-primary" style={{fontVariationSettings: '"FILL" 1'}}>lens_blur</span>
      <div className="flex flex-col items-center text-center gap-1">
      <h1 className="text-2xl font-bold tracking-tight text-on-surface">Elevate AI</h1>
      <p className="text-xs text-on-surface-variant px-4">AI learning and development by ParadigmIT</p>
      </div>
      </div>
      {/* Login Card */}
      <div className="bg-surface-container rounded-xl p-8 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.5)] border border-outline-variant/15">
      <div className="text-center mb-8">
      <h2 className="text-headline-sm font-medium text-on-surface mb-2">Welcome Back</h2>
      <p className="text-body-md text-on-surface-variant">Sign in to access your neural dashboard</p>
      </div>
      
      {error && (
        <div className="mb-4 bg-error-container/20 border border-error/50 p-3 rounded-lg text-error text-center text-sm">
            {error}
        </div>
      )}

      <form className="space-y-5" onSubmit={handleSubmit}>
      {/* Email Field */}
      <div className="space-y-1.5">
      <label className="block text-label-md font-medium text-on-surface-variant tracking-[0.05em] uppercase" htmlFor="identifier">Email or Username</label>
      <div className="relative">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
      <span className="material-symbols-outlined text-on-surface-variant text-sm">mail</span>
      </div>
      <input 
        value={identifier}
        onChange={e => setIdentifier(e.target.value)}
        className="w-full bg-surface-container-highest border border-outline-variant/30 rounded-lg py-2.5 pl-10 pr-4 text-on-surface placeholder:text-on-surface-variant/50 focus:border-primary/50 focus:ring-1 focus:ring-primary/50 focus:outline-none transition-all duration-200" 
        id="identifier" 
        name="identifier" 
        placeholder="name@company.com or name" 
        required 
        type="text"
      />
      </div>
      </div>
      {/* Password Field */}
      <div className="space-y-1.5">
      <label className="block text-label-md font-medium text-on-surface-variant tracking-[0.05em] uppercase" htmlFor="password">Password</label>
      <div className="relative">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
      <span className="material-symbols-outlined text-on-surface-variant text-sm">lock</span>
      </div>
      <input 
        value={password}
        onChange={e => setPassword(e.target.value)}
        className="w-full bg-surface-container-highest border border-outline-variant/30 rounded-lg py-2.5 pl-10 pr-10 text-on-surface placeholder:text-on-surface-variant/50 focus:border-primary/50 focus:ring-1 focus:ring-primary/50 focus:outline-none transition-all duration-200" 
        id="password" 
        name="password" 
        placeholder="••••••••" 
        required 
        type={showPassword ? 'text' : 'password'}
      />
      <button
        className="absolute inset-y-0 right-0 pr-3 flex items-center text-on-surface-variant hover:text-on-surface transition-colors"
        type="button"
        onClick={() => setShowPassword((v) => !v)}
        aria-label={showPassword ? 'Hide password' : 'Show password'}
      >
      <span className="material-symbols-outlined text-sm">{showPassword ? 'visibility' : 'visibility_off'}</span>
      </button>
      </div>
      </div>
      {/* Remember Me & Forgot Password */}
      <div className="flex items-center justify-between pt-2">
      <div className="flex items-center">
      <input className="h-4 w-4 rounded border-outline-variant/50 bg-surface-container-highest text-primary focus:ring-primary focus:ring-offset-surface-container" id="remember-me" name="remember-me" type="checkbox"/>
      <label className="ml-2 block text-body-md text-on-surface-variant" htmlFor="remember-me">
                                      Remember me
                                  </label>
      </div>
      <div className="text-body-md">
      <a className="font-medium text-primary hover:text-primary-fixed transition-colors" href="/login">
                                      Forgot password?
                                  </a>
      </div>
      </div>
      {/* Submit Button */}
      <div className="pt-4">
      <button 
        disabled={isLoading}
        className="w-full flex justify-center py-3 px-4 rounded-xl text-on-primary-container font-medium text-body-md bg-gradient-to-r from-primary to-primary-container hover:from-primary-fixed hover:to-primary hover:shadow-[0_0_20px_rgba(105,156,255,0.3)] transition-all duration-300 transform active:scale-[0.98] disabled:opacity-50" 
        type="submit">
          {isLoading ? 'Signing In...' : 'Sign In'}
      </button>
      </div>
      </form>
      {/* Divider */}
      <div className="mt-8 relative">
      <div aria-hidden="true" className="absolute inset-0 flex items-center">
      <div className="w-full border-t border-outline-variant/20"></div>
      </div>
      <div className="relative flex justify-center">
      <span className="px-3 bg-surface-container text-label-md text-on-surface-variant tracking-[0.05em] uppercase">
                                  or continue with
                              </span>
      </div>
      </div>
      {/* Social Login */}
      <div className="mt-6 grid grid-cols-2 gap-4">
      <button className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-outline/10 text-on-surface text-body-md font-medium hover:bg-surface-container-highest transition-colors group">
      <img alt="Google logo" className="h-5 w-5 opacity-80 group-hover:opacity-100 transition-opacity" src="https://lh3.googleusercontent.com/aida-public/AB6AXuDXhkV1hefK2ZHO-MYsPZfGWr7eIwDvSSI-HkmNzutkrOEQkYlICTdxjpxClCo8M95RcDlrnmSNw1XH-WJpgO7OcreHPURqRVPtIV9b9jgoBFv-9J6lUFfqD-6hcnqRm0d2lRA78dWruBYXEZF4Z7ER12-vX1fKce54RroAe2L3YzeIAi_kyKvH-iLpXGKj2tEff93ExS39M_mBgYUAEowu4A19qeligK6hnXyMvnI2pUhBB--9BuTvUamz9FoX3x3zXUoIXeoHB_M8"/>
                              Google
                          </button>
      <button className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-outline/10 text-on-surface text-body-md font-medium hover:bg-surface-container-highest transition-colors group">
      <img alt="GitHub logo" className="h-5 w-5 filter invert opacity-80 group-hover:opacity-100 transition-opacity" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCfphVzv4Gnw1T1gTPT6dTwGA_DpWqewSPK1z-eThqcm2cDWmF7QCZspQSOUMKNX0lmygrs8tRqp8r3lTHQDmmgkUBclINr_1Hw2F-uEzNtgS4Nux_rQfKr1DBn-mfnJjenTXDKwlhFrN_pHiNILb4zhjwndNApEM_LNuP5TewslE1YDU2U4HrIYR3kfj7eM3W-FsAA6VruKktRMSPqhQr_cRzF4n6OVfMnND4fmJnSYWq2TrEzF4barhWAZAwvzSiv3fYQ0RILc4S-"/>
                              GitHub
                          </button>
      </div>
      </div>
      {/* Registration Link */}
      <div className="mt-8 text-center text-body-md text-on-surface-variant">
                      Don't have an account? 
                      <Link className="font-medium text-primary hover:text-primary-fixed transition-colors ml-1" to="/register">
                          Register
                      </Link>
      </div>
      </div>
      </div>
      
    </div>
  );
}
