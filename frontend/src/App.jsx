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
  // Default to light; ThemeToggle lets the user switch.


  // Jump from a job to that company's questions.
  const askCompany = (co) => {
    try {
      localStorage.setItem("radar.qcompany", JSON.stringify(co));
      localStorage.setItem("radar.round", JSON.stringify("All"));
    } catch { /* storage blocked */ }
    setTab("Questions");
  };

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
  const tabCounts = { Jobs: data.jobs.length, Questions: data.questions.length, Reading: data.reading?.length };
  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="9" opacity="0.4" /><circle cx="12" cy="12" r="5" opacity="0.7" />
              <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
              <path d="M12 12 L19 7" />
            </svg>
          </span>
          <div>
            <h1>GenAI Job Radar</h1>
            <p className="sub">
              {data.jobs.length} open roles · updated {fmtDate(lastRun?.finished_at || data.generated_at)}
              <span className={`badge ${data.live ? "live" : ""}`}>{data.live ? "Live · local" : "Snapshot"}</span>
            </p>
          </div>
        </div>
        <div className="top-actions">
          {data.live && (
            <button
              className="btn"
              disabled={running}
              onClick={() => runNow().then(() => setRunning(true)).catch((e) => alert(e.message))}
            >
              {running ? "Running…" : "Run now"}
            </button>
          )}
          <ThemeToggle />
        </div>
      </header>
      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            {t}
            {tabCounts[t] > 0 && <span className="count">{tabCounts[t]}</span>}
          </button>
        ))}
      </nav>
      <main>
        {tab === "Today" && <Today data={data} />}
        {tab === "Jobs" && <Jobs data={data} onChange={refresh} onAskCompany={askCompany} />}
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

