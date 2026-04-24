import React, { useEffect, useMemo, useState } from 'react';
import AppHeader from '../components/AppHeader';
import TargetRoleSelector from '../components/TargetRoleSelector';
import { useAuth } from '../contexts/AuthContext';
import { updateMyProfile } from '../api/users';

export default function ProfileInfo() {
  const { user, loading: authLoading } = useAuth();

  const initials = useMemo(() => {
    const name = String(user?.full_name || user?.username || 'U').trim();
    const parts = name.split(/\s+/).filter(Boolean);
    const first = parts[0]?.[0] || 'U';
    const second = parts.length > 1 ? parts[parts.length - 1][0] : '';
    return (first + second).toUpperCase();
  }, [user?.full_name, user?.username]);

  const [profile, setProfile] = useState({
    full_name: '',
    department: '',
    job_title: '',
    seniority_level: '',
  });
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState('');

  useEffect(() => {
    if (authLoading) return;
    setProfile({
      full_name: user?.full_name || '',
      department: user?.department || '',
      job_title: user?.job_title || '',
      seniority_level: user?.seniority_level || '',
    });
  }, [authLoading, user]);

  const onSaveProfile = async () => {
    setProfileMsg('');
    setProfileSaving(true);
    try {
      await updateMyProfile({
        full_name: profile.full_name,
        department: profile.department || null,
        job_title: profile.job_title || null,
        seniority_level: profile.seniority_level || null,
      });
      setProfileMsg('Saved.');
    } catch (e) {
      console.error('Failed to update profile', e);
      setProfileMsg('Failed to save profile.');
    } finally {
      setProfileSaving(false);
    }
  };

  return (
    <>
      <AppHeader />
      <main className="flex-1 h-full overflow-y-auto bg-surface-dim relative scroll-smooth pt-28 pb-12 px-6 lg:px-10">
        <div className="max-w-[1400px] mx-auto">
          <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[120px] pointer-events-none -translate-y-1/2 translate-x-1/3" />

          <header className="mb-10 relative z-10">
            <h1 className="text-[2rem] lg:text-[2.5rem] font-display font-semibold tracking-tight text-white mb-2">
              Profile
            </h1>
            <p className="text-on-surface-variant text-sm tracking-wide">
              Your account details and target role.
            </p>
          </header>

          <div className="relative z-10 max-w-3xl">
            <section className="bg-surface-container rounded-xl p-6 lg:p-8 relative overflow-hidden ring-1 ring-white/5">
              <div className="flex items-start justify-between mb-8">
                <div>
                  <h2 className="text-xl font-headline font-medium text-white mb-1">Personal details</h2>
                  <p className="text-xs text-on-surface-variant tracking-wider uppercase">Identity &amp; role</p>
                </div>
                <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-primary to-primary-container p-0.5 shadow-[0_0_20px_rgba(105,156,255,0.2)]">
                  <div className="w-full h-full rounded-full bg-surface-container-lowest flex items-center justify-center text-white font-display text-2xl font-semibold tracking-tighter">
                    {initials}
                  </div>
                </div>
              </div>

              <div className="mb-6">
                <div className="text-[0.75rem] font-label text-on-surface-variant tracking-wider uppercase mb-2">
                  Target role
                </div>
                <TargetRoleSelector />
              </div>

              <form className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="space-y-1.5">
                    <label className="text-[0.75rem] font-label text-on-surface-variant tracking-wider uppercase">
                      Full name
                    </label>
                    <input
                      className="w-full bg-surface-container-highest border border-white/5 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all placeholder-on-surface-variant/50"
                      type="text"
                      value={profile.full_name}
                      onChange={(e) => setProfile((p) => ({ ...p, full_name: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[0.75rem] font-label text-on-surface-variant tracking-wider uppercase">
                      Email
                    </label>
                    <input
                      className="w-full bg-surface-container-low border border-white/5 rounded-lg px-4 py-2.5 text-on-surface-variant text-sm cursor-not-allowed opacity-80"
                      disabled
                      type="email"
                      value={user?.email || ''}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                  <div className="space-y-1.5 md:col-span-1">
                    <label className="text-[0.75rem] font-label text-on-surface-variant tracking-wider uppercase">
                      Department
                    </label>
                    <div className="relative">
                      <select
                        className="w-full bg-surface-container-highest border border-white/5 rounded-lg px-4 py-2.5 text-white text-sm appearance-none focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50"
                        value={profile.department || ''}
                        onChange={(e) => setProfile((p) => ({ ...p, department: e.target.value }))}
                      >
                        <option value="">—</option>
                        <option value="Engineering">Engineering</option>
                        <option value="Product">Product</option>
                        <option value="Design">Design</option>
                        <option value="HR">HR</option>
                        <option value="Operations">Operations</option>
                      </select>
                      <span className="material-symbols-outlined absolute right-3 top-2.5 text-on-surface-variant pointer-events-none text-xl">
                        expand_more
                      </span>
                    </div>
                  </div>
                  <div className="space-y-1.5 md:col-span-1">
                    <label className="text-[0.75rem] font-label text-on-surface-variant tracking-wider uppercase">
                      Job title
                    </label>
                    <input
                      className="w-full bg-surface-container-highest border border-white/5 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50"
                      type="text"
                      value={profile.job_title}
                      onChange={(e) => setProfile((p) => ({ ...p, job_title: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5 md:col-span-1">
                    <label className="text-[0.75rem] font-label text-on-surface-variant tracking-wider uppercase">
                      Seniority
                    </label>
                    <div className="relative">
                      <select
                        className="w-full bg-surface-container-highest border border-white/5 rounded-lg px-4 py-2.5 text-white text-sm appearance-none focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50"
                        value={profile.seniority_level || ''}
                        onChange={(e) => setProfile((p) => ({ ...p, seniority_level: e.target.value }))}
                      >
                        <option value="">—</option>
                        <option value="Trainee">Trainee</option>
                        <option value="Associate">Associate</option>
                        <option value="Mid-Level">Mid-Level</option>
                        <option value="Senior">Senior</option>
                        <option value="Lead">Lead</option>
                        <option value="Principal">Principal</option>
                      </select>
                      <span className="material-symbols-outlined absolute right-3 top-2.5 text-on-surface-variant pointer-events-none text-xl">
                        expand_more
                      </span>
                    </div>
                  </div>
                </div>
                <div className="pt-4 flex justify-end">
                  <button
                    className="bg-gradient-to-r from-primary to-primary-container text-white px-6 py-2.5 rounded-xl font-medium text-sm hover:shadow-[0_0_15px_rgba(105,156,255,0.3)] transition-all disabled:opacity-60"
                    type="button"
                    disabled={profileSaving}
                    onClick={onSaveProfile}
                  >
                    {profileSaving ? 'Saving…' : 'Save changes'}
                  </button>
                </div>
                {!!profileMsg && (
                  <div className="text-xs text-on-surface-variant text-right">{profileMsg}</div>
                )}
              </form>
            </section>
          </div>
        </div>
      </main>
    </>
  );
}
