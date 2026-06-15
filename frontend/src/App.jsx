import { useEffect, useRef, useState } from "react";
import logoUrl from "./assets/logo.png";

const POLL_INTERVAL_IDLE = 5000;
const POLL_INTERVAL_RUNNING = 1500;

const statCards = [
  { label: "Outputs", value: "4", detail: "Report, insight JSON, cleaned XLSX, summary" },
  { label: "Speed", value: "1 flow", detail: "Upload once and wait for the finished analysis pack" },
  { label: "Formats", value: "CSV/XLSX", detail: "SellerSprite and standard Amazon exports" },
];

const stageMap = {
  queued: "Queued",
  running: "Analyzing reviews...",
  completed: "Completed",
  failed: "Failed",
};

function App() {
  const [health, setHealth] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [activeJobId, setActiveJobId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const reviewInputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    async function bootstrap() {
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
        if (!activeJobId && jobsData[0]) {
          setActiveJobId(jobsData[0].job_id);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message);
        }
      }
    }

    function schedule() {
      const anyRunning = jobs.some((job) => job.status === "running" || job.status === "queued");
      timer = window.setTimeout(async () => {
        await bootstrap();
        if (!cancelled) {
          schedule();
        }
      }, anyRunning ? POLL_INTERVAL_RUNNING : POLL_INTERVAL_IDLE);
    }

    bootstrap();
    schedule();
    return () => {
      cancelled = true;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [activeJobId, jobs]);

  const activeJob = jobs.find((job) => job.job_id === activeJobId) ?? jobs[0] ?? null;
  const reportArtifact = activeJob?.artifacts.find((artifact) => artifact.name === "report_html") ?? null;
  const bundleUrl = activeJob ? `/api/jobs/${activeJob.job_id}/download` : "";

  async function submitJob(event) {
    event.preventDefault();
    setError("");
    const form = event.currentTarget;
    const reviewFile = reviewInputRef.current?.files?.[0];
    if (!reviewFile) {
      setError("Please choose a review file before starting analysis.");
      return;
    }
    const formData = new FormData();
    formData.append("review_file", reviewFile);
    setSubmitting(true);
    try {
      const response = await fetch("/api/jobs", { method: "POST", body: formData });
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || "Unable to create job");
      }
      const job = await response.json();
      setActiveJobId(job.job_id);
      setJobs((current) => [job, ...current]);
      form.reset();
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="background-orb background-orb-left" />
      <div className="background-orb background-orb-right" />

      <header className="hero">
        <div className="hero-copy">
          <div className="brand-mark">
            <img src={logoUrl} alt="Amazon Review Insight" />
            <span>Amazon Review Insight</span>
          </div>
          <span className="eyebrow">Review Intelligence Console</span>
          <h1>Upload reviews. Get a decision-ready insight report.</h1>
          <p className="hero-text">
            Built for speed, not setup. Add an Amazon review export and the system returns cleaned
            data, structured insight, and a polished report.
          </p>
          <div className="hero-actions">
            <a href="#upload" className="primary-button">
              Start Analysis
            </a>
            <a href="#results" className="ghost-button">
              View Results
            </a>
          </div>
        </div>

        <div className="hero-panel">
          <div className="signal-card">
            <div className="signal-head">
              <span className="signal-label">Analysis status</span>
              <span className={`badge ${health ? "badge-good" : ""}`}>{health ? "Live" : "Loading"}</span>
            </div>
            <div className="signal-summary">
              <div className="signal-feature">
                <strong>Upload once</strong>
                <span>The system handles preprocessing, insight generation, and report packaging.</span>
              </div>
              <div className="signal-feature">
                <strong>Get a full pack</strong>
                <span>Receive a polished HTML report plus the structured files behind it.</span>
              </div>
              <div className="signal-feature">
                <strong>Track progress</strong>
                <span>Every run stays visible so you can reopen outputs without rerunning analysis.</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="stats-grid">
        {statCards.map((card) => (
          <article className="glass-card stat-card" key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
            <p>{card.detail}</p>
          </article>
        ))}
      </section>

      <main className="content-grid">
        <section className="glass-card upload-card" id="upload">
          <div className="section-heading">
            <span>Upload</span>
            <h2>Start with one file. Everything else should feel automatic.</h2>
          </div>
          <form className="upload-form" onSubmit={submitJob}>
            <label className="upload-field">
              <span>Review export</span>
              <input ref={reviewInputRef} type="file" accept=".csv,.xlsx,.xls" />
            </label>
            <button className="primary-button" disabled={submitting} type="submit">
              {submitting ? "Submitting..." : "Start analysis"}
            </button>
            {error ? <p className="error-text">{error}</p> : null}
          </form>
        </section>

        <section className="glass-card jobs-card">
          <div className="section-heading">
            <span>History</span>
            <h2>Recent analyses</h2>
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
                  <div>
                    <strong>{job.input_filename}</strong>
                    <span>{job.job_id}</span>
                  </div>
                  <span className={`badge badge-${job.status}`}>{stageMap[job.status] ?? job.status}</span>
                </button>
              ))
            ) : (
              <p className="empty-text">No jobs yet. Upload a review file to create the first run.</p>
            )}
          </div>
        </section>

        <section className="glass-card detail-card" id="results">
          <div className="section-heading">
            <span>Results</span>
            <h2>{activeJob ? activeJob.input_filename : "Waiting for first job"}</h2>
          </div>
          {activeJob ? (
            <>
              {activeJob.status === "running" ? (
                <div className="result-processing">
                  <div className="processing-head">
                    <div className="processing-bar">
                      <span style={{ width: `${Math.max(activeJob.progress_pct || 12, 12)}%` }} />
                    </div>
                    <span className="processing-pct">{activeJob.progress_pct || 0}%</span>
                    {activeJob.chunk_index && activeJob.chunk_total ? (
                      <span className="chunk-pill">
                        Chunk {activeJob.chunk_index} / {activeJob.chunk_total}
                      </span>
                    ) : null}
                  </div>
                  <div className="processing-copy">
                    <strong>Analysis in progress</strong>
                    <p>{activeJob.status_detail || "The system is cleaning reviews, generating insight, and preparing the final report."}</p>
                  </div>
                </div>
              ) : null}

              {reportArtifact?.preview_url ? (
                <div className="result-hero">
                  <div>
                    <span className="result-hero-label">Ready to view</span>
                    <h3>Open the finished report first.</h3>
                    <p>
                      The HTML report is the fastest way to review the findings before downloading the full output pack.
                    </p>
                  </div>
                  <a
                    className="primary-button"
                    href={reportArtifact.preview_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open Report
                  </a>
                  <a className="ghost-button" href={bundleUrl}>
                    Download All
                  </a>
                </div>
              ) : null}

              <div className="detail-metrics">
                <div>
                  <span>Status</span>
                  <strong>{stageMap[activeJob.status] ?? activeJob.status}</strong>
                </div>
                <div>
                  <span>Created</span>
                  <strong>{formatDate(activeJob.created_at)}</strong>
                </div>
                <div>
                  <span>Progress</span>
                  <strong>{activeJob.status === "running" ? `${activeJob.progress_pct || 0}%` : activeJob.artifacts.length}</strong>
                </div>
              </div>

              {activeJob.error ? <p className="error-text">{activeJob.error}</p> : null}

              <p className="detail-note">
                {activeJob.status === "running"
                  ? "The files will appear here as soon as this analysis completes."
                  : "Download the full output pack whenever you need the source files behind the report."}
              </p>

              <div className="artifact-grid">
                {activeJob.artifacts.length ? (
                  activeJob.artifacts.map((artifact) => (
                    <article className="artifact-card" key={artifact.name}>
                      <span>{artifact.name}</span>
                      <strong>{artifact.filename}</strong>
                      <div className="artifact-actions">
                        <a href={artifact.download_url} target="_blank" rel="noreferrer">
                          Download
                        </a>
                        {artifact.preview_url ? (
                          <a href={artifact.preview_url} target="_blank" rel="noreferrer">
                            Preview
                          </a>
                        ) : null}
                      </div>
                    </article>
                  ))
                ) : (
                  <p className="empty-text">Artifacts will appear here after the job completes.</p>
                )}
              </div>
            </>
          ) : (
            <p className="empty-text">Select a job to inspect pipeline output.</p>
          )}
        </section>
      </main>
    </div>
  );
}

function formatDate(value) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default App;
