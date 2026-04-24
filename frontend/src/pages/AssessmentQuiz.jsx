import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getLearningRoadmap } from '../api/learning';
import { getWeekAssessment, submitWeekAssessment } from '../api/assessments';
import AppHeader from '../components/AppHeader';

function formatAxiosError(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d))
    return d.map((x) => (typeof x === 'string' ? x : x?.msg || JSON.stringify(x))).join(' ');
  return '';
}

export default function AssessmentQuizTopNav() {
  const [searchParams, setSearchParams] = useSearchParams();
  const weekNumber = Math.max(1, parseInt(searchParams.get('week') || '1', 10) || 1);
  const navigate = useNavigate();

  const [planId, setPlanId] = useState('');
  const [week, setWeek] = useState(null);
  const [answers, setAnswers] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [proctorEnabled] = useState(true);
  const [proctorArmed, setProctorArmed] = useState(false);
  const [proctorViolations, setProctorViolations] = useState(0);
  const lastViolationAtRef = useRef(0);
  const questionRefs = useRef([]);
  const [isStartOverlayOpen, setIsStartOverlayOpen] = useState(true);
  const [autoSubmitPending, setAutoSubmitPending] = useState(false);
  const startOverlayRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError('');
      setSubmitResult(null);
      try {
        // Use the user's stored plan; these params only affect regeneration. Keep defaults stable.
        const roadmap = await getLearningRoadmap({ daily_hours: 2, study_days_per_week: 5 });
        const pid = roadmap?.plan_id;
        if (!pid) throw new Error('No plan_id returned from roadmap.');
        if (!mounted) return;
        setPlanId(pid);

        const data = await getWeekAssessment(pid, weekNumber);
        if (!mounted) return;
        setWeek(data);
        setAnswers(new Array(Number(data.question_count || 0)).fill(null));
      } catch (e) {
        console.error('Failed to load assessment', e);
        if (mounted) {
          setError(
            formatAxiosError(e) ||
              'Failed to load week assessment. Make sure you set a target role and generated a learning roadmap.'
          );
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [weekNumber]);

  useEffect(() => {
    if (!proctorEnabled) return;

    const bumpViolation = (reason) => {
      // Only start counting after fullscreen has been successfully entered.
      if (!proctorArmed) return;
      const now = Date.now();
      if (now - lastViolationAtRef.current < 800) return;
      lastViolationAtRef.current = now;
      console.warn('proctor_violation', reason);
      setProctorViolations((v) => {
        const next = v + 1;
        if (next >= 3) {
          setAutoSubmitPending(true);
        }
        return next;
      });
    };

    const onVisibility = () => {
      if (document.visibilityState !== 'visible') bumpViolation('tab_hidden');
    };
    const onBlur = () => bumpViolation('window_blur');
    const onContextMenu = (e) => {
      e.preventDefault();
      bumpViolation('context_menu');
    };
    const onCopy = (e) => {
      e.preventDefault();
      bumpViolation('copy');
    };
    const onPaste = (e) => {
      e.preventDefault();
      bumpViolation('paste');
    };
    const onKeyDown = (e) => {
      const key = String(e.key || '').toLowerCase();
      const ctrlOrMeta = e.ctrlKey || e.metaKey;
      const blocked = (ctrlOrMeta && ['c', 'v', 'x', 'p', 's', 'u'].includes(key)) || key === 'printscreen';
      if (blocked) {
        e.preventDefault();
        bumpViolation(`key_${key}`);
      }
    };

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('blur', onBlur);
    document.addEventListener('contextmenu', onContextMenu);
    document.addEventListener('copy', onCopy);
    document.addEventListener('paste', onPaste);
    window.addEventListener('keydown', onKeyDown, { capture: true });

    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('blur', onBlur);
      document.removeEventListener('contextmenu', onContextMenu);
      document.removeEventListener('copy', onCopy);
      document.removeEventListener('paste', onPaste);
      window.removeEventListener('keydown', onKeyDown, { capture: true });
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => undefined);
      }
    };
  }, [proctorEnabled, proctorArmed]);

  const questions = useMemo(() => (Array.isArray(week?.questions) ? week.questions : []), [week]);
  // Insights removed (kept assessment UI focused).
  const answeredCount = answers.filter((a) => a !== null && a !== undefined).length;
  const remainingCount = Math.max(0, answers.length - answeredCount);

  const onSelect = (qIndex, optIndex) => {
    if (submitResult) return;
    setAnswers((prev) => {
      const next = [...prev];
      next[qIndex] = optIndex;
      return next;
    });
  };

  const onSubmit = async () => {
    if (!planId) return;
    if (submitting || submitResult) return;
    setSubmitting(true);
    setError('');
    try {
      const result = await submitWeekAssessment(planId, weekNumber, answers);
      setSubmitResult(result);
      // Redirect to result page; don't show results inline.
      navigate(`/assessment/result?week=${weekNumber}`);
    } catch (e) {
      console.error('Submit failed', e);
      setError(
        formatAxiosError(e) || 'Failed to submit assessment. If you already passed this week, retakes are blocked.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  // If the 3rd violation occurs before planId/questions are ready, submit as soon as possible.
  useEffect(() => {
    if (!proctorEnabled) return;
    if (!autoSubmitPending) return;
    if (!planId) return;
    if (submitting || submitResult) return;
    setAutoSubmitPending(false);
    onSubmit();
  }, [proctorEnabled, autoSubmitPending, planId, submitting, submitResult]);

  const enterFullscreen = async () => {
    const el = document.documentElement;
    if (document.fullscreenElement) return true;
    if (!el?.requestFullscreen) return false;
    try {
      await el.requestFullscreen();
      return true;
    } catch {
      return false;
    }
  };

  useEffect(() => {
    if (!proctorEnabled) return;
    const onFsChange = () => {
      setProctorArmed(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', onFsChange);
    // sync initial
    onFsChange();
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, [proctorEnabled]);

  // Try immediately on page open (will succeed only if browser allows).
  useEffect(() => {
    let mounted = true;
    (async () => {
      if (loading || error) return;
      const ok = await enterFullscreen();
      if (!mounted) return;
      if (ok) setIsStartOverlayOpen(false);
      // If blocked, keep the overlay open and focused so Enter works instantly.
      if (!ok) {
        requestAnimationFrame(() => {
          try {
            startOverlayRef.current?.focus?.();
          } catch {
            // ignore
          }
        });
      }
    })();
    return () => {
      mounted = false;
    };
  }, [loading, error]);

  const goToWeek = (nextWeek) => {
    setSearchParams((prev) => {
      const p = new URLSearchParams(prev);
      p.set('week', String(nextWeek));
      return p;
    });
  };
  return (
    <>
      <AppHeader />
      {/* MAIN */}
      <main className="flex flex-col min-h-screen relative">
      {isStartOverlayOpen && !loading && !error && (
        <div
          className="fixed inset-0 z-[100] bg-[#0c0e14]/85 backdrop-blur-sm flex items-center justify-center px-6"
          onClick={async () => {
            const ok = await enterFullscreen();
            if (ok) {
              setProctorViolations(0);
              lastViolationAtRef.current = 0;
              setAutoSubmitPending(false);
              setIsStartOverlayOpen(false);
            }
          }}
          onKeyDown={async (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              const ok = await enterFullscreen();
              if (ok) {
                setProctorViolations(0);
                lastViolationAtRef.current = 0;
                setAutoSubmitPending(false);
                setIsStartOverlayOpen(false);
              }
            }
          }}
          role="button"
          tabIndex={0}
          ref={startOverlayRef}
        >
          <div className="w-full max-w-xl bg-surface-container border border-outline-variant/15 rounded-2xl p-6">
            <div className="text-white font-semibold text-lg">Tap anywhere to start</div>
            <div className="text-on-surface-variant text-sm mt-2">
              This assessment runs in fullscreen. Proctoring is enabled and violations will auto-submit at 3.
            </div>
            <div className="text-on-surface-variant text-xs mt-4">
              Tip: If fullscreen is blocked by the browser, allow fullscreen and tap again.
            </div>
          </div>
        </div>
      )}
      {/* Sub Header (Breadcrumbs) */}
      <div className="pt-28 px-6 md:px-10 max-w-7xl mx-auto w-full">
      <div className="flex items-center text-[10px] uppercase tracking-widest text-on-surface-variant space-x-2">
      <span className="hover:text-white cursor-pointer transition-colors">Learning Roadmap</span>
      <span className="material-symbols-outlined text-[12px]">chevron_right</span>
      <span className="hover:text-white cursor-pointer transition-colors">Week {weekNumber}</span>
      <span className="material-symbols-outlined text-[12px]">chevron_right</span>
      <span className="hover:text-white cursor-pointer transition-colors">Assessment</span>
      <span className="material-symbols-outlined text-[12px]">chevron_right</span>
      <span className="text-primary font-medium">Assessment</span>
      </div>
      </div>
      {/* Assessment Canvas */}
      <div className="flex-1 px-4 sm:px-6 lg:px-10 max-w-7xl mx-auto w-full flex flex-col xl:flex-row gap-8 h-[calc(100vh-7rem)] overflow-hidden pb-8">
      {/* Core Assessment Area (only this pane scrolls) */}
      <div className="flex-1 space-y-6 overflow-y-auto pr-2">
      {proctorEnabled && (
        <div className="bg-surface-container rounded-xl p-3 border border-outline-variant/15 flex items-center justify-end">
          <div className="text-xs text-on-surface-variant">
            Violations: <span className="text-white font-mono">{proctorViolations}</span>
          </div>
        </div>
      )}
      {loading && (
        <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/15 text-on-surface-variant">
          Loading week assessment…
        </div>
      )}
      {!loading && error && (
        <div className="bg-error/20 rounded-xl p-6 border border-error/40 text-white">
          <div className="mb-4">{error}</div>
          <div className="flex flex-wrap gap-3">
            <a
              href="/learning"
              className="px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10 text-xs font-bold text-on-surface-variant hover:text-white hover:bg-surface-container-high transition-colors"
            >
              Go to Learning Roadmap
            </a>
            <a
              href="/profile"
              className="px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10 text-xs font-bold text-on-surface-variant hover:text-white hover:bg-surface-container-high transition-colors"
            >
              Set target role
            </a>
          </div>
        </div>
      )}
      {!loading && !error && questions.length === 0 && (
        <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/15 text-on-surface-variant">
          No questions available for this week yet.
        </div>
      )}
      {!loading && !error && questions.length > 0 && (
      <>
      {/* Assessment Header Card */}
      <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/15 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
      <div className="flex items-center gap-3 mb-2">
      <h2 className="text-xl md:text-2xl font-medium text-white tracking-tight">Week {weekNumber} Assessment</h2>
      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-surface-bright text-on-surface border border-outline-variant/20">
        {String(week?.status || 'pending')}
      </span>
      </div>
      <div className="flex items-center gap-4">
      <span className="text-sm text-on-surface-variant">{answeredCount} of {questions.length} answered</span>
      <div className="flex gap-1.5">
        <div className="h-1 w-40 bg-surface-container-highest rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${Math.round((answeredCount / questions.length) * 100)}%` }}
          />
        </div>
      </div>
      </div>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        {/* Removed prev/next week navigation for proctored flow */}
      </div>
      </div>
      {/* Question List */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/15 p-6 md:p-8">
        <div className="flex items-center justify-between mb-4">
          <div className="text-xs uppercase tracking-widest text-on-surface-variant">
            {questions.length} questions
          </div>
        </div>

        {submitResult && (
          <div className={`mb-6 p-4 rounded-xl border ${submitResult.passed ? 'bg-tertiary/10 border-tertiary/30' : 'bg-error/10 border-error/30'}`}>
            <div className="flex items-center justify-between">
              <div className="text-white font-semibold">
                Score: {Math.round((submitResult.score || 0) * 100)}% ({submitResult.correct_count}/{submitResult.total})
              </div>
              <div className={`text-xs font-bold uppercase tracking-widest ${submitResult.passed ? 'text-tertiary' : 'text-error'}`}>
                {submitResult.passed ? 'Passed' : 'Needs review'}
              </div>
            </div>
            {!submitResult.passed && (
              <div className="text-xs text-on-surface-variant mt-2">
                Explanations are shown below for incorrect / unanswered questions.
              </div>
            )}
          </div>
        )}

        <div className="space-y-6">
          {questions.map((q, idx) => {
            const selected = answers[idx];
            const resultRow = submitResult?.results?.find((r) => r.index === idx) || null;
            const showExplain = !!resultRow && (!resultRow.correct || resultRow.selected_index === null);

            return (
              <div
                key={idx}
                ref={(el) => {
                  questionRefs.current[idx] = el;
                }}
                className="border border-outline-variant/15 rounded-xl p-5 bg-surface-container-low/30 scroll-mt-28"
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <div className="text-primary font-bold text-xs tracking-widest uppercase mb-1">Q{idx + 1}</div>
                    <div className="text-white font-medium">{q.question}</div>
                  </div>
                  {submitResult && resultRow && (
                    <div className={`text-xs font-bold px-2 py-1 rounded ${resultRow.correct ? 'bg-tertiary/10 text-tertiary border border-tertiary/30' : 'bg-error/10 text-error border border-error/30'}`}>
                      {resultRow.correct ? 'Correct' : 'Wrong'}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {(q.options || []).map((opt, optIdx) => {
                    const isSelected = selected === optIdx;
                    const isCorrectOpt = submitResult && resultRow && resultRow.correct_index === optIdx;
                    const isWrongSelected = submitResult && resultRow && isSelected && !resultRow.correct;

                    return (
                      <button
                        key={optIdx}
                        onClick={() => onSelect(idx, optIdx)}
                        disabled={!!submitResult}
                        className={[
                          'w-full text-left rounded-xl p-4 transition-colors flex items-center gap-4 border',
                          isSelected ? 'bg-primary/10 border-primary/50' : 'bg-surface-container-low hover:bg-surface-bright/50 border-outline-variant/15',
                          isCorrectOpt ? 'ring-1 ring-tertiary/40' : '',
                          isWrongSelected ? 'ring-1 ring-error/40' : '',
                          submitResult ? 'cursor-default' : '',
                        ].join(' ')}
                      >
                        <div className={[
                          'w-6 h-6 rounded-full flex items-center justify-center text-xs',
                          isSelected ? 'bg-primary text-on-primary font-bold' : 'border border-outline-variant/30 text-on-surface-variant',
                        ].join(' ')}>
                          {String.fromCharCode(65 + optIdx)}
                        </div>
                        <div className="text-sm text-on-surface">{opt}</div>
                      </button>
                    );
                  })}
                </div>

                {showExplain && (
                  <div className="mt-4 bg-surface-bright/30 border border-outline-variant/10 rounded-lg p-4 text-sm text-on-surface-variant">
                    <div className="text-xs uppercase tracking-widest text-on-surface-variant mb-1">Explanation</div>
                    <div className="text-on-surface-variant">{resultRow.explanation}</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      </>
      )}
      </div>

      {!loading && !error && questions.length > 0 && (
        <div className="w-full xl:w-72 space-y-6 xl:sticky xl:top-28 self-start">
          <div className="bg-surface-container-low rounded-xl border border-outline-variant/15 p-5">
            <h4 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-4">
              Assessment Map
            </h4>

            <button
              type="button"
              onClick={onSubmit}
              disabled={submitting || submitResult || questions.length === 0}
              className="w-full mb-4 px-4 py-2.5 rounded-xl bg-gradient-to-r from-primary to-primary-container text-white shadow-[0_4px_20px_-5px_rgba(67,136,253,0.4)] disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm font-medium"
            >
              {submitting ? 'Submitting…' : submitResult ? 'Submitted' : 'Submit assessment'}
            </button>

            <div className="grid grid-cols-5 gap-2">
              {Array.from({ length: Math.min(questions.length || 0, 25) }).map((_, idx) => {
                const selected = answers[idx];
                const isAnswered = selected !== null && selected !== undefined;
                return (
                  <button
                    type="button"
                    key={idx}
                    className={[
                      'aspect-square rounded-lg flex items-center justify-center border text-xs hover:border-outline-variant/50 transition-colors',
                      isAnswered
                        ? 'bg-surface-bright border-primary/20 text-white'
                        : 'bg-surface border-outline-variant/20 text-on-surface-variant hover:text-white',
                    ].join(' ')}
                    title={isAnswered ? 'Answered' : 'Not answered'}
                    onClick={() => {
                      const el = questionRefs.current[idx];
                      if (el && typeof el.scrollIntoView === 'function') {
                        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                      }
                    }}
                  >
                    {idx + 1}
                  </button>
                );
              })}
            </div>

            <div className="mt-4 pt-4 border-t border-surface-container-high/50 flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-on-surface-variant flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-tertiary" /> Answered
                </span>
                <span className="text-white font-mono">{answeredCount}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-on-surface-variant flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-surface border border-outline-variant/50" /> Remaining
                </span>
                <span className="text-white font-mono">{remainingCount}</span>
              </div>
            </div>
          </div>

          <a
            href="/learning"
            className="block text-center w-full py-2 rounded-lg bg-surface border border-outline-variant/20 text-xs text-on-surface hover:text-white hover:border-outline-variant/40 transition-colors"
          >
            Back to Roadmap
          </a>
        </div>
      )}
      </div>
      </main>
    </>
  );
}
