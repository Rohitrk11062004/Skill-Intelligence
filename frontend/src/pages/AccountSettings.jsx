import React, { useEffect, useState } from 'react';
import AppHeader from '../components/AppHeader';
import {
  changeMyPassword,
  getMyPreferences,
  getMyResumes,
  getMySkillTrend,
  updateMyPreferences,
} from '../api/users';

export default function AccountSettings() {
  const [prefs, setPrefs] = useState(null);
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [prefsMsg, setPrefsMsg] = useState('');

  const [pw, setPw] = useState({ current: '', next: '' });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState('');

  const [resumes, setResumes] = useState([]);
  const [trend, setTrend] = useState(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [p, r, t] = await Promise.all([getMyPreferences(), getMyResumes(), getMySkillTrend()]);
        if (!mounted) return;
        setPrefs(p);
        setResumes(Array.isArray(r) ? r : []);
        setTrend(t || null);
      } catch {
        if (!mounted) return;
        setPrefs((prev) => prev || { email_notifications: false, in_app_notifications: false, weekly_summary: false });
        setResumes((prev) => prev || []);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const onTogglePref = async (key) => {
    if (!prefs) return;
    setPrefsMsg('');
    setPrefsSaving(true);
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    try {
      const saved = await updateMyPreferences({ [key]: next[key] });
      setPrefs(saved);
      setPrefsMsg('Updated.');
    } catch (e) {
      console.error('Failed to update preferences', e);
      setPrefsMsg('Failed to update preferences.');
      setPrefs(prefs);
    } finally {
      setPrefsSaving(false);
    }
  };

  const onChangePassword = async () => {
    setPwMsg('');
    if (!pw.current || !pw.next || String(pw.next).length < 8) {
      setPwMsg('New password must be at least 8 characters.');
      return;
    }
    setPwSaving(true);
    try {
      await changeMyPassword({ currentPassword: pw.current, newPassword: pw.next });
      setPw({ current: '', next: '' });
      setPwMsg('Password updated.');
    } catch (e) {
      console.error('Failed to change password', e);
      setPwMsg('Failed to change password.');
    } finally {
      setPwSaving(false);
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
              Settings
            </h1>
            <p className="text-on-surface-variant text-sm tracking-wide">
              Notifications, security, and resume history.
            </p>
          </header>

          <div className="relative z-10 max-w-3xl space-y-6">
            <section className="bg-surface-container rounded-xl p-6 relative overflow-hidden ring-1 ring-white/5">
              <h2 className="text-sm font-headline font-medium text-white mb-5">Security &amp; preferences</h2>
              <div className="space-y-4 mb-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-on-surface">Weekly digest</p>
                    <p className="text-xs text-on-surface-variant">Receive summary of skill progress</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      className="sr-only peer"
                      type="checkbox"
                      checked={!!prefs?.weekly_summary}
                      onChange={() => onTogglePref('weekly_summary')}
                      disabled={prefsSaving || !prefs}
                    />
                    <div className="w-9 h-5 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-on-surface-variant peer-checked:after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary border border-white/10" />
                  </label>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-on-surface">New opportunity alerts</p>
                    <p className="text-xs text-on-surface-variant">When readiness &gt; 80%</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      className="sr-only peer"
                      type="checkbox"
                      checked={!!prefs?.in_app_notifications}
                      onChange={() => onTogglePref('in_app_notifications')}
                      disabled={prefsSaving || !prefs}
                    />
                    <div className="w-9 h-5 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-on-surface-variant peer-checked:after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary border border-white/10" />
                  </label>
                </div>
              </div>
              <div className="text-[10px] text-on-surface-variant uppercase tracking-wider">
                Email notifications: {prefs?.email_notifications ? 'On' : 'Off'} • {prefsSaving ? 'Saving…' : prefsMsg}
              </div>

              <div className="pt-5 border-t border-white/5 mt-5">
                <h3 className="text-sm font-medium text-white mb-3">Change password</h3>
                <div className="space-y-3">
                  <input
                    className="w-full bg-surface-container-highest border border-white/5 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50"
                    type="password"
                    placeholder="Current password"
                    value={pw.current}
                    onChange={(e) => setPw((p) => ({ ...p, current: e.target.value }))}
                  />
                  <input
                    className="w-full bg-surface-container-highest border border-white/5 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50"
                    type="password"
                    placeholder="New password (min 8 chars)"
                    value={pw.next}
                    onChange={(e) => setPw((p) => ({ ...p, next: e.target.value }))}
                  />
                  <button
                    type="button"
                    className="w-full py-2.5 rounded-lg border border-outline-variant/30 text-on-surface font-medium text-sm hover:bg-surface-bright/30 transition-all disabled:opacity-60"
                    onClick={onChangePassword}
                    disabled={pwSaving}
                  >
                    {pwSaving ? 'Updating…' : 'Update password'}
                  </button>
                  {!!pwMsg && <div className="text-xs text-on-surface-variant">{pwMsg}</div>}
                </div>
              </div>
              <div className="pt-5 border-t border-white/5 mt-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-error-dim">Deactivate account</p>
                    <p className="text-[10px] text-on-surface-variant uppercase tracking-wider">Danger zone</p>
                  </div>
                  <button
                    type="button"
                    className="px-3 py-1.5 rounded border border-error-dim/30 text-error-dim text-xs font-medium hover:bg-error-container/20 transition-colors"
                  >
                    Revoke access
                  </button>
                </div>
              </div>
            </section>

            <section className="bg-surface-container rounded-xl p-6 relative overflow-hidden ring-1 ring-white/5">
              <h2 className="text-sm font-headline font-medium text-white mb-5">Resume history</h2>
              {resumes.length === 0 ? (
                <div className="text-sm text-on-surface-variant">
                  No resumes uploaded yet. <a className="text-primary hover:underline" href="/skill-analysis">Upload one</a>.
                </div>
              ) : (
                <div className="space-y-2">
                  {resumes.slice(0, 6).map((r) => (
                    <div
                      key={r.id}
                      className="flex items-center justify-between gap-4 bg-surface-container-low/30 border border-outline-variant/10 rounded-lg px-3 py-2"
                    >
                      <div className="min-w-0">
                        <div className="text-sm text-white truncate">{r.file_name}</div>
                        <div className="text-[10px] text-on-surface-variant uppercase tracking-widest mt-1">
                          {r.status} • {r.skills_count} skills
                        </div>
                      </div>
                      <div className="text-xs text-on-surface-variant">
                        {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {!!trend?.trend?.length && (
                <div className="mt-5 text-xs text-on-surface-variant">
                  Skill trend points: {trend.trend.length} (last: {trend.trend[trend.trend.length - 1]?.total_score})
                </div>
              )}
            </section>
          </div>
        </div>
      </main>
    </>
  );
}
