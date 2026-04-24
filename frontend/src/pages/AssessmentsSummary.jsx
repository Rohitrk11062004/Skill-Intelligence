import React, { useEffect, useState } from 'react';
import { getMyAssessmentsSummary, getWeekAssessmentHistory } from '../api/assessments';
import AppHeader from '../components/AppHeader';
import { getLearningRoadmap } from '../api/learning';

export default function AssessmentsSummary() {
  const [summary, setSummary] = useState(null);
  const [planId, setPlanId] = useState('');
  const [weekCount, setWeekCount] = useState(0);
  const [selectedWeek, setSelectedWeek] = useState(1);
  const [weekHistory, setWeekHistory] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await getMyAssessmentsSummary();
        if (mounted) setSummary(data);
      } catch (e) {
        // keep page usable even if API not ready yet
        console.error('Failed to load assessment summary', e);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const roadmap = await getLearningRoadmap({ hours_per_week: 10 });
        const pid = roadmap?.plan_id || '';
        const weeks = Array.isArray(roadmap?.weeks) ? roadmap.weeks : [];
        if (!mounted) return;
        setPlanId(pid);
        const count = weeks.length || Number(roadmap?.total_weeks || 0) || 0;
        setWeekCount(count);
        if (count > 0) setSelectedWeek((prev) => Math.min(Math.max(1, prev), count));
      } catch (e) {
        if (mounted) {
          setPlanId('');
          setWeekCount(0);
          setWeekHistory(null);
        }
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    if (!planId || !selectedWeek) return () => {};
    (async () => {
      setHistoryLoading(true);
      try {
        const data = await getWeekAssessmentHistory(planId, selectedWeek);
        if (mounted) setWeekHistory(data);
      } catch (e) {
        console.error('Failed to load week assessment history', e);
        if (mounted) setWeekHistory(null);
      } finally {
        if (mounted) setHistoryLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [planId, selectedWeek]);

  const metrics = summary || {
    assessments_completed: 0,
    average_score: 0,
    skills_assessed: 0,
    proficiency_level: null,
    week_assessments_completed: 0,
    week_assessments_avg_score: 0,
    item_attempts_total: 0,
    item_attempts_accuracy: 0,
  };

  const latestAttempt = (weekHistory?.attempts || [])[0] || null;
  const latestReport = latestAttempt?.report || null;

  return (
    <>
      <AppHeader />
      {/* MAIN */}
      <main className="pt-28 pb-12 px-8 max-w-[1600px] mx-auto">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-6">
      <div>
      <h1 className="text-[2.5rem] font-bold tracking-tight text-white mb-2">Assessment Summary</h1>
      <p className="text-on-surface-variant font-medium text-lg max-w-2xl">Track skill proficiency assessments and identify development gaps through deep cognitive mapping.</p>
      </div>
      <a
        href="/assessment"
        className="bg-gradient-to-r from-primary to-primary-container text-on-primary font-semibold px-8 py-4 rounded-xl shadow-[0_0_20px_rgba(105,156,254,0.3)] hover:scale-[1.02] active:scale-[0.98] transition-all"
      >
        Take New Assessment
      </a>
      </header>
      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-12">
        <div className="bg-surface-container p-6 rounded-xl border-l-4 border-primary shadow-lg">
          <p className="text-label-md text-on-surface-variant tracking-wider uppercase mb-1">Week Assessments Passed</p>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold text-white">{metrics.week_assessments_completed}</span>
            <span className="text-xs text-on-surface-variant">Weeks passed</span>
          </div>
        </div>
        <div className="bg-surface-container p-6 rounded-xl border-l-4 border-tertiary shadow-lg">
          <p className="text-label-md text-on-surface-variant tracking-wider uppercase mb-1">Week Avg Score</p>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold text-tertiary">
              {Math.round((metrics.week_assessments_avg_score || 0) * 100)}%
            </span>
            <span className="text-xs text-tertiary/80 font-medium">Across all attempts</span>
          </div>
        </div>
        <div className="bg-surface-container p-6 rounded-xl border-l-4 border-secondary shadow-lg">
          <p className="text-label-md text-on-surface-variant tracking-wider uppercase mb-1">Item Attempts</p>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold text-white">{metrics.item_attempts_total}</span>
            <span className="text-xs text-on-surface-variant">Total item quiz attempts</span>
          </div>
        </div>
        <div className="bg-surface-container p-6 rounded-xl border-l-4 border-primary-fixed shadow-lg">
          <p className="text-label-md text-on-surface-variant tracking-wider uppercase mb-1">Item Accuracy</p>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold text-white">
              {Math.round((metrics.item_attempts_accuracy || 0) * 100)}%
            </span>
            <span className="text-xs text-on-surface-variant">Correctness rate</span>
          </div>
        </div>
      </div>
      <div className="flex flex-col lg:flex-row gap-8">
      {/* Left Column (60%) */}
      <div className="lg:w-[60%] space-y-8">
      {/* Week Assessment History */}
      <section className="bg-surface-container p-8 rounded-xl border border-outline-variant/10">
        <div className="flex justify-between items-center mb-6 gap-4">
          <h2 className="text-xl font-semibold text-white">Week Assessment History</h2>
          <div className="flex items-center gap-3">
            <span className="text-xs text-on-surface-variant">Week</span>
            <select
              className="bg-surface-container-highest border border-outline-variant/20 rounded-lg px-3 py-2 text-xs text-white"
              value={selectedWeek}
              onChange={(e) => setSelectedWeek(Number(e.target.value))}
              disabled={!planId || weekCount <= 0}
            >
              {Array.from({ length: Math.max(1, weekCount) }, (_, i) => i + 1).map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </div>
        </div>

        {!planId && (
          <div className="text-sm text-on-surface-variant">
            No learning plan found yet. Upload a resume and set a target role to generate weekly assessments.
          </div>
        )}
        {planId && historyLoading && <div className="text-sm text-on-surface-variant">Loading history…</div>}
        {planId && !historyLoading && (
          <div className="space-y-3">
            {(weekHistory?.attempts || []).length === 0 && (
              <div className="text-sm text-on-surface-variant">
                No attempts for week {selectedWeek} yet. Take the assessment from the Learning Roadmap.
              </div>
            )}
            {(weekHistory?.attempts || []).map((a) => (
              <div
                key={a.attempt_id}
                className={`p-4 rounded-xl border ${
                  a.passed ? 'bg-tertiary/10 border-tertiary/20' : 'bg-surface-container-low border-outline-variant/10'
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="text-white font-semibold">
                    {Math.round((a.score || 0) * 100)}%
                    <span
                      className={`text-xs font-bold uppercase tracking-widest ml-2 ${
                        a.passed ? 'text-tertiary' : 'text-outline'
                      }`}
                    >
                      {a.passed ? 'Passed' : 'Attempt'}
                    </span>
                  </div>
                  <div className="text-xs text-on-surface-variant">
                    {a.attempted_at ? new Date(a.attempted_at).toLocaleString() : ''}
                  </div>
                </div>
              </div>
            ))}
            <div className="pt-2">
              <a href="/learning" className="text-primary text-sm font-medium hover:underline">
                Go to Learning Roadmap →
              </a>
            </div>
          </div>
        )}
      </section>
      <section className="bg-surface-container p-8 rounded-xl border border-outline-variant/10">
        <h2 className="text-xl font-semibold text-white mb-2">Overall performance</h2>
        <p className="text-sm text-on-surface-variant mb-6">
          These metrics are computed from your week assessments and item quiz attempts.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-surface-container-low/30 border border-outline-variant/10 rounded-xl p-4">
            <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Average score</div>
            <div className="text-2xl font-bold text-white">
              {Math.round((metrics.average_score || 0) * 100)}%
            </div>
          </div>
          <div className="bg-surface-container-low/30 border border-outline-variant/10 rounded-xl p-4">
            <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Skills assessed</div>
            <div className="text-2xl font-bold text-white">{metrics.skills_assessed}</div>
          </div>
          <div className="bg-surface-container-low/30 border border-outline-variant/10 rounded-xl p-4">
            <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Proficiency level</div>
            <div className="text-2xl font-bold text-white">{metrics.proficiency_level || '—'}</div>
          </div>
        </div>
      </section>
      </div>
      {/* Right Column (40%) */}
      <div className="lg:w-[40%] space-y-8">
        <section className="bg-surface-container p-8 rounded-xl border border-outline-variant/10">
          <div className="flex items-center justify-between gap-3 mb-4">
            <h2 className="text-xl font-semibold text-white">Week report</h2>
            <div className="text-xs text-on-surface-variant">Week {selectedWeek}</div>
          </div>

          {!planId && (
            <div className="text-sm text-on-surface-variant">
              Generate a learning path to unlock week assessment reports.
            </div>
          )}

          {planId && historyLoading && <div className="text-sm text-on-surface-variant">Loading report…</div>}

          {planId && !historyLoading && !latestReport && (
            <div className="text-sm text-on-surface-variant">
              No stored report yet for week {selectedWeek}. Complete the week assessment with ≥ 70% to generate one.
            </div>
          )}

          {planId && !historyLoading && latestReport && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="text-white font-semibold">
                  {Math.round((latestReport.score || 0) * 100)}% ({latestReport.correct_count}/{latestReport.total})
                </div>
                <div
                  className={`text-xs font-bold uppercase tracking-widest ${
                    latestReport.passed ? 'text-tertiary' : 'text-error'
                  }`}
                >
                  {latestReport.passed ? 'Passed' : 'Needs review'}
                </div>
              </div>

              {(latestReport.weak_areas || []).length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">Weak areas</div>
                  <div className="space-y-2">
                    {(latestReport.weak_areas || []).slice(0, 5).map((w) => (
                      <div
                        key={w.tag}
                        className="flex items-center justify-between text-xs bg-surface-container-low/30 border border-outline-variant/10 p-2 rounded"
                      >
                        <span className="text-on-surface">{w.tag}</span>
                        <span className="text-on-surface-variant font-mono">{w.missed}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
      </div>
      </main>
    </>
  );
}
