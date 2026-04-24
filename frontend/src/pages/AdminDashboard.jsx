import React, { useEffect, useState } from 'react';
import api from '../api/client';
import AppHeader from '../components/AppHeader';

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const res = await api.get('/admin/overview');
        if (mounted) setData(res.data);
      } catch (e) {
        setError('Failed to load admin overview (requires admin access).');
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <>
        <AppHeader />
        <div className="min-h-screen bg-[#0c0e14] pt-28 text-white px-10">Loading…</div>
      </>
    );
  }
  if (error) {
    return (
      <>
        <AppHeader />
        <div className="min-h-screen bg-[#0c0e14] pt-28 text-white px-10">{error}</div>
      </>
    );
  }

  return (
    <>
      <AppHeader />
      <div className="min-h-screen bg-[#0c0e14] pt-28 text-white px-10">
        <h1 className="text-3xl font-bold mb-6">Admin Dashboard</h1>
        <pre className="bg-surface-container p-4 rounded-lg overflow-auto text-sm">
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    </>
  );
}

