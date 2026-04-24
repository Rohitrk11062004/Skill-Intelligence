import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import AppHeader from '../components/AppHeader';
import { getLearningRoadmap } from '../api/learning';
import { getWeekAssessmentHistory } from '../api/assessments';

export default function AssessmentResult() {
  const [searchParams] = useSearchParams();
  const weekNumber = Math.max(1, parseInt(searchParams.get('week') || '1', 10) || 1);
  const selectedAttemptId = searchParams.get('attempt') || '';

  const [planId, setPlanId] = useState('');
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const roadmap = await getLearningRoadmap({ daily_hours: 2, study_days_per_week: 5 });
        const pid = roadmap?.plan_id;
        if (!pid) throw new Error('No plan_id available.');
        if (!mounted) return;
        setPlanId(pid);

        const h = await getWeekAssessmentHistory(pid, weekNumber);
        if (!mounted) return;
        setHistory(h);
      } catch (e) {
        console.error('Failed to load assessment result', e);
        if (mounted) setError('Failed to load assessment result.');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [weekNumber]);

  const attempts = useMemo(() => (Array.isArray(history?.attempts) ? history.attempts : []), [history]);
  const activeAttempt = useMemo(() => {
    if (!attempts.length) return null;
    if (selectedAttemptId) {
      const found = attempts.find((a) => String(a?.attempt_id) === String(selectedAttemptId));
      if (found) return found;
    }
    return attempts[0] || null; // newest first
  }, [attempts, selectedAttemptId]);
  const report = activeAttempt?.report || null;

  return (
    <>
      <AppHeader />
      <main className="pt-28 pb-12 px-8 max-w-[1200px] mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold text-white tracking-tight">Week {weekNumber} Result</h1>
          <p className="text-on-surface-variant mt-2">Your assessment outcome and stored report.</p>
        </header>

        {loading && <div className="text-on-surface-variant text-sm">Loading result…</div>}
        {!loading && error && (
          <div className="text-white bg-error/20 border border-error/40 p-4 rounded-xl">{error}</div>
        )}

        {!loading && !error && !planId && (
          <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6 text-on-surface-variant">
            No learning plan found.
          </div>
        )}

        {!loading && !error && planId && attempts.length === 0 && (
          <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6 text-on-surface-variant">
            No attempts found for week {weekNumber}.
          </div>
        )}

        {!loading && !error && activeAttempt && (
          <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <div className="text-white font-semibold text-xl">
                  {Math.round((activeAttempt.score || 0) * 100)}%
                </div>
                <div className="text-xs text-on-surface-variant mt-1">
                  Attempted:{' '}
                  {activeAttempt.attempted_at ? new Date(activeAttempt.attempted_at).toLocaleString() : '—'}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div
                  className={`text-xs font-bold uppercase tracking-widest ${activeAttempt.passed ? 'text-tertiary' : 'text-error'}`}
                >
                  {activeAttempt.passed ? 'Passed' : 'Needs review'}
                </div>
              </div>
            </div>

            {attempts.length > 1 && (
              <div className="mt-5">
                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">All attempts</div>
                <div className="space-y-2">
                  {attempts.map((a, idx) => {
                    const isActive = String(a?.attempt_id) === String(activeAttempt?.attempt_id);
                    const pct = Math.round((a?.score || 0) * 100);
                    return (
                      <a
                        key={a.attempt_id || idx}
                        href={`/assessment/result?week=${weekNumber}&attempt=${encodeURIComponent(String(a.attempt_id))}`}
                        className={[
                          'block rounded-xl border px-4 py-3 transition-colors',
                          isActive
                            ? 'border-primary/40 bg-primary/10'
                            : 'border-outline-variant/10 bg-surface-container-low/30 hover:bg-surface-container-low/50',
                        ].join(' ')}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm text-white font-semibold truncate">
                              Attempt {attempts.length - idx} • {pct}%
                            </div>
                            <div className="text-xs text-on-surface-variant mt-1">
                              {a.attempted_at ? new Date(a.attempted_at).toLocaleString() : '—'}
                              {a.report ? '' : ' • (no stored report)'}
                            </div>
                          </div>
                          <div className={`text-[10px] font-bold uppercase tracking-widest ${a.passed ? 'text-tertiary' : 'text-error'}`}>
                            {a.passed ? 'Passed' : 'Review'}
                          </div>
                        </div>
                      </a>
                    );
                  })}
                </div>
              </div>
            )}

            {report ? (
              <div className="mt-6">
                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">Report</div>
                <div className="space-y-3">
                  {(report.questions || []).map((q) => (
                    <div key={q.index} className="bg-surface-container-low/30 border border-outline-variant/10 rounded-xl p-4">
                      <div className="text-xs uppercase tracking-widest text-on-surface-variant mb-1">
                        Q{q.index + 1} {q.correct ? '• Correct' : '• Wrong'}
                      </div>
                      <div className="text-white font-medium">{q.question}</div>
                      <div className="mt-3 grid grid-cols-1 gap-2">
                        {(q.options || []).map((opt, i) => {
                          const isCorrect = q.correct_index === i;
                          const isSelected = q.selected_index === i;
                          return (
                            <div
                              key={i}
                              className={[
                                'rounded-lg px-3 py-2 border text-sm',
                                isCorrect ? 'border-tertiary/40 bg-tertiary/10 text-tertiary' : 'border-outline-variant/10 bg-surface-container-low/30 text-on-surface',
                                isSelected && !isCorrect ? 'border-error/40 bg-error/10 text-error' : '',
                              ].join(' ')}
                            >
                              {String.fromCharCode(65 + i)}. {opt}
                            </div>
                          );
                        })}
                      </div>
                      {q.explanation && (
                        <div className="mt-3 text-sm text-on-surface-variant">
                          <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Explanation</div>
                          {q.explanation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mt-6 text-sm text-on-surface-variant">
                Report not available for this attempt yet.
              </div>
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href="/assessments-summary"
                className="px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10 text-xs font-bold text-on-surface-variant hover:text-white hover:bg-surface-container-high transition-colors"
              >
                Go to Assessment Results
              </a>
              <a
                href="/learning"
                className="px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10 text-xs font-bold text-on-surface-variant hover:text-white hover:bg-surface-container-high transition-colors"
              >
                Back to Roadmap
              </a>
            </div>
          </div>
        )}
      </main>
    </>
  );
}

