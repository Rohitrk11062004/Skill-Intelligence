import React, { useEffect, useMemo, useRef, useState } from 'react';
import AppHeader from '../components/AppHeader';
import { getMyResumes } from '../api/users';
import { getMyGaps, getMyGapsSummary } from '../api/gaps';
import { uploadResume, startProcessing, pollStatus, getResults } from '../api/resume';
import { deleteLearningPlan, getLearningRoadmap } from '../api/learning';
import TargetRoleSelector from '../components/TargetRoleSelector';
import { getMyTargetRole } from '../api/roles';

const POLL_MS = 2000;
const PROCESS_WAIT_MS = 10 * 60 * 1000;

/** Prefer FastAPI `detail` over axios generic `Request failed with status code …`. */
function formatAxiosError(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d))
    return d.map((x) => (typeof x === 'string' ? x : x?.msg || JSON.stringify(x))).join(' ');
  return '';
}

async function waitUntilResumeComplete(jobId) {
  const started = Date.now();
  while (Date.now() - started < PROCESS_WAIT_MS) {
    const res = await pollStatus(jobId);
    const st = (res?.status || '').toLowerCase();
    if (st === 'complete') return;
    if (st === 'failed' || st === 'error' || res?.error_message) {
      throw new Error(res?.error_message || 'Resume processing failed.');
    }
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
  throw new Error('Resume processing timed out. Try again.');
}

export default function SkillAnalysisTopNav() {
  const [resumes, setResumes] = useState([]);
  const [file, setFile] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [jobId, setJobId] = useState(null);
  /** 'upload' | 'extract' | 'gaps' — sub-step while loading */
  const [pipelineStep, setPipelineStep] = useState('');
  const [extraction, setExtraction] = useState(null);
  const [gapsSummary, setGapsSummary] = useState(null);
  const [gaps, setGaps] = useState([]);
  const [roadmap, setRoadmap] = useState(null);
  const [loading, setLoading] = useState(false);
  const [deletingPath, setDeletingPath] = useState(false);
  const [error, setError] = useState('');
  /** Hours available for studying on each study day */
  const [dailyHours, setDailyHours] = useState(2);
  /** How many days per week the learner dedicates (Mon-first block) */
  const [studyDaysPerWeek, setStudyDaysPerWeek] = useState(5);
  const [weeksCount, setWeeksCount] = useState(8);

  const [filePreviewUrl, setFilePreviewUrl] = useState(null);
  const replaceFileInputRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await getMyResumes();
        if (mounted) setResumes(Array.isArray(r) ? r : []);
      } catch {
        // optional
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!file) {
      setFilePreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setFilePreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const isPdfFile = useMemo(() => {
    if (!file) return false;
    const t = (file.type || '').toLowerCase();
    const n = (file.name || '').toLowerCase();
    return t === 'application/pdf' || n.endsWith('.pdf');
  }, [file]);

  const extractedSkills = useMemo(() => {
    const skills = extraction?.skills;
    if (Array.isArray(skills)) {
      return skills
        .map((s) => {
          if (!s) return null;
          if (typeof s === 'string') return { name: s };
          if (typeof s === 'object') {
            return {
              name: s.skill || s.skill_name || s.name || '',
              source: s.source || s.category || '',
              confidence: s.confidence ?? s.score ?? null,
            };
          }
          return null;
        })
        .filter((x) => x && x.name);
    }
    return [];
  }, [extraction]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError('');
      setExtraction(null);
      setGapsSummary(null);
      setGaps([]);
      setRoadmap(null);
    }
  };

  const clearSelectedFile = () => {
    setFile(null);
    setFileInputKey((k) => k + 1);
  };

  const runGapAnalysis = async () => {
    setError('');

    if (!file) {
      setError('Select a resume file before running gap analysis.');
      return;
    }

    try {
      const tr = await getMyTargetRole();
      if (!tr?.role_id) {
        setError('Select a target role before running gap analysis.');
        return;
      }
    } catch {
      setError('Could not verify target role. Try again.');
      return;
    }

    setLoading(true);
    setPipelineStep('');
    try {
      setPipelineStep('upload');
      const up = await uploadResume(file);
      const id = up?.job_id;
      if (!id) throw new Error('Upload succeeded but no job_id returned');
      setJobId(id);
      await startProcessing(id);
      setPipelineStep('extract');
      await waitUntilResumeComplete(id);
      const data = await getResults(id);
      setExtraction(data);
      try {
        const r = await getMyResumes();
        setResumes(Array.isArray(r) ? r : []);
      } catch {
        // ignore
      }

      await new Promise((r) => requestAnimationFrame(() => r(undefined)));

      setPipelineStep('gaps');
      // Run sequentially: both endpoints recompute gaps; parallel calls can contend on DB (e.g. SQLite).
      const summary = await getMyGapsSummary();
      const list = await getMyGaps();
      setGapsSummary(summary);
      setGaps(Array.isArray(list?.gaps) ? list.gaps : []);
    } catch (e) {
      console.error('Gap analysis failed', e);
      const apiDetail = formatAxiosError(e);
      const msg = apiDetail || e?.message || '';
      if (msg.includes('timed out')) {
        setError(msg);
      } else if (apiDetail) {
        setError(apiDetail);
      } else {
        setError(
          'Gap analysis failed. Ensure your resume processed successfully and your target role is valid.'
        );
      }
    } finally {
      setLoading(false);
      setPipelineStep('');
    }
  };

  const generateLearningPath = async () => {
    setLoading(true);
    setError('');
    try {
      const dh = Number(dailyHours);
      const sd = Number(studyDaysPerWeek);
      const wc = Number(weeksCount);
      const params = {
        daily_hours: Number.isFinite(dh) && dh > 0 ? dh : 2,
        study_days_per_week: Number.isFinite(sd) && sd >= 1 && sd <= 7 ? Math.floor(sd) : 5,
        deadline_weeks: Number.isFinite(wc) && wc > 0 ? wc : 8,
      };

      const data = await getLearningRoadmap(params);
      setRoadmap(data);
    } catch (e) {
      console.error('Learning path generation failed', e);
      let msg = formatAxiosError(e);
      if (!msg) {
        msg =
          'Failed to generate learning path. Ensure you uploaded & processed a resume and set a target role.';
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

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

  const weeks = useMemo(() => (Array.isArray(roadmap?.weeks) ? roadmap.weeks : []), [roadmap]);

  const runGapAnalysisLabel = useMemo(() => {
    if (!loading) return 'Run Gap Analysis';
    if (pipelineStep === 'upload') return 'Uploading resume…';
    if (pipelineStep === 'extract') return 'Extracting skills…';
    if (pipelineStep === 'gaps') return 'Running gap analysis…';
    return 'Working…';
  }, [loading, pipelineStep]);

  const workflowSteps = useMemo(
    () => [
      {
        key: 'resume',
        label: 'Resume',
        icon: 'upload_file',
      },
      {
        key: 'extract',
        label: 'Extract skills',
        icon: 'psychology',
      },
      {
        key: 'gaps',
        label: 'Gap analysis',
        icon: 'analytics',
      },
    ],
    []
  );

  const pipelineVisual = useMemo(() => {
    const resumeReady = Boolean(file);
    const extractedDone = Boolean(extraction);
    const gapsDone = Boolean(gapsSummary);

    const stepStatus = workflowSteps.map((_, index) => {
      if (index === 0) {
        if (resumeReady || extractedDone || gapsDone) return 'complete';
        return 'pending';
      }
      if (index === 1) {
        if (extractedDone || gapsDone) return 'complete';
        if (loading && (pipelineStep === 'upload' || pipelineStep === 'extract')) return 'active';
        return 'pending';
      }
      if (index === 2) {
        if (gapsDone) return 'complete';
        if (loading && pipelineStep === 'gaps') return 'active';
        return 'pending';
      }
      return 'pending';
    });

    let progressPct = 0;
    if (gapsDone) progressPct = 100;
    else if (loading && pipelineStep === 'gaps') progressPct = 88;
    else if (extractedDone) progressPct = 66;
    else if (loading && (pipelineStep === 'extract' || pipelineStep === 'upload')) progressPct = 42;
    else if (resumeReady) progressPct = 15;

    return { stepStatus, progressPct };
  }, [file, extraction, gapsSummary, loading, pipelineStep, workflowSteps]);

  return (
    <>
      <AppHeader />
      {/* MAIN */}
      <main className="flex-1 flex flex-col h-screen relative bg-surface-dim">
      {/* Page Content Scrollable Area */}
      <div className="flex-1 overflow-y-auto pt-28 pb-12 px-10">
      <div className="max-w-[1400px] mx-auto">
      {/* Page Header */}
      <div className="mb-8">
      <h2 className="font-headline text-headline-sm text-on-surface tracking-tight">Skill Analysis</h2>
      <p className="text-body-md text-on-surface-variant mt-1">
        Select a target role, upload a resume, then run gap analysis to extract skills and compare them to your role.
      </p>
      </div>
      <div className="mb-8 flex flex-wrap gap-3">
        <div className="min-w-[260px]">
          <TargetRoleSelector
            className="w-full"
            onChange={() => {
              // target role change affects gaps + roadmap
              setGapsSummary(null);
              setGaps([]);
              setRoadmap(null);
            }}
          />
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10">
          <span className="text-xs font-bold text-on-surface-variant">Hours/day</span>
          <input
            type="number"
            min={0.5}
            max={24}
            step={0.5}
            value={dailyHours}
            onChange={(e) => setDailyHours(e.target.value)}
            className="w-16 bg-transparent text-white text-sm font-medium focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10">
          <span className="text-xs font-bold text-on-surface-variant">Study days/wk</span>
          <select
            value={studyDaysPerWeek}
            onChange={(e) => setStudyDaysPerWeek(Number(e.target.value))}
            className="bg-transparent text-white text-sm font-medium focus:outline-none appearance-none pr-6"
          >
            {[3, 4, 5, 6, 7].map((n) => (
              <option key={n} value={n} className="bg-surface-container text-white">
                {n} days
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container-low border border-outline-variant/10">
          <span className="text-xs font-bold text-on-surface-variant">Weeks</span>
          <input
            type="number"
            min={1}
            max={104}
            value={weeksCount}
            onChange={(e) => setWeeksCount(e.target.value)}
            className="w-24 bg-transparent text-white text-sm font-medium focus:outline-none placeholder:text-on-surface-variant/70"
          />
        </div>
      </div>
      {!!error && (
        <div className="mb-6 p-4 rounded-lg bg-error/20 text-error border border-error/50">{error}</div>
      )}
      {/* Tab 1 Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      {/* Left Column */}
      <div className="lg:col-span-3 flex flex-col gap-6">
      {/* Upload Card */}
      <div className="bg-surface-container rounded-xl p-8 relative overflow-hidden group border border-outline-variant/10">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-32 bg-primary/5 blur-[80px] pointer-events-none"></div>
      <div className="relative z-10 flex flex-col items-stretch w-full">
      {!file ? (
        <div className="w-full border-2 border-dashed border-outline-variant/30 hover:border-primary/50 hover:bg-surface-container-highest/30 transition-all duration-300 rounded-xl p-12 flex flex-col items-center justify-center cursor-pointer bg-surface-container-highest/10 relative overflow-hidden text-center">
          <input
            key={fileInputKey}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={handleFileChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
          />
          <div className="w-16 h-16 rounded-full bg-surface-bright/40 backdrop-blur-md flex items-center justify-center mb-4 border border-outline-variant/20 group-hover:scale-110 transition-transform duration-300 group-hover:shadow-[0_0_20px_rgba(105,156,255,0.2)]">
            <span className="material-symbols-outlined text-3xl text-primary-dim">cloud_upload</span>
          </div>
          <h3 className="text-on-surface font-medium mb-1">Drop your resume here or click to browse</h3>
          <p className="text-on-surface-variant text-sm">PDF, DOCX — Max 10MB</p>
          <p className="text-on-surface-variant text-xs mt-4 max-w-md mx-auto leading-relaxed">
            Choose a resume file below, pick a target role above, then use <span className="text-on-surface font-medium">Run Gap Analysis</span>{' '}
            to extract skills and analyze gaps.
          </p>
        </div>
      ) : (
        <div className="w-full space-y-5">
          <div className="rounded-xl border border-outline-variant/20 bg-surface-container-highest/20 overflow-hidden">
            <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-outline-variant/15 bg-surface-container-low/40">
              <div className="min-w-0 text-left">
                <div className="text-sm font-medium text-on-surface truncate">{file.name}</div>
                <div className="text-[10px] text-on-surface-variant uppercase tracking-widest mt-0.5">
                  {(file.size / 1024).toFixed(0)} KB · {isPdfFile ? 'PDF' : 'DOCX'}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <input
                  ref={replaceFileInputRef}
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => replaceFileInputRef.current?.click()}
                  className="px-3 py-1.5 rounded-lg border border-outline-variant/30 text-xs font-medium text-on-surface-variant hover:text-white hover:bg-surface-bright/20 transition-colors"
                >
                  Replace file
                </button>
                <button
                  type="button"
                  onClick={clearSelectedFile}
                  className="px-3 py-1.5 rounded-lg border border-outline-variant/30 text-xs font-medium text-on-surface-variant hover:text-error hover:border-error/40 transition-colors"
                >
                  Remove
                </button>
              </div>
            </div>
            {isPdfFile && filePreviewUrl ? (
              <iframe
                title="Resume preview"
                src={`${filePreviewUrl}#toolbar=0&navpanes=0`}
                className="w-full min-h-[320px] h-[min(480px,55vh)] bg-black/40"
              />
            ) : (
              <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                <span className="material-symbols-outlined text-5xl text-primary/70">draft</span>
                <p className="mt-4 text-sm text-on-surface-variant max-w-sm">
                  Word documents are processed on the server. Run gap analysis to extract skills from this file.
                </p>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={runGapAnalysis}
            disabled={loading}
            className="w-full py-4 rounded-xl bg-gradient-to-r from-primary to-primary-container text-on-primary font-medium text-base shadow-[0_4px_20px_rgba(67,136,253,0.3)] hover:shadow-[0_6px_25px_rgba(67,136,253,0.4)] transition-all active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-60"
          >
            <span className={`material-symbols-outlined text-xl ${loading ? 'animate-spin' : ''}`}>
              {loading ? 'sync' : 'analytics'}
            </span>
            {runGapAnalysisLabel}
          </button>

          {loading && pipelineStep ? (
            <div className="w-full text-sm text-on-surface-variant flex items-center justify-center gap-2">
              <span className={`material-symbols-outlined text-lg text-primary ${pipelineStep !== 'gaps' ? 'animate-spin' : ''}`}>
                {pipelineStep === 'gaps' ? 'analytics' : 'sync'}
              </span>
              <span className="text-primary">{runGapAnalysisLabel}</span>
            </div>
          ) : null}
        </div>
      )}
      </div>
      </div>
      {/* Processing Pipeline Section */}
      <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/10">
        <h4 className="font-label text-label-md text-on-surface-variant mb-6 uppercase tracking-[0.05em]">
          Analysis Pipeline Status
        </h4>
        <div className="flex items-start justify-between relative px-1 pt-1 pb-2 min-h-[88px]">
          <div className="absolute top-5 left-4 right-4 h-0.5 bg-surface-container-highest z-0 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary to-primary/25 rounded-full transition-[width] duration-700 ease-out shadow-[0_0_12px_rgba(105,156,255,0.35)]"
              style={{ width: `${pipelineVisual.progressPct}%` }}
            />
          </div>
          {workflowSteps.map((step, i) => {
            const status = pipelineVisual.stepStatus[i];
            const isComplete = status === 'complete';
            const isActive = status === 'active';
            return (
              <div
                key={step.key}
                className="relative z-10 flex flex-col items-center gap-2 w-[30%] min-w-0"
              >
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center border transition-colors ${
                    isComplete
                      ? 'bg-surface-dim border-primary shadow-[0_0_14px_rgba(105,156,255,0.35)]'
                      : isActive
                        ? 'bg-surface-dim border-primary ring-2 ring-primary/45 ring-offset-2 ring-offset-surface-container'
                        : 'bg-surface-container-highest border-outline-variant/35'
                  }`}
                >
                  {isComplete ? (
                    <span className="material-symbols-outlined text-primary text-base font-bold">check</span>
                  ) : (
                    <span
                      className={`material-symbols-outlined text-base ${
                        isActive ? 'text-primary' : 'text-on-surface-variant'
                      }`}
                    >
                      {step.icon}
                    </span>
                  )}
                </div>
                <span
                  className={`text-[11px] sm:text-xs font-medium text-center leading-tight px-0.5 ${
                    isComplete || isActive ? 'text-on-surface' : 'text-on-surface-variant'
                  }`}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Extracted Skills */}
      <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/10">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-headline text-base font-medium text-on-surface">Extracted Skills</h3>
          {!!extraction && (
            <div className="text-xs text-on-surface-variant">
              {extractedSkills.length} skills
            </div>
          )}
        </div>
        {!extraction && (
          <div className="text-sm text-on-surface-variant">
            Choose a resume file below, then use Run Gap Analysis under the preview to extract skills.
          </div>
        )}
        {!!extraction && extractedSkills.length === 0 && (
          <div className="text-sm text-on-surface-variant">
            Extraction finished, but no skills were returned.
          </div>
        )}
        {extractedSkills.length > 0 && (
          <ul className="space-y-2">
            {extractedSkills.map((s, idx) => (
              <li
                key={`${s.name}-${idx}`}
                className="p-3 rounded-lg bg-surface-container-low border border-outline-variant/10 flex items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="text-sm text-white truncate">{s.name}</div>
                  <div className="text-[10px] text-on-surface-variant uppercase tracking-widest mt-1">
                    {s.source ? s.source : 'extracted'}
                  </div>
                </div>
                <div className="text-xs text-on-surface-variant">
                  {typeof s.confidence === 'number' ? `${Math.round(s.confidence * 100)}%` : ''}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      </div>
      {/* Right Column */}
      <div className="lg:col-span-2 space-y-6">
        <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-headline text-base font-medium text-on-surface">Upload History</h3>
            <a className="text-xs text-primary hover:underline" href="/settings">
              View full
            </a>
          </div>
          {resumes.length === 0 ? (
            <div className="text-sm text-on-surface-variant">
              No uploads yet. <a className="text-primary hover:underline" href="/resumes">Upload a resume</a>.
            </div>
          ) : (
            <div className="space-y-2">
              {resumes.slice(0, 5).map((r) => (
                <div
                  key={r.id}
                  className="p-3 rounded-lg bg-surface-container-low border border-outline-variant/10 flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="text-sm text-white truncate">{r.file_name}</div>
                    <div className="text-[10px] text-on-surface-variant uppercase tracking-widest mt-1">
                      {r.status} • {r.skills_count} skills
                    </div>
                  </div>
                  <div className="text-xs text-on-surface-variant">
                    {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/10">
          <div className="mb-4">
            <h3 className="font-headline text-base font-medium text-on-surface">Gap Analysis</h3>
          </div>
          {!!error && <div className="text-xs text-error mb-3">{error}</div>}
          {gapsSummary && (
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="bg-surface-container-low/30 border border-outline-variant/10 rounded-lg p-3">
                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant">Readiness</div>
                <div className="text-white font-semibold">
                  {Math.round((gapsSummary.readiness_score || 0) * 100)}%
                </div>
              </div>
              <div className="bg-surface-container-low/30 border border-outline-variant/10 rounded-lg p-3">
                <div className="text-[10px] uppercase tracking-widest text-on-surface-variant">Total gaps</div>
                <div className="text-white font-semibold">{gapsSummary.total_gaps}</div>
              </div>
            </div>
          )}
          {gaps.length > 0 && (
            <div className="space-y-2">
              {gaps.slice(0, 6).map((g) => (
                <div
                  key={g.skill_id}
                  className="bg-surface-container-low/30 border border-outline-variant/10 rounded-lg p-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm text-white font-medium">{g.skill_name}</div>
                    <div className="text-[10px] text-on-surface-variant uppercase tracking-widest">{g.gap_type}</div>
                  </div>
                  <div className="text-[10px] text-on-surface-variant mt-1">
                    Priority {Math.round(g.priority_score || 0)} • {g.time_to_learn_hours} hrs
                  </div>
                </div>
              ))}
            </div>
          )}
          {!loading && !error && !gapsSummary && (
            <div className="text-sm text-on-surface-variant">
              Run gap analysis to compute missing/weak skills for your target role.
            </div>
          )}
        </div>

        <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/10">
          <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
            <h3 className="font-headline text-base font-medium text-on-surface">Learning Path</h3>
            <div className="flex items-center gap-2 shrink-0">
              {!!roadmap && (
                <button
                  type="button"
                  onClick={deleteLearningPath}
                  disabled={loading || deletingPath}
                  className="px-3 py-1.5 rounded-lg border border-error/40 text-error text-xs font-semibold hover:bg-error/10 transition-all disabled:opacity-60"
                >
                  {deletingPath ? 'Deleting…' : 'Delete path'}
                </button>
              )}
              <button
                type="button"
                onClick={generateLearningPath}
                disabled={loading || deletingPath}
                className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-primary to-primary-container text-on-primary text-xs font-bold hover:brightness-110 transition-all disabled:opacity-60"
              >
                {loading ? 'Generating…' : 'Generate Learning Path'}
              </button>
            </div>
          </div>
          {!roadmap && (
            <div className="text-sm text-on-surface-variant">
              After gap analysis, use Generate Learning Path to build your plan from gaps and your target role.
            </div>
          )}
          {!!roadmap && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-surface-container-low/30 border border-outline-variant/10 rounded-lg p-3">
                  <div className="text-[10px] uppercase tracking-widest text-on-surface-variant">Target role</div>
                  <div className="text-white font-semibold">{roadmap.target_role || '—'}</div>
                </div>
                <div className="bg-surface-container-low/30 border border-outline-variant/10 rounded-lg p-3">
                  <div className="text-[10px] uppercase tracking-widest text-on-surface-variant">Readiness</div>
                  <div className="text-white font-semibold">
                    {Math.round(((roadmap.readiness_score || 0) * 100) || 0)}%
                  </div>
                </div>
              </div>

              {weeks.length > 0 && (
                <ul className="space-y-2">
                  {weeks.map((w) => (
                    <li key={w.week_number} className="p-3 rounded-lg bg-surface-container-low border border-outline-variant/10">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm text-white font-medium">
                          Week {w.week_number}: {w.week_title || 'Focus'}
                        </div>
                        <div className="text-[10px] text-on-surface-variant uppercase tracking-widest">
                          {w.total_hours ? `${Math.round(w.total_hours)}h` : ''}
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {(w.skills || []).slice(0, 8).map((s, idx) => (
                          <span
                            key={idx}
                            className="px-3 py-1 rounded-full text-[10px] bg-primary/10 border border-primary/20 text-primary"
                          >
                            {s.skill_name || s}
                          </span>
                        ))}
                      </div>
                      {Array.isArray(w.days) && w.days.some((d) => (d.estimated_hours || 0) > 0) && (
                        <div className="mt-3 pt-3 border-t border-outline-variant/15 space-y-2">
                          <div className="text-[10px] uppercase tracking-widest text-on-surface-variant">Daily plan</div>
                          {w.days
                            .filter((d) => (d.estimated_hours || 0) > 0 || (d.capacity_hours || 0) > 0)
                            .map((d) => (
                              <div
                                key={`${w.week_number}-${d.day_index}`}
                                className="text-xs bg-surface-container-highest/15 rounded-lg px-2 py-1.5 border border-outline-variant/10"
                              >
                                <span className="text-white font-medium">{d.day_name}</span>
                                <span className="text-on-surface-variant ml-2">
                                  {Math.round(d.estimated_hours || 0)}h
                                  {d.capacity_hours ? ` / ${Math.round(d.capacity_hours)}h cap` : ''}
                                </span>
                                {(d.skills || []).length > 0 && (
                                  <span className="text-on-surface-variant block mt-1">
                                    {(d.skills || []).map((b) => b.skill_name).join(' · ')}
                                  </span>
                                )}
                              </div>
                            ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {weeks.length === 0 && (
                <div className="text-sm text-on-surface-variant">No roadmap weeks returned.</div>
              )}
            </div>
          )}
        </div>
      </div>
      </div>
      </div>
      </div>
      </main>
    </>
  );
}
