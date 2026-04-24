import React, { useEffect, useState } from 'react';
import { listRoles, setMyTargetRole, getMyTargetRole } from '../api/roles';

export default function TargetRoleSelector({ className = '', onChange }) {
  const [roles, setRoles] = useState([]);
  const [selectedRoleId, setSelectedRoleId] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const rolesData = await listRoles();
        if (!mounted) return;
        setRoles(Array.isArray(rolesData) ? rolesData : []);
        try {
          const tr = await getMyTargetRole();
          if (mounted && tr?.role_id) setSelectedRoleId(String(tr.role_id));
        } catch {
          /* optional */
        }
      } catch (e) {
        console.error('Failed to load roles', e);
        if (mounted) setError('Failed to load roles. Please refresh.');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const handleSelect = async (e) => {
    const roleId = e.target.value;
    if (!roleId) return;
    setSaving(true);
    setError('');
    try {
      const res = await setMyTargetRole({ roleId });
      setSelectedRoleId(String(res.role_id));
      if (typeof onChange === 'function') onChange(res);
    } catch (err) {
      console.error('Failed to set target role', err);
      setError('Failed to set target role.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={className}>
      <div className="flex items-center gap-3 px-4 py-2 bg-surface-container-low rounded-xl border border-outline-variant/15">
        <span className="material-symbols-outlined text-primary text-lg">psychology</span>
        <select
          className="min-w-0 flex-1 cursor-pointer bg-transparent text-sm font-medium text-white focus:outline-none"
          value={selectedRoleId}
          onChange={handleSelect}
          disabled={loading || saving}
        >
          <option value="">
            {loading ? 'Loading roles…' : 'Select target role'}
          </option>
          {roles.map((r) => (
            <option key={r.id} value={r.id} className="text-black">
              {r.name}
            </option>
          ))}
        </select>
        {saving && <span className="text-[10px] text-on-surface-variant uppercase tracking-widest">Saving…</span>}
      </div>
      {!!error && <div className="text-xs text-error mt-2">{error}</div>}
    </div>
  );
}
