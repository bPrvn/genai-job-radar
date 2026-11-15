import { useState } from "react";

// Single-series charts: one hue (--series-1), no legend (the title names the series),
// hover tooltip on every mark, values in text ink.

export function HBars({ rows, format = (v) => v, label = "value" }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="hbars" role="table" aria-label={label}>
      {rows.map((r, i) => (
        <div
          key={r.key}
          className={`hbar-row ${hover === i ? "is-hover" : ""}`}
          role="row"
          onMouseEnter={() => setHover(i)}
          onMouseLeave={() => setHover(null)}
        >
          <span className="hbar-label" role="cell">{r.key}</span>
          <span className="hbar-track" role="cell">
            <span className="hbar-fill" style={{ width: `${(r.value / max) * 100}%` }} />
            {hover === i && (
              <span className="tip" style={{ left: `${Math.min(80, (r.value / max) * 100)}%` }}>
                <b>{r.key}</b>
                <br />
                {format(r.value)} {r.detail ? `· ${r.detail}` : ""}
              </span>
            )}
          </span>
          <span className="hbar-value" role="cell">{format(r.value)}</span>
        </div>
      ))}
    </div>
  );
}

export function Columns({ rows, height = 120, unit = "" }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(1, ...rows.map((r) => r.value));
  const w = 100 / Math.max(rows.length, 1);
  return (
    <div className="columns" style={{ height }}>
      <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" width="100%" height={height} aria-hidden="true">
        <line x1="0" x2="100" y1={height - 0.5} y2={height - 0.5} className="axis" vectorEffect="non-scaling-stroke" />
        {rows.map((r, i) => {
          const h = Math.max(2, (r.value / max) * (height - 18));
          return (
            <rect
              key={r.key}
              x={i * w + w * 0.15}
              width={w * 0.7}
              y={height - h}
              height={h}
              rx="0.8"
              className={`col ${hover === i ? "is-hover" : ""}`}
            />
          );
        })}
      </svg>
      <div className="col-hits">
        {rows.map((r, i) => (
          <span
            key={r.key}
            style={{ width: `${w}%` }}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            tabIndex={0}
            onFocus={() => setHover(i)}
            onBlur={() => setHover(null)}
            aria-label={`${r.key}: ${r.value}${unit}`}
          >
            {hover === i && (
              <span className="tip tip-col">
                <b>{r.key}</b>
                <br />
                {r.value}
                {unit}
              </span>
            )}
          </span>
        ))}
      </div>
      <div className="col-axis">
        <span>{rows[0]?.key}</span>
        <span>{rows[rows.length - 1]?.key}</span>
      </div>
    </div>
  );
}
