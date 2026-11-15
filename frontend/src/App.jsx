import { useEffect, useMemo, useState } from "react";
import { marked } from "marked";
import { loadData, runNow, setJob, setPracticed, health } from "./data.js";
import { Columns, HBars } from "./charts.jsx";

const TABS = ["Today", "Jobs", "Skills", "Questions", "Reading"];
const ROUNDS = ["Coding (DSA)", "GenAI depth", "LLM system design", "Evaluation", "Backend", "Behavioural", "General"];

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "");
const isToday = (s) => s && s.slice(0, 10) === new Date().toISOString().slice(0, 10);

function useStored(key, initial) {
  const [v, setV] = useState(() => {
    try {
      const s = localStorage.getItem(key);
      return s ? JSON.parse(s) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(v));
    } catch {
      /* storage blocked: keep in memory */
    }
  }, [key, v]);
  return [v, setV];
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useStored("radar.tab", "Today");
  const [running, setRunning] = useState(false);

  const refresh = () =>
    loadData()
      .then((d) => {
        setData(d);
        setRunning(!!d.run?.running);
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    refresh();
  }, []);

  // While a run is going, poll the backend and reload when it finishes.
  useEffect(() => {
    if (!running) return;
    const t = setInterval(async () => {
      try {
        const h = await health();
        if (!h.running) {
          setRunning(false);
          refresh();
        }
      } catch {
        setRunning(false);
      }
    }, 4000);
    return () => clearInterval(t);
  }, [running]);

  if (error) return <div className="shell"><p className="empty">{error}</p></div>;
  if (!data) return <div className="shell"><p className="empty">Loading…</p></div>;

  const lastRun = data.runs?.[0];
  return (
    <div className="shell">
      <header className="top">
        <div>
          <h1>GenAI Job Radar</h1>
          <p className="sub">
            {data.jobs.length} open roles · updated {fmtDate(lastRun?.finished_at || data.generated_at)}{" "}
            <span className={`badge ${data.live ? "live" : ""}`}>{data.live ? "Live · local backend" : "Snapshot · read-only"}</span>
          </p>
        </div>
        {data.live && (
          <button
            className="btn"
            disabled={running}
            onClick={() => runNow().then(() => setRunning(true)).catch((e) => alert(e.message))}
          >
            {running ? "Running… (a few minutes)" : "Run now"}
          </button>
        )}
      </header>
      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </nav>
      <main>
        {tab === "Today" && <Today data={data} />}
        {tab === "Jobs" && <Jobs data={data} onChange={refresh} />}
        {tab === "Skills" && <Skills data={data} />}
        {tab === "Questions" && <Questions data={data} onChange={refresh} />}
        {tab === "Reading" && <Reading data={data} />}
      </main>
      {lastRun?.errors?.length > 0 && (
        <details className="errors">
          <summary>{lastRun.errors.length} source(s) had problems on the last run</summary>
          <ul>{lastRun.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
        </details>
      )}
    </div>
  );
}

function Stat({ label, value, note }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {note && <span className="stat-note">{note}</span>}
    </div>
  );
}

