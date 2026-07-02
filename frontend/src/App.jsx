import { useEffect, useMemo, useRef, useState } from "react";
import logoUrl from "./assets/logo.png";

const POLL_INTERVAL = 2500;

const stageMap = {
  queued: "Queued",
  running: "Analyzing",
  completed: "Completed",
  failed: "Failed",
};

const artifactLabels = {
  report_html: "HTML report",
  analysis_json: "Insight JSON",
  cleaned_xlsx: "Cleaned workbook",
  selected_csv: "Selected reviews",
  metadata_json: "Pipeline metadata",
  summary_md: "Markdown summary",
};

const workflowSteps = [
  { label: "Clean", detail: "Deduplicate, verify, and select useful review text." },
  { label: "Analyze", detail: "Extract personas, pain points, advantages, and semantic themes." },
  { label: "Package", detail: "Create the report, source files, and workflow summary." },
];

const deliverables = [
  "Executive HTML report",
  "Structured insight JSON",
  "Cleaned review workbook",
  "Selected review CSV",
];

function App() {
  if (window.location.pathname.startsWith("/admin")) {
    return <AdminDashboard />;
  }
  return <UserWorkspace />;
}

function UserWorkspace() {
  const [health, setHealth] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [activeJobId, setActiveJobId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState("");
  const [error, setError] = useState("");
  const reviewInputRef = useRef(null);
  const identityRef = useRef(getTrackingIdentity());

  useEffect(() => {
    recordPageView(identityRef.current);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      try {
        const [healthRes, jobsRes] = await Promise.all([
          fetch("/api/health"),
          fetch("/api/jobs"),
        ]);
        const [healthData, jobsData] = await Promise.all([
          healthRes.json(),
          jobsRes.json(),
        ]);
        if (cancelled) {
          return;
        }
        setHealth(healthData);
        setJobs(jobsData);
        setActiveJobId((current) => current || jobsData[0]?.job_id || "");
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message);
        }
      }
    }

    refresh();
    const timer = window.setInterval(refresh, POLL_INTERVAL);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const activeJob = useMemo(
    () => jobs.find((job) => job.job_id === activeJobId) ?? jobs[0] ?? null,
    [activeJobId, jobs],
  );
  const reportArtifact = activeJob?.artifacts.find((artifact) => artifact.name === "report_html") ?? null;
  const bundleUrl = activeJob ? `/api/jobs/${activeJob.job_id}/download` : "";
  const runningJobs = jobs.filter((job) => job.status === "running" || job.status === "queued").length;
  const completedJobs = jobs.filter((job) => job.status === "completed").length;
  const failedJobs = jobs.filter((job) => job.status === "failed").length;
  const configuredProviders = health?.providers?.filter((provider) => provider.configured).length ?? 0;
  const metricCards = [
    { label: "Queue", value: runningJobs, detail: runningJobs ? "Runs in progress" : "Ready for a new file" },
    { label: "Reports", value: completedJobs, detail: "Finished insight packs" },
    { label: "Reviews", value: activeJob?.summary?.total_selected_reviews ?? "CSV/XLSX", detail: activeJob ? "Selected in active run" : "Supported input formats" },
  ];

  async function submitJob(event) {
    event.preventDefault();
    setError("");
    const form = event.currentTarget;
    const reviewFile = reviewInputRef.current?.files?.[0];
    if (!reviewFile) {
      setError("Choose a CSV or Excel review export before starting analysis.");
      return;
    }
    const { sessionId, visitId } = identityRef.current;
    const formData = new FormData();
    formData.append("review_file", reviewFile);
    formData.append("session_id", sessionId);
    formData.append("visit_id", visitId);
    setSubmitting(true);
    try {
      const response = await fetch("/api/jobs", { method: "POST", body: formData });
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || "Unable to create job");
      }
      const job = await response.json();
      setActiveJobId(job.job_id);
      setJobs((current) => [job, ...current.filter((item) => item.job_id !== job.job_id)]);
      form.reset();
      setSelectedFileName("");
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/">
          <img src={logoUrl} alt="Amazon Review Insight" />
          <span>
            <strong>Amazon Review Insight</strong>
            <small>Review intelligence workspace</small>
          </span>
        </a>
        <div className="system-strip">
          <StatusPill label="API" status={health ? "Live" : "Loading"} tone={health ? "good" : "idle"} />
          <StatusPill label="Providers" status={`${configuredProviders} ready`} tone={configuredProviders ? "good" : "warn"} />
          <StatusPill label="Queue" status={runningJobs ? `${runningJobs} active` : "Idle"} tone={runningJobs ? "busy" : "idle"} />
        </div>
      </header>

      <main className="workspace product-workspace">
        <section className="product-hero">
          <div className="hero-copy">
            <p className="eyebrow">Amazon review intelligence</p>
            <h1>Turn raw reviews into a report your team can act on.</h1>
            <p>
              Upload one Amazon review export. The workflow cleans the data, extracts commercial themes,
              and returns a polished report pack for product, content, and category decisions.
            </p>
          </div>

          <form className="upload-console hero-upload" onSubmit={submitJob}>
            <label className={`file-drop ${selectedFileName ? "file-drop-ready" : ""}`}>
              <span className="file-drop-label">Review export</span>
              <strong>{selectedFileName || "Drop or select a CSV / XLSX file"}</strong>
              <small>{selectedFileName ? "Ready to start the analysis run" : "SellerSprite and standard Amazon exports are supported"}</small>
              <input
                ref={reviewInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(event) => setSelectedFileName(event.target.files?.[0]?.name || "")}
              />
            </label>
            <button className="primary-button" disabled={submitting} type="submit">
              {submitting ? "Submitting..." : "Start analysis"}
            </button>
            {error ? <p className="error-text">{error}</p> : null}
          </form>

          <div className="workflow-strip">
            {workflowSteps.map((step, index) => (
              <article className="workflow-step" key={step.label}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </article>
            ))}
          </div>
        </section>

        <aside className="report-preview panel">
          <div className="report-preview-head">
            <p className="eyebrow">Report pack</p>
            <span className="badge badge-queued">{configuredProviders ? "LLM ready" : "Provider needed"}</span>
          </div>
          <div className="report-sheet">
            <div className="sheet-kicker">Amazon Review Insight</div>
            <h2>Decision report</h2>
            <div className="sheet-bars">
              <span />
              <span />
              <span />
            </div>
            <div className="sheet-grid">
              <span />
              <span />
              <span />
              <span />
            </div>
          </div>
          <div className="deliverable-list">
            {deliverables.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </aside>

        <section className="metrics-grid workspace-metrics" aria-label="Workspace status">
          {metricCards.map((card) => (
            <article className="metric-card" key={card.label}>
              <span>{card.label}</span>
              <strong>{typeof card.value === "number" ? formatNumber(card.value) : card.value}</strong>
              <small>{card.detail}</small>
            </article>
          ))}
        </section>

        <section className="jobs-panel panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Recent runs</p>
              <h2>Recent analyses</h2>
            </div>
            <span className="count-chip">{jobs.length}</span>
          </div>
          <div className="job-list">
            {jobs.length ? (
              jobs.map((job) => (
                <button
                  className={`job-item ${activeJob?.job_id === job.job_id ? "job-item-active" : ""}`}
                  key={job.job_id}
                  onClick={() => setActiveJobId(job.job_id)}
                  type="button"
                >
                  <span className={`status-dot status-${job.status}`} />
                  <span className="job-text">
                    <strong>{job.input_filename}</strong>
                    <small>{formatDate(job.created_at)} · {job.job_id}</small>
                  </span>
                  <span className={`badge badge-${job.status}`}>{stageMap[job.status] ?? job.status}</span>
                </button>
              ))
            ) : (
              <EmptyState title="No analyses yet" body="Upload a review export to create the first run." />
            )}
          </div>
        </section>

        <section className="results-panel panel" id="results">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Active report</p>
              <h2>{activeJob ? activeJob.input_filename : "Waiting for analysis"}</h2>
            </div>
            {activeJob ? <span className={`badge badge-${activeJob.status}`}>{stageMap[activeJob.status] ?? activeJob.status}</span> : null}
          </div>

          {activeJob ? (
            <>
              <ProgressBlock job={activeJob} />

              {reportArtifact?.preview_url ? (
                <div className="report-callout">
                  <div>
                    <span>Primary output</span>
                    <strong>Open the finished HTML report first.</strong>
                    <small>Use the full bundle when you need the source files behind the report.</small>
                  </div>
                  <div className="callout-actions">
                    <a className="primary-button" href={reportArtifact.preview_url} target="_blank" rel="noreferrer">
                      Open report
                    </a>
                    <a className="secondary-button" href={bundleUrl}>
                      Download all
                    </a>
                  </div>
                </div>
              ) : null}

              <div className="detail-grid">
                <DetailItem label="Created" value={formatDate(activeJob.created_at)} />
                <DetailItem label="Progress" value={activeJob.status === "running" || activeJob.status === "queued" ? `${activeJob.progress_pct || 0}%` : `${activeJob.artifacts.length} files`} />
                <DetailItem label="Stage" value={activeJob.current_stage || activeJob.status} />
              </div>

              {activeJob.error ? <p className="error-text">{activeJob.error}</p> : null}

              <div className="artifact-grid">
                {activeJob.artifacts.length ? (
                  activeJob.artifacts.map((artifact) => (
                    <article className="artifact-card" key={artifact.name}>
                      <span>{artifactLabels[artifact.name] ?? artifact.name}</span>
                      <strong>{artifact.filename}</strong>
                      <div className="artifact-actions">
                        <a href={artifact.download_url} target="_blank" rel="noreferrer">Download</a>
                        {artifact.preview_url ? <a href={artifact.preview_url} target="_blank" rel="noreferrer">Preview</a> : null}
                      </div>
                    </article>
                  ))
                ) : (
                  <EmptyState title="Artifacts pending" body="Files appear here when the worker finishes the run." />
                )}
              </div>
            </>
          ) : (
            <EmptyState title="Select or submit a run" body="The report pack, status, and downloads will appear here." />
          )}
        </section>
      </main>
    </div>
  );
}

