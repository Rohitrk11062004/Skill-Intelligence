import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { deleteLearningPlan, getLearningRoadmap } from '../api/learning';
import AppHeader from '../components/AppHeader';
import TargetRoleSelector from '../components/TargetRoleSelector';

export default function LearningPathRoadmap() {
  const [roadmap, setRoadmap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [deletingPath, setDeletingPath] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState({}); // { [topicKey: string]: true }

  const loadRoadmap = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getLearningRoadmap({
        daily_hours: 2,
        study_days_per_week: 5,
      });
      setRoadmap(data);
    } catch (e) {
      console.error('Failed to load learning roadmap', e);
      setError('Failed to load roadmap. Ensure you uploaded & processed a resume and set a target role.');
      setRoadmap(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRoadmap();
  }, [loadRoadmap]);

  const deleteLearningPath = async () => {
    if (!roadmap) return;
    if (!window.confirm('Delete this learning path? You can generate a new one later.')) return;
    setDeletingPath(true);
    setError('');
    try {
      if (roadmap.plan_id) {
        await deleteLearningPlan(roadmap.plan_id);
      }
      setRoadmap(null);
    } catch (e) {
      console.error('Delete learning path failed', e);
      const detail = e?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => (typeof d === 'string' ? d : d?.msg || JSON.stringify(d))).join(' ')
            : 'Could not delete the learning path. Try again.';
      setError(msg);
    } finally {
      setDeletingPath(false);
    }
  };

  const headerRole = roadmap?.target_role || 'Learning Roadmap';
  const readinessPct = Math.round(((roadmap?.readiness_score ?? 0) * 100) || 0);
  const planId = roadmap?.plan_id ? String(roadmap.plan_id) : 'no-plan';
  const firstWeek = useMemo(() => {
    const weeks = Array.isArray(roadmap?.weeks) ? roadmap.weeks : [];
    return weeks.length ? weeks[0] : null;
  }, [roadmap]);
  const weeks = useMemo(() => (Array.isArray(roadmap?.weeks) ? roadmap.weeks : []), [roadmap]);
  const deferred = useMemo(
    () => (Array.isArray(roadmap?.deferred_items) ? roadmap.deferred_items : []),
    [roadmap]
  );

  const progressStorageKey = useMemo(() => `learningProgress|${planId}`, [planId]);

  useEffect(() => {
    if (!planId) return;
    try {
      const raw = window.localStorage.getItem(progressStorageKey);
      if (!raw) {
        setProgress({});
        return;
      }
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') setProgress(parsed);
      else setProgress({});
    } catch {
      setProgress({});
    }
  }, [progressStorageKey, planId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(progressStorageKey, JSON.stringify(progress || {}));
    } catch {
      // ignore storage quota / privacy mode
    }
  }, [progressStorageKey, progress]);

  const buildTopicKey = useCallback(
    ({ weekNumber, dayIndex, skillId, focusTitle, skillName }) => {
      const w = `w${String(weekNumber ?? '')}`;
      const d = dayIndex != null ? `d${String(dayIndex)}` : 'd-';
      const s = (skillId != null && String(skillId).trim()) ? `s${String(skillId).trim()}` : `sn:${String(skillName || '').trim()}`;
      const f = focusTitle ? `f:${String(focusTitle).trim()}` : '';
      return `${progressStorageKey}|${w}|${d}|${s}|${f}`;
    },
    [progressStorageKey]
  );

  const toggleTopicDone = useCallback((topicKey, nextVal) => {
    setProgress((prev) => {
      const v = typeof nextVal === 'boolean' ? nextVal : !prev?.[topicKey];
      if (v) return { ...(prev || {}), [topicKey]: true };
      const { [topicKey]: _removed, ...rest } = prev || {};
      return rest;
    });
  }, []);

  const topicsForWeek = useCallback(
    (w) => {
      const hasDays =
        Array.isArray(w?.days) && w.days.some((d) => (d.estimated_hours || 0) > 0 || (d.capacity_hours || 0) > 0);

      if (hasDays) {
        const items = [];
        (w.days || [])
          .filter((d) => (d.estimated_hours || 0) > 0 || (d.capacity_hours || 0) > 0)
          .forEach((d) => {
            (d.skills || []).forEach((b) => {
              items.push(
                buildTopicKey({
                  weekNumber: w.week_number,
                  dayIndex: d.day_index,
                  skillId: b?.skill_id,
                  focusTitle: b?.focus_title,
                  skillName: b?.skill_name,
                })
              );
            });
          });
        return items;
      }

      return (w.skills || []).map((s) =>
        buildTopicKey({
          weekNumber: w.week_number,
          dayIndex: null,
          skillId: s?.skill_id,
          focusTitle: null,
          skillName: s?.skill_name,
        })
      );
    },
    [buildTopicKey]
  );

  const allTopicKeys = useMemo(() => weeks.flatMap((w) => topicsForWeek(w)), [weeks, topicsForWeek]);
  const doneCount = useMemo(() => allTopicKeys.filter((k) => !!progress?.[k]).length, [allTopicKeys, progress]);
  const totalCount = allTopicKeys.length;
  const overallPct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;

  return (
    <>
      <AppHeader />

      {/* MAIN */}
      <main className="pt-28 pb-12 px-8 max-w-[1600px] mx-auto">
        {/* HEADER (kept inside main so spacing collapses when sections don't render) */}
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div className="space-y-1">
            <h1 className="text-display-lg text-4xl font-semibold tracking-tight">My Learning Path</h1>
            <p className="text-on-surface-variant text-lg max-w-2xl leading-relaxed">
              Personalized skill development roadmap based on your role and proficiency gaps.
            </p>
          </div>
          <div className="flex flex-col items-end gap-3">
            <TargetRoleSelector
              className="w-full"
              onChange={() => {
                loadRoadmap();
              }}
            />
            <div className="bg-primary/10 border border-primary/20 text-primary px-3 py-1 rounded-full text-xs font-bold tracking-widest uppercase">
              Readiness: {readinessPct}%
            </div>
          </div>
        </header>

        {loading && (
          <div className="text-on-surface-variant text-sm">Loading roadmap…</div>
        )}
        {!loading && error && (
          <div className="text-white bg-error/20 border border-error/40 p-4 rounded-xl mb-8">
            <div className="mb-3">{error}</div>
            <div className="flex flex-wrap gap-3">
              <a
                href="/profile"
                className="px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10 text-xs font-bold text-on-surface-variant hover:text-white hover:bg-surface-container-high transition-colors"
              >
                Set Target Role
              </a>
              <a
                href="/resumes"
                className="px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10 text-xs font-bold text-on-surface-variant hover:text-white hover:bg-surface-container-high transition-colors"
              >
                Upload Resume
              </a>
            </div>
          </div>
        )}
        {!loading && !error && !roadmap && (
          <div className="bg-surface-container-low/40 border border-outline-variant/15 rounded-xl p-8 text-center mb-8">
            <p className="text-white font-medium">No active learning path</p>
            <p className="text-sm text-on-surface-variant mt-2 max-w-md mx-auto leading-relaxed">
              Generate one from Skills analysis after gap analysis, or reload once your resume and target role are set.
            </p>
            <a
              href="/skill-analysis"
              className="inline-block mt-5 px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-primary-container text-on-primary text-xs font-bold hover:brightness-110 transition-all"
            >
              Go to Skills analysis
            </a>
          </div>
        )}
        {!loading && !error && roadmap && firstWeek && (
          <div className="mb-8 bg-surface-container-low/40 border border-outline-variant/15 rounded-xl p-5">
            <div className="text-xs uppercase tracking-widest text-on-surface-variant mb-2">
              Week {firstWeek.week_number}: {firstWeek.week_title || 'Focus areas'}
            </div>
            <div className="flex flex-wrap gap-2">
              {(firstWeek.skills || []).slice(0, 8).map((s, idx) => (
                <span key={idx} className="px-3 py-1 rounded-full text-xs bg-primary/10 border border-primary/20 text-primary">
                  {s.skill_name || s}
                </span>
              ))}
            </div>
          </div>
        )}
        {!loading && !error && roadmap && (
          <>
            <section className="mb-10 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              <div className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Target role</div>
                <div className="text-white font-semibold">{headerRole}</div>
              </div>
              <div className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Pace</div>
                <div className="text-white font-semibold">
                  {roadmap.daily_hours != null && roadmap.daily_hours !== undefined
                    ? `${roadmap.daily_hours}h/day × ${roadmap.study_days_per_week ?? 7} study days`
                    : '—'}
                </div>
              </div>
              <div className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Scheduled</div>
                <div className="text-white font-semibold">{roadmap.total_weeks} weeks</div>
              </div>
              <div className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Total hours</div>
                <div className="text-white font-semibold">{Math.round(roadmap.total_hours_estimate || 0)} hrs</div>
              </div>
            </section>

            <section className="mb-8 bg-surface-container rounded-xl border border-outline-variant/10 p-5">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Learning progress</div>
                  <div className="text-white font-semibold">
                    {overallPct}% <span className="text-on-surface-variant font-normal">({doneCount}/{totalCount} topics)</span>
                  </div>
                </div>
                <button
                  type="button"
                  className="px-3 py-1.5 rounded-lg border border-outline-variant/20 text-xs font-semibold text-on-surface-variant hover:text-white hover:bg-surface-container-high transition-all"
                  onClick={() => {
                    if (!window.confirm('Reset learning progress for this plan?')) return;
                    setProgress({});
                  }}
                >
                  Reset progress
                </button>
              </div>
              <div className="mt-4 h-2 rounded-full bg-surface-container-highest/30 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-primary to-primary-container"
                  style={{ width: `${overallPct}%` }}
                />
              </div>
            </section>

            <section className="space-y-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <h2 className="text-xl font-semibold text-white">Weekly plan</h2>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={deleteLearningPath}
                    disabled={loading || deletingPath}
                    className="px-3 py-1.5 rounded-lg border border-error/40 text-error text-xs font-semibold hover:bg-error/10 transition-all disabled:opacity-60"
                  >
                    {deletingPath ? 'Deleting…' : 'Delete path'}
                  </button>
                  <div className="text-xs text-on-surface-variant">
                    {weeks.length} week{weeks.length === 1 ? '' : 's'}
                  </div>
                </div>
              </div>

              {weeks.length === 0 && (
                <div className="bg-surface-container-low/40 border border-outline-variant/15 rounded-xl p-5 text-on-surface-variant text-sm">
                  No weeks scheduled yet. Upload & process a resume, then select a target role above.
                </div>
              )}

              {weeks.map((w) => (
                (() => {
                  const weekTopicKeys = topicsForWeek(w);
                  const weekDone = weekTopicKeys.length > 0 && weekTopicKeys.every((k) => !!progress?.[k]);
                  const weekDoneCount = weekTopicKeys.filter((k) => !!progress?.[k]).length;
                  const weekPct = weekTopicKeys.length > 0 ? Math.round((weekDoneCount / weekTopicKeys.length) * 100) : 0;
                  return (
                <details key={w.week_number} className="bg-surface-container rounded-xl border border-outline-variant/10 overflow-hidden">
                  <summary className="cursor-pointer select-none px-5 py-4 flex items-center justify-between gap-4">
                    <div>
                      <div className="text-xs uppercase tracking-widest text-on-surface-variant">
                        Week {w.week_number}
                      </div>
                      <div className="text-white font-semibold">{w.week_title || 'Week focus'}</div>
                      <div className="text-[10px] text-on-surface-variant mt-1">{weekPct}% complete</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <label
                        className="flex items-center gap-2 text-xs font-semibold text-on-surface-variant"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          className="accent-primary"
                          checked={weekDone}
                          onChange={(e) => {
                            const next = e.target.checked;
                            weekTopicKeys.forEach((k) => toggleTopicDone(k, next));
                          }}
                        />
                        Mark week done
                      </label>
                      <a
                        className="text-xs font-bold text-primary hover:underline"
                        href={`/assessment?week=${w.week_number}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        Take week assessment
                      </a>
                      <div className="text-xs text-on-surface-variant">
                        {Math.round(w.total_hours || 0)} hrs • {(w.skills || []).length} skill{(w.skills || []).length === 1 ? '' : 's'}
                      </div>
                    </div>
                  </summary>

                  <div className="px-5 pb-5 space-y-4">
                    {Array.isArray(w.days) && w.days.some((d) => (d.estimated_hours || 0) > 0) && (
                      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
                        <div className="text-xs font-bold text-primary uppercase tracking-widest mb-3">Day-by-day</div>
                        <div className="space-y-2">
                          {w.days
                            .filter((d) => (d.estimated_hours || 0) > 0 || (d.capacity_hours || 0) > 0)
                            .map((d, dayIdx) => (
                              <div
                                key={`${w.week_number}-${d.day_index}`}
                                className="bg-surface-container-low/40 border border-outline-variant/10 rounded-xl p-4"
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-sm font-semibold text-white">
                                    Day {dayIdx + 1}
                                    {d.day_name ? <span className="text-on-surface-variant font-normal"> · {d.day_name}</span> : null}
                                  </span>
                                  <span className="text-[10px] text-on-surface-variant">
                                    {Math.round(d.estimated_hours || 0)}h
                                    {d.capacity_hours ? ` / ${Math.round(d.capacity_hours)}h` : ''}
                                  </span>
                                </div>

                                <div className="mt-3 space-y-3">
                                  {(d.skills || []).map((b, bi) => {
                                    const topicKey = buildTopicKey({
                                      weekNumber: w.week_number,
                                      dayIndex: d.day_index,
                                      skillId: b?.skill_id,
                                      focusTitle: b?.focus_title,
                                      skillName: b?.skill_name,
                                    });
                                    const skillId = String(b?.skill_id || '').trim();
                                    const fromWeek = (w.skills || []).find((ws) => String(ws?.skill_id || '').trim() === skillId);
                                    const resources = Array.isArray(fromWeek?.resources) ? fromWeek.resources : [];
                                    const focus = b?.focus_title ? ` — ${b.focus_title}` : '';
                                    return (
                                      <div key={bi} className="rounded-lg bg-surface-container-highest/10 border border-outline-variant/10 p-3">
                                        <div className="flex items-start justify-between gap-3">
                                          <div className="min-w-0">
                                            <label className="flex items-start gap-2">
                                              <input
                                                type="checkbox"
                                                className="mt-1 accent-primary"
                                                checked={!!progress?.[topicKey]}
                                                onChange={(e) => toggleTopicDone(topicKey, e.target.checked)}
                                              />
                                              <div className="min-w-0">
                                                <div className="text-sm text-white font-medium">
                                                  {b.skill_name || 'Topic'}
                                                  <span className="text-on-surface-variant font-normal">{focus}</span>
                                                </div>
                                              </div>
                                            </label>
                                          </div>
                                          <div className="text-[10px] text-primary whitespace-nowrap">
                                            {Math.round(b.estimated_hours || 0)}h
                                          </div>
                                        </div>

                                        {resources.length > 0 && (
                                          <div className="mt-2">
                                            <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Resources</div>
                                            <div className="space-y-1">
                                              {resources.slice(0, 2).map((r, rIdx) => (
                                                <a
                                                  key={rIdx}
                                                  href={r.url}
                                                  target="_blank"
                                                  rel="noreferrer"
                                                  className="block text-xs text-primary hover:underline truncate"
                                                  title={r.title}
                                                >
                                                  {r.title}
                                                </a>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}
                    {/* Avoid showing the same plan twice: if day-by-day exists, it already covers topics + resources. */}
                    {!(Array.isArray(w.days) && w.days.some((d) => (d.estimated_hours || 0) > 0 || (d.capacity_hours || 0) > 0)) &&
                      (w.skills || []).map((s, idx) => (
                        <div
                          key={`${w.week_number}-${s.skill_id || s.skill_name}-${idx}`}
                          className="bg-surface-container-low/30 border border-outline-variant/10 rounded-xl p-4"
                        >
                          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-2">
                            <div>
                              <label className="flex items-start gap-2">
                                <input
                                  type="checkbox"
                                  className="mt-1 accent-primary"
                                  checked={
                                    !!progress?.[
                                      buildTopicKey({
                                        weekNumber: w.week_number,
                                        dayIndex: null,
                                        skillId: s?.skill_id,
                                        focusTitle: null,
                                        skillName: s?.skill_name,
                                      })
                                    ]
                                  }
                                  onChange={(e) =>
                                    toggleTopicDone(
                                      buildTopicKey({
                                        weekNumber: w.week_number,
                                        dayIndex: null,
                                        skillId: s?.skill_id,
                                        focusTitle: null,
                                        skillName: s?.skill_name,
                                      }),
                                      e.target.checked
                                    )
                                  }
                                />
                                <div className="min-w-0">
                                  <div className="text-white font-semibold">{s.skill_name}</div>
                                </div>
                              </label>
                              <div className="text-xs text-on-surface-variant mt-1">
                                {s.gap_type} • priority {Math.round(s.priority_score || 0)} • {Math.round(s.total_hours || 0)} hrs
                              </div>
                              {s.skill_rationale && (
                                <div className="text-sm text-on-surface-variant mt-2">{s.skill_rationale}</div>
                              )}
                            </div>
                            <a className="text-xs font-bold text-primary hover:underline" href={`/assessment?week=${w.week_number}`}>
                              Take week assessment
                            </a>
                          </div>

                          {(s.subtopics || []).length > 0 && (
                            <div className="mt-3">
                              <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">Subtopics</div>
                              <div className="space-y-2">
                                {(s.subtopics || []).map((st, stIdx) => (
                                  <div
                                    key={stIdx}
                                    className="bg-surface-container-highest/20 border border-outline-variant/10 rounded-lg px-3 py-2"
                                  >
                                    <div className="flex items-center justify-between gap-3">
                                      <div className="text-sm text-white">{st.title}</div>
                                      <div className="text-[10px] text-on-surface-variant">
                                        {Math.round(st.estimated_hours || 0)} hrs
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {(s.resources || []).length > 0 && (
                            <div className="mt-3">
                              <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">Resources</div>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                {(s.resources || []).slice(0, 6).map((r, rIdx) => (
                                  <a
                                    key={rIdx}
                                    href={r.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="block bg-surface-container-highest/20 border border-outline-variant/10 rounded-lg px-3 py-2 hover:border-primary/30 transition-colors"
                                  >
                                    <div className="text-sm text-white">{r.title}</div>
                                    <div className="text-[10px] text-on-surface-variant mt-1">
                                      {r.provider} • {r.resource_type} • {Math.round(r.estimated_hours || 0)} hrs
                                    </div>
                                  </a>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                  </div>
                </details>
                  );
                })()
              ))}
            </section>

            {deferred.length > 0 && (
              <section className="mt-10 bg-surface-container rounded-xl border border-outline-variant/10 p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-white font-semibold">Deferred items</h3>
                  <div className="text-xs text-on-surface-variant">{deferred.length}</div>
                </div>
                <div className="space-y-2">
                  {deferred.slice(0, 12).map((d, idx) => (
                    <div key={idx} className="flex items-center justify-between gap-3 bg-surface-container-low/30 border border-outline-variant/10 rounded-lg px-3 py-2">
                      <div className="text-sm text-white">{d.skill_name}</div>
                      <div className="text-[10px] text-on-surface-variant">
                        {d.gap_type} • {Math.round(d.estimated_hours || 0)} hrs
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </>
  );
}
