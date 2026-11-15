"""CLI.
  python -m radar run        scrape everything, update the DB, write the daily summary
  python -m radar run --jobs-only   careers sites only (no web search / RSS / NIM extraction)
  python -m radar export     write frontend/public/data/snapshot.json
  python -m radar serve      start the local API on http://localhost:8000
  python -m radar summary    print today's summary
"""

import argparse
import logging


def main():
    p = argparse.ArgumentParser(prog="radar")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--jobs-only", action="store_true")
    sub.add_parser("export")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8000)
    sm = sub.add_parser("summary")
    sm.add_argument("--rebuild", action="store_true", help="rewrite today's brief from the current DB")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "primp", "ddgs", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if a.cmd == "run":
        from . import export, pipeline
        pipeline.run(skip_web=a.jobs_only)
        print("snapshot:", export.write_snapshot())
    elif a.cmd == "export":
        from . import export
        print("snapshot:", export.write_snapshot())
    elif a.cmd == "serve":
        import uvicorn
        uvicorn.run("radar.api:app", host="127.0.0.1", port=a.port)
    elif a.cmd == "summary":
        from .db import connect, today
        if a.rebuild:
            from . import export, pipeline
            with connect() as conn:
                pipeline.write_summary(conn, today(), [])
            export.write_snapshot()
        with connect() as conn:
            row = conn.execute("SELECT markdown FROM summaries ORDER BY day DESC LIMIT 1").fetchone()
        print(row[0] if row else "No summary yet: run `python -m radar run` first.")


if __name__ == "__main__":
    main()
