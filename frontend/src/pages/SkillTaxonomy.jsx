import React, { useEffect, useMemo, useState } from 'react';
import AppHeader from '../components/AppHeader';
import { getRoleSkills, listRoles } from '../api/roles';

export default function SkillTaxonomyExplorer() {
  const [roles, setRoles] = useState([]);
  const [roleId, setRoleId] = useState('');
  const [roleSkills, setRoleSkills] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await listRoles();
        if (!mounted) return;
        const list = Array.isArray(data) ? data : [];
        setRoles(list);
        if (!roleId && list.length) setRoleId(String(list[0].id));
      } catch (e) {
        if (mounted) setError('Failed to load roles.');
      }
    })();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let mounted = true;
    if (!roleId) return () => {};
    (async () => {
      setLoading(true);
      setError('');
      try {
        const data = await getRoleSkills(roleId);
        if (mounted) setRoleSkills(data);
      } catch (e) {
        console.error('Failed to load role skills', e);
        if (mounted) setError('Failed to load taxonomy for role.');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [roleId]);

  const grouped = useMemo(() => {
    const skills = Array.isArray(roleSkills?.skills) ? roleSkills.skills : [];
    const map = new Map();
    for (const s of skills) {
      const cat = String(s.category || 'Uncategorized');
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat).push(s);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [roleSkills]);

  return (
    <>
      <AppHeader />
      <main className="pt-28 flex-1 p-8 overflow-y-auto">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-6">
          <div>
            <h1 className="text-3xl font-display font-medium text-white tracking-tight mb-1">
              Skill Taxonomy Explorer
            </h1>
            <p className="text-on-surface-variant text-sm">
              Browse and analyze skills required by each role.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <a
              href="/jds"
              className="px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10 text-xs font-bold text-on-surface-variant hover:text-white hover:bg-surface-container-high transition-colors"
            >
              Ingest JD
            </a>
            <div className="flex items-center gap-3 bg-surface-container-low px-4 py-2 rounded-xl border border-outline-variant/10">
              <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Role</span>
              <select
                className="bg-transparent text-sm text-white focus:outline-none"
                value={roleId}
                onChange={(e) => setRoleId(e.target.value)}
              >
                {roles.map((r) => (
                  <option key={r.id} value={r.id} className="text-black">
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {loading && <div className="text-on-surface-variant text-sm">Loading taxonomy…</div>}
        {!loading && error && (
          <div className="text-white bg-error/20 border border-error/40 p-4 rounded-xl mb-8">{error}</div>
        )}

        {!loading && !error && roleSkills && (
          <>
            <div className="glass-panel p-6 rounded-xl border border-outline-variant/10 mb-8 flex flex-col md:flex-row justify-between gap-6">
              <div className="flex items-start gap-5">
                <div className="w-16 h-16 bg-primary-container/20 rounded-2xl flex items-center justify-center">
                  <span
                    className="material-symbols-outlined text-3xl text-primary"
                    style={{ fontVariationSettings: '"FILL" 1' }}
                  >
                    neurology
                  </span>
                </div>
                <div>
                  <h2 className="text-xl font-medium text-white mb-2">{roleSkills.role_name}</h2>
                  <div className="flex flex-wrap gap-x-6 gap-y-2">
                    <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                      <span className="material-symbols-outlined text-sm">category</span>
                      {roleSkills.department || '—'}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                      <span className="material-symbols-outlined text-sm">workspace_premium</span>
                      {roleSkills.seniority_level || '—'}
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-end justify-center">
                <div className="text-4xl font-display font-medium text-primary">
                  {(roleSkills.skills || []).length}
                </div>
                <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                  Total Skills
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {grouped.map(([cat, skills]) => (
                <details
                  key={cat}
                  className="rounded-xl border border-outline-variant/15 overflow-hidden bg-surface-container-low/40"
                  open
                >
                  <summary className="w-full flex items-center justify-between p-5 bg-surface-container-high/40 text-left cursor-pointer">
                    <div className="flex items-center gap-4">
                      <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                        <span className="material-symbols-outlined text-primary text-lg">construction</span>
                      </div>
                      <div>
                        <span className="text-base font-medium text-white">{cat}</span>
                        <span className="ml-3 text-xs text-on-surface-variant/70">
                          {skills.length} skills
                        </span>
                      </div>
                    </div>
                    <span className="material-symbols-outlined text-on-surface-variant">expand_more</span>
                  </summary>
                  <div className="p-6 bg-surface-container/20">
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                      {skills.map((s) => (
                        <div
                          key={s.skill_id}
                          className="bg-surface-container-highest p-4 rounded-xl border border-outline-variant/5 hover:border-primary/20 transition-all duration-300"
                        >
                          <div className="flex justify-between items-start mb-3">
                            <div>
                              <h4 className="text-sm font-semibold text-white mb-1">{s.skill_name}</h4>
                              <span
                                className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full ${
                                  s.is_mandatory
                                    ? 'bg-primary/10 text-primary'
                                    : 'bg-surface-variant text-on-surface-variant'
                                }`}
                              >
                                {s.is_mandatory ? 'Mandatory' : 'Optional'}
                              </span>
                            </div>
                            <div className="text-right">
                              <span className="text-xs font-bold text-tertiary">
                                {Math.round((s.importance || 0) * 100)}%
                              </span>
                              <p className="text-[10px] text-on-surface-variant uppercase">Importance</p>
                            </div>
                          </div>
                          <div className="text-[10px] text-on-surface-variant uppercase tracking-wider font-medium">
                            Min proficiency: {s.min_proficiency}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </details>
              ))}
            </div>
          </>
        )}
      </main>
    </>
  );
}

