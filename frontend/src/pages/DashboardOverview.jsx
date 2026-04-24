import React, { useEffect, useState } from 'react';
import { getDashboardStats } from '../api/dashboard';
import AppHeader from '../components/AppHeader';

export default function DashboardOverview() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function fetchStats() {
      try {
        const data = await getDashboardStats();
        setStats(data);
      } catch (err) {
        console.error('Failed to fetch dashboard stats', err);
        setError('Failed to load dashboard data. Please try again.');
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0c0e14] pt-28 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#0c0e14] pt-28 flex items-center justify-center">
        <div className="text-white bg-error/20 border border-error/50 p-6 rounded-xl">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  // Fallback default structure if stats is empty to prevent crashes
  const data = stats || {
    detected_skills_count: 0,
    skill_gaps_count: 0,
    active_paths_count: 0,
    avg_mastery: 0,
    priority_gaps: [],
    recent_skills: [],
    overall_progress: { done: 0, pending: 0, total: 0 }
  };

  const progressPercentage = data.overall_progress.total > 0 
    ? Math.round((data.overall_progress.done / data.overall_progress.total) * 100) 
    : 0;

  return (
    <>
      <AppHeader />

      {/* MAIN */}
      <main className="pt-28 pb-12 px-10 max-w-[1600px] mx-auto min-h-screen text-white">
        
        {/* Empty State if No Data */}
        {data.detected_skills_count === 0 && data.skill_gaps_count === 0 && (
          <div className="mb-10 p-8 glass-panel border border-primary/20 rounded-xl flex flex-col items-center justify-center text-center">
            <span className="material-symbols-outlined text-6xl text-primary mb-4">upload_file</span>
            <h2 className="text-2xl font-bold mb-2">Welcome to your Dashboard</h2>
            <p className="text-on-surface-variant mb-6">Looks like you haven't uploaded a resume yet. Let's get started to analyze your skills and generate a learning roadmap.</p>
            <a href="/resumes" className="px-6 py-2 bg-primary text-on-primary font-bold rounded-lg hover:bg-primary/90 transition-colors">
              Upload Resume
            </a>
          </div>
        )}

        {/* Hero Metrics */}
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
          <div className="glass-panel p-6 rounded-xl border border-outline-variant/10 relative overflow-hidden group">
            <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-110 transition-transform duration-500">
              <span className="material-symbols-outlined text-9xl">hub</span>
            </div>
            <p className="text-[0.75rem] font-medium tracking-[0.05em] text-on-surface-variant uppercase mb-2">Detected Skills</p>
            <div className="flex items-baseline gap-2">
              <h2 className="text-4xl font-bold text-white">{data.detected_skills_count}</h2>
            </div>
            <div className="mt-4 h-1 w-full bg-surface-container-highest rounded-full overflow-hidden">
              <div className="h-full w-full bg-primary animate-pulse"></div>
            </div>
          </div>

          <div className="glass-panel p-6 rounded-xl border border-outline-variant/10 relative overflow-hidden group">
            <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-110 transition-transform duration-500">
              <span className="material-symbols-outlined text-9xl">troubleshoot</span>
            </div>
            <p className="text-[0.75rem] font-medium tracking-[0.05em] text-on-surface-variant uppercase mb-2">Skill Gaps</p>
            <div className="flex items-baseline gap-2">
              <h2 className="text-4xl font-bold text-white">{data.skill_gaps_count}</h2>
            </div>
            <div className="mt-4 flex gap-1">
              <div className="h-1 flex-1 bg-error rounded-full opacity-70"></div>
              <div className="h-1 flex-1 bg-error rounded-full opacity-50"></div>
            </div>
          </div>

          <div className="glass-panel p-6 rounded-xl border border-outline-variant/10 relative overflow-hidden group">
            <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-110 transition-transform duration-500">
              <span className="material-symbols-outlined text-9xl">route</span>
            </div>
            <p className="text-[0.75rem] font-medium tracking-[0.05em] text-on-surface-variant uppercase mb-2">Active Paths</p>
            <div className="flex items-baseline gap-2">
              <h2 className="text-4xl font-bold text-white">{data.active_paths_count}</h2>
            </div>
            <div className="mt-4 flex items-center gap-2">
              <div className="h-px flex-grow bg-outline-variant/30"></div>
            </div>
          </div>

          <div className="glass-panel p-6 rounded-xl border border-outline-variant/10 relative overflow-hidden group">
            <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-110 transition-transform duration-500">
              <span className="material-symbols-outlined text-9xl">school</span>
            </div>
            <p className="text-[0.75rem] font-medium tracking-[0.05em] text-on-surface-variant uppercase mb-2">Avg Mastery</p>
            <div className="flex items-baseline gap-2">
              <h2 className="text-4xl font-bold text-white">{(data.avg_mastery * 10).toFixed(1)}<span className="text-xl">/10</span></h2>
            </div>
            <div className="mt-4 flex -space-x-2">
              <div className="h-1 flex-1 bg-tertiary rounded-full"></div>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-10 gap-8">
          {/* LEFT COLUMN */}
          <div className="lg:col-span-6 space-y-8">
            {/* Priority Gaps */}
            <section className="glass-panel p-8 rounded-xl border border-outline-variant/10">
              <h3 className="text-xl font-medium text-white mb-6">Priority Gaps to Close</h3>
              {data.priority_gaps?.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="text-on-surface-variant text-[0.75rem] uppercase tracking-wider">
                        <th className="pb-4 font-medium">Skill Name</th>
                        <th className="pb-4 font-medium">Gap Type</th>
                        <th className="pb-4 font-medium text-center">Score</th>
                        <th className="pb-4 font-medium text-right">Est. Hours</th>
                      </tr>
                    </thead>
                    <tbody className="text-sm divide-y divide-outline-variant/10">
                      {data.priority_gaps.map((gap, i) => (
                        <tr key={i} className="group hover:bg-surface-bright/20 transition-colors">
                          <td className="py-4 font-medium text-white">{gap.skill_name}</td>
                          <td className="py-4 text-on-surface-variant capitalize">{gap.gap_type.replace('_', ' ')}</td>
                          <td className="py-4 text-center">
                            <span className="text-error font-mono">{gap.priority_score.toFixed(2)}</span>
                          </td>
                          <td className="py-4 text-right">
                            <span className="inline-flex items-center px-2 py-1 rounded bg-surface-container text-on-surface-variant text-xs font-medium">{gap.time_to_learn_hours}h</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-on-surface-variant text-sm">No critical skill gaps identified right now.</p>
              )}
            </section>
          </div>

          {/* RIGHT COLUMN */}
          <div className="lg:col-span-4 space-y-8">
             {/* Progress Status */}
             <section className="glass-panel p-8 rounded-xl border border-outline-variant/10">
              <h3 className="text-lg font-medium text-white mb-6">Overall Progress</h3>
              <div className="flex flex-col items-center justify-center py-6">
                <div className="relative w-32 h-32 flex items-center justify-center rounded-full border-8 border-surface-container-high">
                   <div 
                      className="absolute inset-0 rounded-full border-8 border-primary transition-all duration-1000"
                      style={{ 
                         clipPath: `polygon(50% 50%, 50% 0, ${progressPercentage > 50 ? '100% 0' : progressPercentage * 3.6 + '% 0'}, 100% 50%, 100% 100%, 0% 100%, 0% 0%, 50% 0%)`,
                         transformOrigin: 'center'
                      }}
                   ></div>
                   <div className="text-center">
                      <span className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-tertiary">{progressPercentage}%</span>
                   </div>
                </div>
                <div className="flex gap-8 mt-8 text-center">
                   <div>
                     <p className="text-2xl font-bold text-white">{data.overall_progress.done}</p>
                     <p className="text-xs text-on-surface-variant uppercase">Completed</p>
                   </div>
                   <div>
                     <p className="text-2xl font-bold text-white">{data.overall_progress.pending}</p>
                     <p className="text-xs text-on-surface-variant uppercase">Pending</p>
                   </div>
                </div>
              </div>
            </section>

            {/* Top Skills Cloud */}
            <section className="glass-panel p-8 rounded-xl border border-outline-variant/10">
              <h3 className="text-lg font-medium text-white mb-6">Recently Detected Skills</h3>
              <div className="flex flex-wrap gap-2">
                {data.recent_skills?.length > 0 ? data.recent_skills.map((skill, i) => (
                  <span key={i} className="px-4 py-1.5 bg-primary/10 text-primary rounded-lg text-sm font-medium border border-primary/20">
                    {skill}
                  </span>
                )) : (
                  <span className="text-sm text-on-surface-variant">No skills recently extracted.</span>
                )}
              </div>
            </section>
          </div>
        </div>
      </main>
    </>
  );
}
