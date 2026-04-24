import React, { useMemo, useState } from 'react';

const safeStr = (v) => String(v ?? '').trim();

export default function LearningRoadmapGraph({ roadmap }) {
  const weeks = useMemo(() => (Array.isArray(roadmap?.weeks) ? roadmap.weeks : []), [roadmap]);
  const [selected, setSelected] = useState(null);

  return (
    <div className="relative bg-surface-container rounded-xl border border-outline-variant/10 overflow-hidden">
      <div className="px-5 py-4 border-b border-outline-variant/10 flex items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-on-surface-variant">Pipeline view</div>
          <div className="text-white font-semibold">Weeks → Days → Topics</div>
        </div>
        <div className="text-xs text-on-surface-variant">
          Scroll horizontally to browse weeks
        </div>
      </div>

      <div className="relative">
        <div className="overflow-x-auto overflow-y-hidden">
          <div className="min-w-full w-max p-5">
            <div className="flex items-start gap-6">
              {weeks.map((w, wi) => {
                const weekNum = w.week_number ?? wi + 1;
                const days = Array.isArray(w.days) ? w.days : [];
                const dayRows = days.filter((d) => (d?.estimated_hours || 0) > 0 || (d?.capacity_hours || 0) > 0);

                const weekSkills = Array.isArray(w.skills) ? w.skills : [];
                const byId = new Map(weekSkills.map((s) => [safeStr(s?.skill_id), s]));

                return (
                  <div key={weekNum} className="relative">
                    {/* connector to next week */}
                    {wi < weeks.length - 1 && (
                      <div className="absolute top-10 left-full w-6 h-px bg-outline-variant/30" />
                    )}

                    <div className="w-[360px] bg-surface-container-low/30 border border-outline-variant/15 rounded-2xl overflow-hidden">
                      <div className="px-4 py-3 bg-gradient-to-r from-primary/15 to-transparent border-b border-outline-variant/10">
                        <div className="text-[10px] uppercase tracking-widest text-on-surface-variant">
                          Week {weekNum}
                        </div>
                        <div className="text-white font-semibold">{w.week_title || 'Focus areas'}</div>
                        <div className="mt-2 flex items-center gap-2 text-[10px] text-on-surface-variant">
                          <span>{Math.round(w.total_hours || 0)}h</span>
                          <span>•</span>
                          <span>{(w.skills || []).length} topics</span>
                        </div>
                      </div>

                      <div className="p-4 space-y-3">
                        {dayRows.length === 0 && (
                          <div className="text-sm text-on-surface-variant">
                            No scheduled days for this week.
                          </div>
                        )}

                        {dayRows.map((d, di) => {
                          const estH = Math.round(d.estimated_hours || 0);
                          const capH = d.capacity_hours != null ? Math.round(d.capacity_hours || 0) : null;
                          const dayTitle = `Day ${di + 1}${d.day_name ? ` · ${d.day_name}` : ''}`;

                          return (
                            <div key={`${weekNum}-${d.day_index ?? di}`} className="bg-surface-container border border-outline-variant/10 rounded-xl overflow-hidden">
                              <div className="px-3 py-2 flex items-center justify-between gap-2 bg-surface-container-highest/10 border-b border-outline-variant/10">
                                <div className="text-sm font-semibold text-white">{dayTitle}</div>
                                <div className="text-[10px] text-on-surface-variant whitespace-nowrap">
                                  {capH != null ? `${estH}h / ${capH}h` : `${estH}h`}
                                </div>
                              </div>

                              <div className="p-3 space-y-2">
                                {(Array.isArray(d.skills) ? d.skills : []).map((b, bi) => {
                                  const skillId = safeStr(b?.skill_id);
                                  const fromWeek = byId.get(skillId);
                                  const resources = Array.isArray(fromWeek?.resources) ? fromWeek.resources : [];
                                  const focus = b?.focus_title ? ` — ${b.focus_title}` : '';
                                  const hours = Math.round(b?.estimated_hours || 0);

                                  return (
                                    <button
                                      key={`${skillId || bi}`}
                                      type="button"
                                      onClick={() =>
                                        setSelected({
                                          weekNumber: weekNum,
                                          dayTitle,
                                          skillName: b?.skill_name,
                                          focusTitle: b?.focus_title,
                                          estimatedHours: hours,
                                          resources,
                                        })
                                      }
                                      className="w-full text-left bg-surface-container-low/30 border border-outline-variant/10 rounded-lg px-3 py-2 hover:border-primary/30 transition-colors"
                                    >
                                      <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0">
                                          <div className="text-sm text-white font-medium truncate">
                                            {b?.skill_name || 'Topic'}
                                            <span className="text-on-surface-variant font-normal">{focus}</span>
                                          </div>
                                          {resources.length > 0 && (
                                            <div className="text-[10px] text-on-surface-variant mt-1">
                                              {resources.length} resource{resources.length === 1 ? '' : 's'}
                                            </div>
                                          )}
                                        </div>
                                        <div className="text-[10px] text-primary whitespace-nowrap">{hours}h</div>
                                      </div>
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {selected && (
          <div className="absolute top-4 right-4 w-[360px] max-w-[92vw] bg-surface-container border border-outline-variant/15 rounded-xl p-4 shadow-[0_20px_60px_rgba(0,0,0,0.5)]">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs uppercase tracking-widest text-on-surface-variant">
                  Week {selected.weekNumber} · {selected.dayTitle}
                </div>
                <div className="text-white font-semibold mt-1 truncate">{selected.skillName || 'Topic'}</div>
                {selected.focusTitle && (
                  <div className="text-xs text-on-surface-variant mt-1">{selected.focusTitle}</div>
                )}
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="text-on-surface-variant hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="mt-3 text-xs text-on-surface-variant">
              {selected.estimatedHours != null ? `Estimated: ${Math.round(selected.estimatedHours || 0)}h` : null}
            </div>

            {Array.isArray(selected.resources) && selected.resources.length > 0 ? (
              <div className="mt-3">
                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">
                  Resources
                </div>
                <div className="space-y-2">
                  {selected.resources.slice(0, 10).map((r, idx) => (
                    <a
                      key={idx}
                      href={r.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block bg-surface-container-low/30 border border-outline-variant/10 rounded-lg px-3 py-2 hover:border-primary/30 transition-colors"
                    >
                      <div className="text-sm text-white">{r.title}</div>
                      <div className="text-[10px] text-on-surface-variant mt-1">
                        {r.provider} • {r.resource_type} • {Math.round(r.estimated_hours || 0)} hrs
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mt-3 text-xs text-on-surface-variant">No resources attached to this topic.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