function AdminDashboard() {
  const [token, setToken] = useState(() => window.sessionStorage.getItem("ari_admin_token") || "");
  const [draftToken, setDraftToken] = useState(() => window.sessionStorage.getItem("ari_admin_token") || "");
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      return;
    }
    let cancelled = false;

    async function loadSummary() {
      setLoading(true);
      setError("");
      try {
        const response = await fetch("/api/analytics/summary", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Unable to load analytics.");
        }
        const payload = await response.json();
        if (!cancelled) {
          setSummary(payload);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError.message);
          setSummary(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadSummary();
    const timer = window.setInterval(loadSummary, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [token]);

  function submitToken(event) {
    event.preventDefault();
    const clean = draftToken.trim();
    if (!clean) {
      setError("Enter the analytics admin token.");
      return;
    }
    window.sessionStorage.setItem("ari_admin_token", clean);
    setToken(clean);
  }

  function clearToken() {
    window.sessionStorage.removeItem("ari_admin_token");
    setToken("");
    setDraftToken("");
    setSummary(null);
  }

  const adminMetrics = [
    { label: "Page views", value: summary?.page_views ?? 0, detail: "Tracked page loads" },
    { label: "Unique visitors", value: summary?.unique_visitors ?? 0, detail: "Browser sessions" },
    { label: "Unique IPs", value: summary?.unique_ips ?? 0, detail: "Server-observed IPs" },
    { label: "Task submissions", value: summary?.task_submissions ?? 0, detail: "Jobs created" },
  ];

  return (
    <div className="app-shell admin-shell">
      <header className="topbar">
        <a className="brand" href="/">
          <img src={logoUrl} alt="Amazon Review Insight" />
          <span>
            <strong>Analytics Admin</strong>
            <small>Private traffic and task metrics</small>
          </span>
        </a>
        <div className="system-strip">
          <a className="secondary-button compact-button" href="/">Workspace</a>
          {token ? <button className="secondary-button compact-button" onClick={clearToken} type="button">Lock</button> : null}
        </div>
      </header>

      <main className="admin-grid">
        <section className="panel admin-auth-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Private access</p>
              <h2>Analytics dashboard</h2>
            </div>
            {loading ? <span className="badge badge-running">Refreshing</span> : null}
          </div>
          <form className="admin-token-form" onSubmit={submitToken}>
            <label>
              <span>Admin token</span>
              <input
                autoComplete="off"
                onChange={(event) => setDraftToken(event.target.value)}
                placeholder="Paste ANALYTICS_ADMIN_TOKEN"
                type="password"
                value={draftToken}
              />
            </label>
            <button className="primary-button" type="submit">Unlock analytics</button>
          </form>
          {error ? <p className="error-text">{error}</p> : null}
          <p className="admin-note">
            This page is hidden from the public workflow. The API still requires the server-side token.
          </p>
        </section>

        <section className="metrics-grid admin-metrics" aria-label="Private analytics metrics">
          {adminMetrics.map((card) => (
            <article className="metric-card" key={card.label}>
              <span>{card.label}</span>
              <strong>{formatNumber(card.value)}</strong>
              <small>{card.detail}</small>
            </article>
          ))}
        </section>

        <section className="panel admin-events-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Recent events</p>
              <h2>Latest tracked activity</h2>
            </div>
          </div>
          <div className="event-table">
            {summary?.recent_events?.length ? (
              summary.recent_events.map((event, index) => (
                <article className="event-row" key={`${event.timestamp}-${index}`}>
                  <span className="event-type">{event.event_type}</span>
                  <span>{event.ip_address || "No IP"}</span>
                  <span>{event.path || "-"}</span>
                  <span>{event.job_id || "-"}</span>
                  <time>{formatDate(event.timestamp * 1000)}</time>
                </article>
              ))
            ) : (
              <EmptyState title="No visible events" body={token ? "Events will appear after visits or submissions." : "Unlock analytics to load recent events."} />
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

function ProgressBlock({ job }) {
  const showProgress = job.status === "running" || job.status === "queued";
  const progress = Math.max(Number(job.progress_pct || 0), showProgress ? 4 : 100);
  return (
    <div className="progress-block">
      <div className="progress-top">
        <strong>{job.status_detail || (showProgress ? "Analysis is queued or running." : "Analysis complete.")}</strong>
        <span>{showProgress ? `${job.progress_pct || 0}%` : "100%"}</span>
      </div>
      <div className="progress-bar">
        <span style={{ width: `${Math.min(progress, 100)}%` }} />
      </div>
      {job.chunk_index && job.chunk_total ? (
        <small>Chunk {job.chunk_index} of {job.chunk_total}</small>
      ) : null}
    </div>
  );
}

function StatusPill({ label, status, tone }) {
  return (
    <span className={`status-pill status-pill-${tone}`}>
      <small>{label}</small>
      <strong>{status}</strong>
    </span>
  );
}

function DetailItem({ label, value }) {
  return (
    <div className="detail-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyState({ title, body }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

function getTrackingIdentity() {
  const sessionKey = "ari_session_id";
  const visitKey = "ari_visit_id";
  let sessionId = window.localStorage.getItem(sessionKey);
  if (!sessionId) {
    sessionId = `s_${crypto.randomUUID()}`;
    window.localStorage.setItem(sessionKey, sessionId);
  }
  let visitId = window.sessionStorage.getItem(visitKey);
  if (!visitId) {
    visitId = `v_${crypto.randomUUID()}`;
    window.sessionStorage.setItem(visitKey, visitId);
  }
  return { sessionId, visitId };
}

function recordPageView({ sessionId, visitId }) {
  fetch("/api/analytics/event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_type: "page_view",
      session_id: sessionId,
      visit_id: visitId,
      path: window.location.pathname,
      metadata: { referrer: document.referrer || "" },
    }),
  }).catch(() => {});
}

function formatDate(value) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(Number(value || 0));
}

export default App;