function Today({ data }) {
  const [day, setDay] = useState(0);
  const s = data.summaries?.[day];
  const newToday = data.jobs.filter((j) => isToday(j.first_seen)).length;
  const top = data.jobs.filter((j) => j.fit_score >= 80).length;
  const practiced = data.questions.filter((q) => q.practiced).length;
  const perDay = (data.jobs_by_day || []).slice(-30).map((d) => ({ key: fmtDate(d.day), value: d.n }));
  return (
    <>
      <section className="stats">
        <Stat label="New today" value={newToday} />
        <Stat label="Strong fits (80+)" value={top} />
        <Stat label="Open roles" value={data.jobs.length} />
        <Stat
          label="Questions"
          value={data.questions.length}
          note={data.personal ? `${practiced} practised` : undefined}
        />
      </section>
      <section className="card">
        <div className="card-head">
          <h2>Daily brief</h2>
          {data.summaries?.length > 1 && (
            <select value={day} onChange={(e) => setDay(+e.target.value)} aria-label="Brief date">
              {data.summaries.map((x, i) => <option key={x.day} value={i}>{x.day}</option>)}
            </select>
          )}
        </div>
        {s ? (
          <>
            <article className="md" dangerouslySetInnerHTML={{ __html: marked.parse(s.markdown.replace(/^## .*\n/, "")) }} />
            <p className="muted small">
              {s.model === "template" ? "Rule-based brief. Add NVIDIA_API_KEY to backend/.env for an AI-written one." : `Written by ${s.model} (NVIDIA NIM).`}
            </p>
          </>
        ) : (
          <p className="empty">No brief yet.</p>
        )}
      </section>
      {perDay.length > 1 && (
        <section className="card">
          <h2>New roles found per day</h2>
          <Columns rows={perDay} unit=" roles" />
        </section>
      )}
    </>
  );
}

function Jobs({ data, onChange }) {
  const [q, setQ] = useStored("radar.q", "");
  const [company, setCompany] = useStored("radar.company", "All");
  const [minFit, setMinFit] = useStored("radar.minfit", 60);
  const [onlyNew, setOnlyNew] = useStored("radar.new", false);
  const [showLeads, setShowLeads] = useStored("radar.leads", true);
  const [open, setOpen] = useState(null);
  const companies = useMemo(() => ["All", ...new Set(data.jobs.map((j) => j.company))].sort(), [data]);
  const rows = data.jobs
    .filter((j) => company === "All" || j.company === company)
    .filter((j) => j.fit_score >= minFit)
    .filter((j) => showLeads || j.source !== "web")
    .filter((j) => !onlyNew || isToday(j.first_seen))
    .filter((j) => !q || `${j.title} ${j.company} ${j.location} ${j.keywords.join(" ")}`.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => b.fit_score - a.fit_score);

  return (
    <section className="card">
      <div className="filters">
        <input placeholder="Search title, skill, city…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={company} onChange={(e) => setCompany(e.target.value)} aria-label="Company">
          {companies.map((c) => <option key={c}>{c}</option>)}
        </select>
        <label>
          Fit ≥ {minFit}
          <input type="range" min="0" max="95" step="5" value={minFit} onChange={(e) => setMinFit(+e.target.value)} />
        </label>
        <label className="check"><input type="checkbox" checked={onlyNew} onChange={(e) => setOnlyNew(e.target.checked)} /> New today</label>
        <label className="check"><input type="checkbox" checked={showLeads} onChange={(e) => setShowLeads(e.target.checked)} /> Web leads</label>
      </div>
      <p className="muted small">{rows.length} roles</p>
      <div className="table-wrap">
        <table className="jobs">
          <thead>
            <tr>
              <th>Fit</th><th>Role</th><th>Company</th><th>Location</th><th>Yrs</th><th>Found</th>
              {data.personal && <th>Status</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((j) => (
              <JobRow key={j.id} j={j} data={data} open={open === j.id} toggle={() => setOpen(open === j.id ? null : j.id)} onChange={onChange} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function JobRow({ j, data, open, toggle, onChange }) {
  const cols = data.personal ? 7 : 6;
  return (
    <>
      <tr className={open ? "open" : ""}>
        <td><span className={`fit ${j.fit_score >= 80 ? "hi" : j.fit_score >= 65 ? "mid" : ""}`}>{j.fit_score}</span></td>
        <td>
          <button className="linkish" onClick={toggle} aria-expanded={open}>{j.title}</button>
          {j.source === "web" && <span className="tag">lead · verify</span>}
          {isToday(j.first_seen) && <span className="tag new">new</span>}
        </td>
        <td>{j.company}<div className="muted small">{j.tier}</div></td>
        <td className="small">{(j.location || "").split("|")[0]}</td>
        <td>{j.min_years ?? "–"}</td>
        <td className="small">{fmtDate(j.first_seen)}</td>
        {data.personal && (
          <td>
            <select
              value={j.status}
              disabled={!data.live}
              onChange={(e) => setJob(j.id, { status: e.target.value }).then(onChange)}
              aria-label="Status"
            >
              {data.statuses.map((s) => <option key={s}>{s}</option>)}
            </select>
          </td>
        )}
      </tr>
      {open && (
        <tr className="detail">
          <td colSpan={cols}>
            <div className="chips">{j.keywords.map((k) => <span key={k} className="chip">{k}</span>)}</div>
            <p className="excerpt">{j.excerpt}…</p>
            <a href={j.url} target="_blank" rel="noreferrer">Open posting ↗</a>
            {data.live && (
              <textarea
                placeholder="Notes (referral contact, recruiter, prep)…"
                defaultValue={j.notes}
                onBlur={(e) => e.target.value !== j.notes && setJob(j.id, { notes: e.target.value })}
              />
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function Skills({ data }) {
  const total = data.jobs.filter((j) => j.source !== "web").length || 1;
  const hist = data.keyword_history || [];
  const days = [...new Set(hist.map((h) => h.day))];
  const first = days[0];
  const rows = data.keywords.map((k) => {
    const then = hist.find((h) => h.keyword === k.keyword && h.day === first);
    const delta = then && days.length > 1 ? Math.round((k.share - then.share) * 100) : null;
    return { key: k.keyword, value: Math.round(k.share * 100), detail: `${k.count} of ${total} roles${delta ? `, ${delta > 0 ? "+" : ""}${delta} pts since ${fmtDate(first)}` : ""}` };
  });
  return (
    <section className="card">
      <h2>Share of open roles that mention each skill</h2>
      <p className="muted small">From {total} roles on company careers sites (web leads excluded). Put the top ones you have used on your resume, in these words.</p>
      <HBars rows={rows} format={(v) => `${v}%`} label="Skill demand" />
    </section>
  );
}

function Questions({ data, onChange }) {
  const [round, setRound] = useStored("radar.round", "All");
  const [hideDone, setHideDone] = useStored("radar.hidedone", false);
  const counts = Object.fromEntries(ROUNDS.map((r) => [r, data.questions.filter((q) => q.round === r).length]));
  const rows = data.questions
    .filter((q) => round === "All" || q.round === round)
    .filter((q) => !hideDone || !q.practiced);
  return (
    <section className="card">
      <div className="filters">
        <div className="seg">
          {["All", ...ROUNDS.filter((r) => counts[r])].map((r) => (
            <button key={r} className={round === r ? "on" : ""} onClick={() => setRound(r)}>
              {r} <span className="muted">{r === "All" ? data.questions.length : counts[r]}</span>
            </button>
          ))}
        </div>
        {data.personal && (
          <label className="check"><input type="checkbox" checked={hideDone} onChange={(e) => setHideDone(e.target.checked)} /> Hide practised</label>
        )}
      </div>
      <ul className="qlist">
        {rows.map((q) => (
          <li key={q.id} className={q.practiced ? "done" : ""}>
            {data.personal && (
              <input
                type="checkbox"
                checked={!!q.practiced}
                disabled={!data.live}
                onChange={(e) => setPracticed(q.id, e.target.checked).then(onChange)}
                aria-label="Practised"
              />
            )}
            <div>
              <p>{q.text}</p>
              <p className="muted small">
                {q.round}
                {q.company ? ` · ${q.company}` : ""} · {q.source_url ? <a href={q.source_url} target="_blank" rel="noreferrer">{q.source}</a> : q.source}
                {isToday(q.first_seen) && <span className="tag new">new</span>}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Reading({ data }) {
  return (
    <section className="card">
      <h2>From the shortlisted blogs</h2>
      <ul className="reading">
        {data.reading.map((a) => (
          <li key={a.url}>
            <a href={a.url} target="_blank" rel="noreferrer">{a.title}</a>
            <span className="muted small"> · {a.source} · {fmtDate(a.published || a.first_seen)}</span>
          </li>
        ))}
        {!data.reading.length && <li className="empty">Nothing yet. The next run reads the blog feeds.</li>}
      </ul>
    </section>
  );
}
