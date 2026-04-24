import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Registration() {
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [accountRole, setAccountRole] = useState('employee');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const isValidUsername = (value) => /^[a-zA-Z0-9_]{3,30}$/.test(value);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setError('');
      setIsLoading(true);
      if (!isValidUsername(username)) {
        setError('Username must be 3–30 characters and contain only letters, numbers, or underscores.');
        return;
      }
      if (password.length < 8) {
        setError('Password must be at least 8 characters.');
        return;
      }
      await register({
        full_name: fullName,
        username,
        account_role: accountRole,
        email,
        password
      });
      navigate('/');
    } catch (err) {
      if (err.response?.data?.detail) {
        setError(Array.isArray(err.response.data.detail) ? err.response.data.detail[0].msg : err.response.data.detail);
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* HEADER */}
      
      {/* MAIN */}
      
      {/* Left Side: Neural Background & Branding (55%) */}
      <div className="hidden lg:flex lg:w-[55%] relative overflow-hidden bg-surface-dim items-center justify-center">
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
      {/* Right Side: Registration Form (45%) */}
      <div className="w-full lg:w-[45%] flex items-center justify-center p-8 sm:p-12 lg:p-16 bg-surface-container-lowest relative z-10">
      {/* Form Card */}
      <div className="w-full max-w-md bg-surface-container rounded-xl p-8 ghost-border shadow-[0_32px_64px_-16px_rgba(67,136,253,0.06)]">
      <div className="mb-10 text-center">
      <h2 className="font-headline text-[1.5rem] font-medium text-on-surface mb-2">Create Account</h2>
      <p className="font-body text-[0.875rem] text-on-surface-variant">Join Elevate AI.</p>
      </div>
      
      {error && (
        <div className="mb-4 bg-error-container/20 border border-error/50 p-3 rounded-lg text-error text-center text-sm">
            {error}
        </div>
      )}

      <form className="space-y-6" onSubmit={handleSubmit}>
      {/* Full Name Input */}
      <div className="space-y-2">
      <label className="block font-label text-[0.75rem] tracking-[0.05em] uppercase text-on-surface-variant" htmlFor="fullName">Full Name</label>
      <div className="relative">
      <span className="absolute inset-y-0 left-0 flex items-center pl-4 text-on-surface-variant">
      <span className="material-symbols-outlined text-[1.25rem]">person</span>
      </span>
      <input 
        value={fullName}
        onChange={e => setFullName(e.target.value)}
        className="w-full pl-12 pr-4 py-3 bg-surface-container-highest border border-outline-variant/15 rounded-lg text-on-surface font-body text-[0.875rem] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all placeholder:text-on-surface-variant/50" 
        id="fullName" 
        name="fullName" 
        placeholder="Jane Doe" 
        required
        type="text"
      />
      </div>
      </div>
      {/* Username Input */}
      <div className="space-y-2">
      <label className="block font-label text-[0.75rem] tracking-[0.05em] uppercase text-on-surface-variant" htmlFor="username">Username</label>
      <div className="relative">
      <span className="absolute inset-y-0 left-0 flex items-center pl-4 text-on-surface-variant">
      <span className="material-symbols-outlined text-[1.25rem]">badge</span>
      </span>
      <input 
        value={username}
        onChange={e => setUsername(e.target.value)}
        className="w-full pl-12 pr-4 py-3 bg-surface-container-highest border border-outline-variant/15 rounded-lg text-on-surface font-body text-[0.875rem] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all placeholder:text-on-surface-variant/50" 
        id="username" 
        name="username" 
        placeholder="jane"
        required
        type="text"
      />
      </div>
      <p className="font-label text-[0.75rem] text-on-surface-variant mt-2">
        Use 3–30 characters: letters, numbers, or underscores.
      </p>
      </div>
      {/* Email Input */}
      <div className="space-y-2">
      <label className="block font-label text-[0.75rem] tracking-[0.05em] uppercase text-on-surface-variant" htmlFor="email">Email</label>
      <div className="relative">
      <span className="absolute inset-y-0 left-0 flex items-center pl-4 text-on-surface-variant">
      <span className="material-symbols-outlined text-[1.25rem]">mail</span>
      </span>
      <input 
        value={email}
        onChange={e => setEmail(e.target.value)}
        className="w-full pl-12 pr-4 py-3 bg-surface-container-highest border border-outline-variant/15 rounded-lg text-on-surface font-body text-[0.875rem] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all placeholder:text-on-surface-variant/50" 
        id="email" 
        name="email" 
        placeholder="jane@example.com" 
        required
        type="email"
      />
      </div>
      </div>
      {/* Account Role */}
      <div className="space-y-2">
      <label className="block font-label text-[0.75rem] tracking-[0.05em] uppercase text-on-surface-variant" htmlFor="accountRole">Account Role</label>
      <div className="relative">
      <span className="absolute inset-y-0 left-0 flex items-center pl-4 text-on-surface-variant">
      <span className="material-symbols-outlined text-[1.25rem]">group</span>
      </span>
      <select
        id="accountRole"
        name="accountRole"
        value={accountRole}
        onChange={(e) => setAccountRole(e.target.value)}
        className="w-full pl-12 pr-4 py-3 bg-surface-container-highest border border-outline-variant/15 rounded-lg text-on-surface font-body text-[0.875rem] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all"
      >
        <option value="employee">Employee</option>
        <option value="hr">HR</option>
        <option value="admin">Admin</option>
      </select>
      </div>
      </div>
      {/* Password Input */}
      <div className="space-y-2">
      <label className="block font-label text-[0.75rem] tracking-[0.05em] uppercase text-on-surface-variant" htmlFor="password">Password</label>
      <div className="relative">
      <span className="absolute inset-y-0 left-0 flex items-center pl-4 text-on-surface-variant">
      <span className="material-symbols-outlined text-[1.25rem]">lock</span>
      </span>
      <input 
        value={password}
        onChange={e => setPassword(e.target.value)}
        className="w-full pl-12 pr-12 py-3 bg-surface-container-highest border border-outline-variant/15 rounded-lg text-on-surface font-body text-[0.875rem] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all placeholder:text-on-surface-variant/50" 
        id="password" 
        name="password" 
        placeholder="••••••••" 
        required
        type={showPassword ? 'text' : 'password'}
      />
      <button
        className="absolute inset-y-0 right-0 flex items-center pr-4 text-on-surface-variant hover:text-on-surface transition-colors"
        type="button"
        onClick={() => setShowPassword((v) => !v)}
        aria-label={showPassword ? 'Hide password' : 'Show password'}
      >
      <span className="material-symbols-outlined text-[1.25rem]">{showPassword ? 'visibility' : 'visibility_off'}</span>
      </button>
      </div>
      {/* Strength Indicator (Static for visual) */}
      <div className="flex gap-1 mt-2">
      <div className="h-1 flex-1 bg-tertiary rounded-full"></div>
      <div className="h-1 flex-1 bg-tertiary rounded-full"></div>
      <div className="h-1 flex-1 bg-surface-variant rounded-full"></div>
      <div className="h-1 flex-1 bg-surface-variant rounded-full"></div>
      </div>
      <p className="font-label text-[0.75rem] text-on-surface-variant mt-1 text-right">Medium Strength</p>
      </div>
      {/* Terms Checkbox */}
      <div className="flex items-start gap-3 pt-2">
      <div className="flex items-center h-5">
      <input className="w-4 h-4 rounded border-outline-variant/30 bg-surface-container-highest text-primary focus:ring-primary/50 focus:ring-offset-surface-container" id="terms" type="checkbox" required/>
      </div>
      <label className="font-body text-[0.875rem] text-on-surface-variant leading-tight" htmlFor="terms">
                              I agree to the <a className="text-primary hover:text-primary-fixed transition-colors" href="/profile">Terms &amp; Conditions</a> and <a className="text-primary hover:text-primary-fixed transition-colors" href="/profile">Privacy Policy</a>
      </label>
      </div>
      {/* Submit Button */}
      <button 
        disabled={isLoading}
        className="w-full py-4 bg-gradient-to-r from-primary to-primary-container text-on-primary font-headline text-[1rem] font-semibold rounded-xl hover:shadow-[0_0_20px_rgba(67,136,253,0.4)] transition-all duration-300 transform hover:-translate-y-0.5 disabled:opacity-50" 
        type="submit">
          {isLoading ? 'Creating Account...' : 'Create Account'}
      </button>
      </form>
      {/* Divider */}
      <div className="relative my-8">
      <div className="absolute inset-0 flex items-center">
      <div className="w-full border-t border-outline-variant/20"></div>
      </div>
      <div className="relative flex justify-center text-sm">
      <span className="px-4 bg-surface-container font-label text-[0.75rem] tracking-[0.05em] uppercase text-on-surface-variant">Or register with</span>
      </div>
      </div>
      {/* OAuth Buttons */}
      <div className="grid grid-cols-2 gap-4">
      <button className="flex items-center justify-center gap-2 py-3 px-4 border border-outline-variant/20 rounded-lg text-on-surface hover:bg-surface-variant/50 transition-colors font-body text-[0.875rem]" type="button">
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"></path>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"></path>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"></path>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"></path>
      </svg>
                          Google
                      </button>
      <button className="flex items-center justify-center gap-2 py-3 px-4 border border-outline-variant/20 rounded-lg text-on-surface hover:bg-surface-variant/50 transition-colors font-body text-[0.875rem]" type="button">
      <svg aria-hidden="true" className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
      <path clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" fillRule="evenodd"></path>
      </svg>
                          GitHub
                      </button>
      </div>
      {/* Sign In Link */}
      <div className="mt-8 text-center">
      <p className="font-body text-[0.875rem] text-on-surface-variant">
                          Already have an account? 
                          <Link className="text-primary hover:text-primary-fixed transition-colors font-medium ml-1" to="/login">Sign In</Link>
      </p>
      </div>
      </div>
      </div>
      
    </div>
  );
}