function ThemeToggle() {
  const [theme, setTheme] = useStored("radar.theme", "auto"); // auto | light | dark
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "auto") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
  }, [theme]);
  const next = { auto: "light", light: "dark", dark: "auto" };
  const icon = {
    auto: <><circle cx="12" cy="12" r="9" /><path d="M12 3v18" /></>,
    light: <><circle cx="12" cy="12" r="4.5" /><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" /></>,
    dark: <path d="M21 12.8A8 8 0 1 1 11.2 3 6.2 6.2 0 0 0 21 12.8Z" />,
  };
  return (
    <button className="icon-btn" title={`Theme: ${theme} (click for ${next[theme]})`} aria-label="Toggle theme" onClick={() => setTheme(next[theme])}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{icon[theme]}</svg>
    </button>
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

function WeekStrip({ data }) {
  const byDay = Object.fromEntries((data.jobs_by_day || []).map((d) => [String(d.day).slice(0, 10), d.n]));
  const todayKey = new Date().toISOString().slice(0, 10);
  const days = [...Array(7)].map((_, i) => {
    const dt = new Date();
    dt.setDate(dt.getDate() - (6 - i));
    const key = dt.toISOString().slice(0, 10);
    return {
      key,
      dow: dt.toLocaleDateString("en-IN", { weekday: "short" }),
      dom: dt.getDate(),
      n: byDay[key] || 0,
      today: key === todayKey,
    };
  });
  const max = Math.max(1, ...days.map((d) => d.n));
  return (
    <section className="card glass weekstrip">
      <div className="card-head">
        <h2>This week</h2>
        <span className="muted small">new roles found per day</span>
      </div>
      <div className="week">
        {days.map((d) => (
          <div key={d.key} className={`daycell ${d.today ? "today" : ""}`}>
            <span className="dow">{d.dow}</span>
            <span className="dring" style={{ "--p": `${Math.round((d.n / max) * 100)}%` }}>
              <span className="dnum">{d.n || "·"}</span>
            </span>
            <span className="dom">{d.dom}</span>
          </div>
        ))}
      </div>
    </section>
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
      <WeekStrip data={data} />
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

// Rough market estimate (India, GenAI / Applied AI), by company tier and seniority. Not from the posting.
const SALARY_BANDS = { Top: [40, 80], GCC: [28, 55], "Indian product": [22, 45], "Web lead": [18, 40], Other: [18, 40] };
function salaryEstimate(j) {
  const [lo, hi] = SALARY_BANDS[j.tier] || SALARY_BANDS.Other;
  const senior = (j.min_years ?? 0) >= 6 || /lead|staff|principal|senior|sr\.?\b/i.test(j.title || "");
  return senior ? `₹${Math.round(lo * 1.15)}–${Math.round(hi * 1.1)} LPA` : `₹${lo}–${hi} LPA`;
}

function Jobs({ data, onChange, onAskCompany }) {
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
    .filter((j) => showLeads || (j.source !== "web" && j.source !== "rss"))
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
              <JobRow key={j.id} j={j} data={data} open={open === j.id} toggle={() => setOpen(open === j.id ? null : j.id)} onChange={onChange} onAskCompany={onAskCompany} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function JobRow({ j, data, open, toggle, onChange, onAskCompany }) {
  const cols = data.personal ? 7 : 6;
  const qCount = data.questions.filter((x) => normCo(x.company) === normCo(j.company)).length;
  return (
    <>
      <tr className={open ? "open" : ""}>
        <td><span className={`fit ${j.fit_score >= 80 ? "hi" : j.fit_score >= 65 ? "mid" : ""}`}>{j.fit_score}</span></td>
        <td>
          <button className="linkish" onClick={toggle} aria-expanded={open}>{j.title}</button>
          {(j.source === "web" || j.source === "rss") && <span className="tag">lead · verify</span>}
          {isToday(j.first_seen) && <span className="tag new">new</span>}
        </td>
        <td>
          <span className="co-cell">
            <CompanyLogo name={j.company} size={22} />
            <span>{j.company}<div className="muted small">{j.tier}</div></span>
          </span>
        </td>
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
            <div className="job-stats">
              <div className="job-stat">
                <span className="job-stat-label">Est. salary <span className="muted" title="Rough market estimate from company tier and seniority — not from the posting.">ⓘ</span></span>
                <span className="job-stat-value">{salaryEstimate(j)}</span>
              </div>
              <div className="job-stat">
                <span className="job-stat-label">Experience</span>
                <span className="job-stat-value">{j.min_years != null ? `${j.min_years}+ yrs` : "—"}</span>
              </div>
              <div className="job-stat">
                <span className="job-stat-label">Fit</span>
                <span className="job-stat-value">{j.fit_score}/100</span>
              </div>
            </div>

            <p className="detail-h">Topics to prepare</p>
            {j.keywords.length ? (
              <div className="chips">{j.keywords.map((k) => <span key={k} className="chip">{k}</span>)}</div>
            ) : (
              <p className="muted small">No topics parsed from this posting — open it to read the full JD.</p>
            )}

            <p className="excerpt">{j.excerpt}…</p>
            <div className="detail-actions">
              <a className="btn-ghost" href={j.url} target="_blank" rel="noreferrer">Open posting ↗</a>
              {qCount > 0 && onAskCompany && (
                <button className="btn-ghost" onClick={() => onAskCompany(j.company)}>
                  {qCount} {j.company} interview question{qCount === 1 ? "" : "s"} →
                </button>
              )}
            </div>
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

const UNKNOWN_CO = "Other / general";

// Stable per-company colour for the avatar, from the company name.
const CO_COLORS = ["#2f6df0", "#8e5cff", "#0a9d6e", "#d9534f", "#d98b2b", "#5a6acf", "#c0398e", "#1f9bb0"];
function coColor(name) {
  if (name === UNKNOWN_CO) return "#80838f";
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return CO_COLORS[h % CO_COLORS.length];
}
function coInitials(name) {
  if (name === UNKNOWN_CO) return "··";
  const w = name.replace(/[^A-Za-z0-9 ]/g, "").split(/\s+/).filter(Boolean);
  return ((w[0]?.[0] || "") + (w[1]?.[0] || w[0]?.[1] || "")).toUpperCase();
}

// Known company → domain, for logos. Unknown names fall back to "<firstword>.com".
const CO_DOMAINS = {
  Apple: "apple.com", Google: "google.com", Microsoft: "microsoft.com", Amazon: "amazon.com",
  Nvidia: "nvidia.com", Atlassian: "atlassian.com", Salesforce: "salesforce.com", Adobe: "adobe.com",
  "Walmart Global Tech": "walmart.com", Walmart: "walmart.com", Uber: "uber.com", Flipkart: "flipkart.com",
  Databricks: "databricks.com", ServiceNow: "servicenow.com", Rubrik: "rubrik.com", Target: "target.com",
  Meesho: "meesho.com", Groww: "groww.in", CRED: "cred.club", Swiggy: "swiggy.com", PhonePe: "phonepe.com",
  Razorpay: "razorpay.com", "Sarvam AI": "sarvam.ai", Intuit: "intuit.com", "Goldman Sachs": "goldmansachs.com",
  "JPMorgan Chase": "jpmorganchase.com", "American Express": "americanexpress.com", Uber_: "uber.com",
};
function coDomain(name) {
  if (!name || name === UNKNOWN_CO) return null;
  if (CO_DOMAINS[name]) return CO_DOMAINS[name];
  const first = name.split(/\s+/)[0].toLowerCase().replace(/[^a-z0-9]/g, "");
  return first ? `${first}.com` : null;
}

function CompanyLogo({ name, size = 24 }) {
  const [failed, setFailed] = useState(false);
  const domain = coDomain(name);
  const style = { width: size, height: size, borderRadius: size * 0.29, fontSize: size * 0.42 };
  if (!domain || failed) {
    return <span className="co-avatar" style={{ ...style, background: coColor(name) }}>{coInitials(name)}</span>;
  }
  return (
    <img
      className="co-logo"
      style={style}
      src={`https://icons.duckduckgo.com/ip3/${domain}.ico`}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

// Fold model-tagged variants into one clean company name.
const CO_ALIASES = { NVIDIA: "Nvidia", "Uber Drivers": "Uber", "Google LLC": "Google", "Amazon Web Services": "Amazon", AWS: "Amazon" };
function normCo(name) {
  if (!name) return UNKNOWN_CO;
  const n = String(name).trim();
  return CO_ALIASES[n] || n;
}

function CompanyCard({ name, items, data, onChange }) {
  const real = name !== UNKNOWN_CO;
  return (
    <article className="qcard">
      <header className="qcard-head">
        <CompanyLogo name={name} size={42} />
        <div className="qcard-title">
          <h3>{name}</h3>
          <p className="muted small">{real ? `Asked in a ${name} AI / ML engineer interview` : "General & uncredited questions"}</p>
        </div>
        <span className="qcard-count" title={`${items.length} questions`}>{items.length}</span>
      </header>
      <ul className="qfeed">
        {items.map((q) => (
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
            <div className="qbody">
              <p className="qtext">{q.text}</p>
              <div className="qmeta">
                <span className="round-tag">{q.round}</span>
                <span className="dot">·</span>
                {q.source_url ? <a href={q.source_url} target="_blank" rel="noreferrer">{q.source} ↗</a> : <span className="muted">{q.source}</span>}
                {isToday(q.first_seen) && <span className="tag new">new</span>}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </article>
  );
}

function Questions({ data, onChange }) {
  const [round, setRound] = useStored("radar.round", "All");
  const [company, setCompany] = useStored("radar.qcompany", "All");
  const [hideDone, setHideDone] = useStored("radar.hidedone", false);

  const counts = Object.fromEntries(ROUNDS.map((r) => [r, data.questions.filter((q) => q.round === r).length]));
  const coOf = (q) => normCo(q.company);
  // Companies present, most-asked first, with "Other / general" last.
  const companies = useMemo(() => {
    const c = {};
    data.questions.forEach((q) => { c[coOf(q)] = (c[coOf(q)] || 0) + 1; });
    return Object.entries(c).sort((a, b) =>
      (a[0] === UNKNOWN_CO) - (b[0] === UNKNOWN_CO) || b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [data]);
  const namedCount = companies.filter(([n]) => n !== UNKNOWN_CO).length;

  // Self-heal stale localStorage: if a saved filter no longer matches the data, treat it as "All".
  const activeRound = round === "All" || counts[round] ? round : "All";
  const activeCompany = company === "All" || companies.some(([n]) => n === company) ? company : "All";

  const rows = data.questions
    .filter((q) => activeRound === "All" || q.round === activeRound)
    .filter((q) => activeCompany === "All" || coOf(q) === activeCompany)
    .filter((q) => !hideDone || !q.practiced);

  const groups = useMemo(() => {
    const m = new Map();
    rows.forEach((q) => { const k = coOf(q); if (!m.has(k)) m.set(k, []); m.get(k).push(q); });
    return [...m.entries()].sort((a, b) =>
      (a[0] === UNKNOWN_CO) - (b[0] === UNKNOWN_CO) || b[1].length - a[1].length || a[0].localeCompare(b[0]));
  }, [rows]);

  return (
    <>
      <div className="card toolbar">
        <div className="seg">
          {["All", ...ROUNDS.filter((r) => counts[r])].map((r) => (
            <button key={r} className={activeRound === r ? "on" : ""} onClick={() => setRound(r)}>
              {r} <span className="muted">{r === "All" ? data.questions.length : counts[r]}</span>
            </button>
          ))}
        </div>
        <div className="toolbar-right">
          <select value={activeCompany} onChange={(e) => setCompany(e.target.value)} aria-label="Company">
            <option value="All">All companies ({namedCount})</option>
            {companies.map(([name, n]) => <option key={name} value={name}>{name} ({n})</option>)}
          </select>
          {data.personal && (
            <label className="check"><input type="checkbox" checked={hideDone} onChange={(e) => setHideDone(e.target.checked)} /> Hide practised</label>
          )}
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="empty">No questions yet for this filter.</p>
      ) : (
        <div className="feed">
          {groups.map(([name, items]) => (
            <CompanyCard key={name} name={name} items={items} data={data} onChange={onChange} />
          ))}
        </div>
      )}
    </>
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
