import React, { useMemo, useState } from 'react';
import AppHeader from '../components/AppHeader';
import { ingestJd } from '../api/roles';

export default function UploadJds() {
  const [file, setFile] = useState(null);
  const [roleName, setRoleName] = useState('');
  const [department, setDepartment] = useState('');
  const [seniorityLevel, setSeniorityLevel] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const canSubmit = useMemo(() => !!file && !!roleName.trim() && !submitting, [file, roleName, submitting]);

  const onSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError('');
    setResult(null);
    try {
      const res = await ingestJd({
        file,
        roleName: roleName.trim(),
        department: department.trim() || null,
        seniorityLevel: seniorityLevel.trim() || null,
      });
      setResult(res);
    } catch (e) {
      console.error('JD ingest failed', e);
      setError(e?.response?.data?.detail || 'Failed to ingest JD.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <AppHeader />
      {/* MAIN */}
      <main className="max-w-7xl mx-auto px-8 py-10">
      {/* Page Header */}
      <header className="mb-10">
      <h1 className="text-display-lg font-medium tracking-tight text-white mb-2">Upload Job Descriptions</h1>
      <p className="text-on-surface-variant max-w-2xl">
        Upload a JD DOCX to extract skills and populate role requirements (admin-only).
      </p>
      </header>
      <div className="grid grid-cols-12 gap-8">
      {/* LEFT COLUMN (55%) */}
      <div className="col-span-12 lg:col-span-7 space-y-8">
      {/* Upload Area */}
      <section className="surface-container rounded-xl p-8 border-2 border-dashed border-primary-dim/20 bg-gradient-to-b from-primary-dim/5 to-transparent hover:border-primary-dim/40 transition-all duration-500 flex flex-col items-center justify-center text-center group">
      <div className="w-16 h-16 rounded-full bg-primary-dim/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
      <span className="material-symbols-outlined text-primary-dim text-4xl">cloud_upload</span>
      </div>
      <h3 className="text-headline-sm font-medium text-white mb-2">Drag &amp; drop DOCX files here</h3>
      <p className="text-on-surface-variant mb-6">or</p>
      <input
        type="file"
        accept=".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
        className="text-sm text-on-surface-variant"
      />
      <div className="mt-8 pt-6 border-t border-outline-variant/10 w-full flex justify-center gap-6">
      <span className="text-label-md tracking-widest uppercase text-on-surface-variant flex items-center gap-2">
      <span className="material-symbols-outlined text-xs">description</span> .docx files only
                              </span>
      <span className="text-label-md tracking-widest uppercase text-on-surface-variant flex items-center gap-2">
      <span className="material-symbols-outlined text-xs">analytics</span> Max 50 files per batch
                              </span>
      </div>
      </section>
      <section className="surface-container-low rounded-xl p-6 border border-outline-variant/10">
        <h2 className="text-label-md tracking-widest uppercase text-on-surface-variant mb-4">Ingest</h2>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-on-surface-variant uppercase tracking-widest">Role name</label>
            <input
              className="mt-2 w-full bg-surface-container-highest border border-outline-variant/20 rounded-lg px-4 py-3 text-sm text-white"
              value={roleName}
              onChange={(e) => setRoleName(e.target.value)}
              placeholder="e.g., Backend Engineer"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-on-surface-variant uppercase tracking-widest">Department</label>
              <input
                className="mt-2 w-full bg-surface-container-highest border border-outline-variant/20 rounded-lg px-4 py-3 text-sm text-white"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                placeholder="Engineering"
              />
            </div>
            <div>
              <label className="text-xs text-on-surface-variant uppercase tracking-widest">Seniority</label>
              <input
                className="mt-2 w-full bg-surface-container-highest border border-outline-variant/20 rounded-lg px-4 py-3 text-sm text-white"
                value={seniorityLevel}
                onChange={(e) => setSeniorityLevel(e.target.value)}
                placeholder="Senior"
              />
            </div>
          </div>
          <button
            type="button"
            onClick={onSubmit}
            disabled={!canSubmit}
            className="w-full flex items-center justify-center gap-3 px-10 py-4 rounded-full bg-gradient-to-r from-primary to-primary-container text-white font-bold shadow-2xl shadow-primary/40 hover:scale-[1.01] active:scale-95 transition-all disabled:opacity-60"
          >
            {submitting ? 'Extracting…' : 'Start Extraction'}
          </button>
          {!!error && <div className="text-sm text-error">{error}</div>}
          {!!result && (
            <div className="text-sm text-on-surface-variant">
              Role: <span className="text-white font-semibold">{result.role_name}</span> • extracted{' '}
              <span className="text-white font-semibold">{result.extracted_skill_count}</span> skills • linked{' '}
              <span className="text-white font-semibold">{result.linked_requirements}</span>
            </div>
          )}
        </div>
      </section>
      </div>
      {/* RIGHT COLUMN (45%) */}
      <div className="col-span-12 lg:col-span-5 space-y-8">
      {/* Processing Configuration */}
      <section className="glass rounded-xl p-6">
      <h2 className="text-label-md tracking-widest uppercase text-on-surface-variant mb-6 flex items-center gap-2">
      <span className="material-symbols-outlined text-sm">settings_input_component</span>
                              Processing Configuration
                          </h2>
      <div className="space-y-6">
      <div>
      <label className="text-label-md text-on-surface-variant block mb-2 uppercase tracking-tighter">Model Selection</label>
      <div className="relative">
      <select className="w-full bg-surface-container-highest border-none rounded-lg text-sm text-white focus:ring-1 focus:ring-primary-dim/50 py-3 appearance-none">
      <option>Gemini 2.0 Flash Lite</option>
      <option>Gemini 1.5 Pro</option>
      <option>Custom LLM Endpoint</option>
      </select>
      <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-on-surface-variant">expand_more</span>
      </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
      <div>
      <label className="text-label-md text-on-surface-variant block mb-2 uppercase tracking-tighter">Max Retries</label>
      <input className="w-full bg-surface-container-highest border-none rounded-lg text-sm text-white focus:ring-1 focus:ring-primary-dim/50 py-3" type="number" value="3"/>
      </div>
      <div>
      <label className="text-label-md text-on-surface-variant block mb-2 uppercase tracking-tighter">Backoff slider</label>
      <div className="flex items-center gap-3 h-[46px]">
      <input className="accent-primary-dim w-full h-1 bg-surface-container-highest rounded-lg appearance-none cursor-pointer" type="range"/>
      <span className="text-xs text-white bg-surface-container px-2 py-1 rounded">2s</span>
      </div>
      </div>
      </div>
      <div className="space-y-4 pt-2 border-t border-outline-variant/10">
      <label className="flex items-center justify-between cursor-pointer group">
      <span className="text-sm text-on-surface">Log Raw Gemini Responses</span>
      <div className="relative w-10 h-5 bg-surface-container-highest rounded-full transition-colors group-hover:bg-surface-container-highest/80">
      <div className="absolute left-1 top-1 bg-primary-dim w-3 h-3 rounded-full translate-x-5 transition-transform"></div>
      </div>
      </label>
      <label className="flex items-center justify-between cursor-pointer group">
      <span className="text-sm text-on-surface">Save Raw JSON</span>
      <div className="relative w-10 h-5 bg-surface-container-highest rounded-full transition-colors group-hover:bg-surface-container-highest/80">
      <div className="absolute left-1 top-1 bg-outline-variant w-3 h-3 rounded-full transition-transform"></div>
      </div>
      </label>
      </div>
      </div>
      </section>
      {/* Section Detection Preview */}
      <section className="surface-container rounded-xl p-6 border-l-4 border-secondary-dim/30">
      <h2 className="text-label-md tracking-widest uppercase text-on-surface-variant mb-4 flex items-center gap-2">
      <span className="material-symbols-outlined text-sm">segment</span>
                              Section Detection Preview
                          </h2>
      <div className="space-y-2">
      <div className="flex items-center justify-between p-3 rounded-lg bg-surface-container-high/50 hover:bg-surface-container-high transition-colors">
      <span className="text-xs font-mono text-secondary-dim">[KEY RESPONSIBILITIES]</span>
      <span className="text-xs text-on-surface-variant font-medium">12 items</span>
      </div>
      <div className="flex items-center justify-between p-3 rounded-lg bg-surface-container-high/50 hover:bg-surface-container-high transition-colors">
      <span className="text-xs font-mono text-secondary-dim">[TECHNICAL SKILLS]</span>
      <span className="text-xs text-on-surface-variant font-medium">8 items</span>
      </div>
      <div className="flex items-center justify-between p-3 rounded-lg bg-surface-container-high/50 hover:bg-surface-container-high transition-colors">
      <span className="text-xs font-mono text-secondary-dim">[QUALIFICATIONS]</span>
      <span className="text-xs text-on-surface-variant font-medium">4 items</span>
      </div>
      </div>
      </section>
      {/* Batch Statistics */}
      <section className="surface-container-high rounded-xl p-6 relative overflow-hidden">
      <div className="absolute top-0 right-0 p-4 opacity-10">
      <span className="material-symbols-outlined text-6xl text-primary-dim">analytics</span>
      </div>
      <h2 className="text-label-md tracking-widest uppercase text-on-surface-variant mb-6">Batch Statistics</h2>
      <div className="grid grid-cols-2 gap-6">
      <div>
      <p className="text-label-md text-on-surface-variant uppercase tracking-tighter mb-1">Files Processed</p>
      <p className="text-2xl font-bold text-white">2 <span className="text-on-surface-variant font-normal text-sm">of 5</span></p>
      </div>
      <div>
      <p className="text-label-md text-on-surface-variant uppercase tracking-tighter mb-1">Skills Extracted</p>
      <p className="text-2xl font-bold text-white">41</p>
      </div>
      <div>
      <p className="text-label-md text-on-surface-variant uppercase tracking-tighter mb-1">Avg Time</p>
      <p className="text-2xl font-bold text-white">4.2s</p>
      </div>
      <div>
      <p className="text-label-md text-on-surface-variant uppercase tracking-tighter mb-1">Errors</p>
      <p className="text-2xl font-bold text-error">0</p>
      </div>
      </div>
      </section>
      </div>
      </div>
      </main>
    </>
  );
}
