#!/usr/bin/env python3
"""FastUp GAS (GEO Audit System) Benchmark Runner.

Measures AI search engine visibility across ChatGPT (Web Search), Google (AI Overviews),
and Yandex (Alice/Neuro) according to the FastUp GAS v1.4.4 open standard.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure repository root and scripts/ are on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Also add projects/fastup-gas to sys.path so we can import fastup_gas directly
_GAS_PKG_DIR = _REPO_ROOT / "projects" / "fastup-gas"
if str(_GAS_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_GAS_PKG_DIR))

from env_load import load_env
from fastup_gas.core import FastUpGASRunner, _safe_log


def validate_matrix(queries_data: dict, file_path: Path) -> None:
    """Pre-flight validation of the queries matrix schema to prevent invalid runs."""
    missing = []
    for section in ["non_branded", "brand", "person"]:
        items = queries_data.get(section, [])
        if not items or len(items) == 0:
            missing.append(section)

    if missing:
        print(f"\n[FATAL] Query matrix in '{file_path}' is INVALID!", file=sys.stderr)
        print(f"Missing or empty required sections: {', '.join(missing)}", file=sys.stderr)
        print("To calculate valid GAS metrics (NVI, CBK, PKS, PCL, SCG), all 3 sections are mandatory.", file=sys.stderr)
        sys.exit(1)


def validate_environment(engine: str) -> None:
    """Validate that required API keys exist in the environment."""
    load_env()
    missing_keys = []

    if engine in ("chatgpt", "all"):
        if not os.environ.get("PROXYAPI_KEY"):
            missing_keys.append("PROXYAPI_KEY (for ChatGPT web search via ProxyAPI)")

    if engine in ("google", "yandex", "all"):
        if not os.environ.get("XMLRIVER_USER") or not os.environ.get("XMLRIVER_KEY"):
            missing_keys.append("XMLRIVER_USER / XMLRIVER_KEY (for Google AI Overviews and Yandex Alice)")

    if missing_keys:
        print("\n[FATAL] Missing required environment variables in .env:", file=sys.stderr)
        for k in missing_keys:
            print(f"  - {k}", file=sys.stderr)
        sys.exit(1)


def run_single_engine(
    runner: FastUpGASRunner,
    engine_name: str,
    queries_data: dict,
    assume_organic: bool,
    out_dir: Path,
    target_domain: str,
    target_brand: str,
    target_person: str,
) -> dict:
    """Run audit for a single engine with live real-time progress logging."""
    print(f"\n{'='*70}", flush=True)
    print(f"[*] Starting FastUp GAS Audit for: {engine_name.upper()}", flush=True)
    print(f"{'='*70}", flush=True)

    # Engine query wrapper
    if engine_name == "chatgpt":
        raw_query_func = lambda q: runner.query_proxyapi_chatgpt(q)
    elif engine_name == "google":
        raw_query_func = lambda q: runner.query_xmlriver(q, engine="google", ai=True)
    elif engine_name == "yandex":
        raw_query_func = lambda q: runner.query_xmlriver(q, engine="yandex", ai=True)
    elif engine_name == "mock":
        raw_query_func = lambda q: {
            "text": f"Компания {target_brand} ({target_domain}) — digital агентство в Беларуси. Основатель {target_person}.",
            "sources": [f"https://{target_domain}/"]
        }
    else:
        raise ValueError(f"Unknown engine: {engine_name}")

    total_queries = (
        len(queries_data.get("non_branded", []))
        + len(queries_data.get("brand", []))
        + len(queries_data.get("person", []))
    )
    current_idx = [0]

    def logging_query_wrapper(prompt: str) -> dict:
        current_idx[0] += 1
        t0 = time.time()
        res = raw_query_func(prompt)
        dt = time.time() - t0

        text = res.get("text", "")
        sources = res.get("sources", [])
        src_preview = sources[0] if sources else "—"
        if len(src_preview) > 50:
            src_preview = src_preview[:47] + "..."

        snippet = text.replace("\n", " ").strip()
        if len(snippet) > 60:
            snippet = snippet[:57] + "..."

        print(
            f"[{engine_name.title()} {current_idx[0]}/{total_queries}] "
            f"\"{prompt[:40]}\" -> {len(sources)} sources [{src_preview}] ({dt:.1f}s)",
            flush=True
        )
        return res

    results = runner.run_audit(
        queries_data=queries_data,
        engine_func=logging_query_wrapper,
        assume_organic_if_missing=assume_organic,
    )
    results["engine"] = engine_name

    # Generate Markdown report and JSON
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_md = runner.generate_markdown_report(results)

    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{date_str}-gas-{engine_name}.md"
    json_path = out_dir / f"{date_str}-gas-{engine_name}-data.json"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    m = results["metrics"]
    print(f"\n[OK] {engine_name.upper()} Audit Complete!", flush=True)
    print(f"Report: {md_path}", flush=True)
    print(f"Data:   {json_path}", flush=True)
    print(
        f"Scorecard: NVI={m['NVI']}% | CBK={m['CBK']}% | PKS={m['PKS']}% | "
        f"PCL={m['PCL']}/6 | SCG={m['SCG']}%",
        flush=True
    )
    return results


def main():
    parser = argparse.ArgumentParser(
        prog="geo_check",
        description="FastUp GAS (GEO Audit System) Benchmark Runner v1.4.4"
    )
    parser.add_argument(
        "--engine",
        default="all",
        choices=["all", "chatgpt", "google", "yandex", "mock"],
        help="Search engine surface to measure (default: all)"
    )
    parser.add_argument(
        "--queries",
        default=str(_REPO_ROOT / "geo" / "index" / "fastup-self" / "queries-2026-09-20.json"),
        help="Path to queries matrix JSON"
    )
    parser.add_argument("--target-domain", default="fastup.by", help="Target domain (default: fastup.by)")
    parser.add_argument("--target-brand", default="FastUp", help="Target brand name (default: FastUp)")
    parser.add_argument("--target-person", default="Егор Воронов", help="Target expert name (default: Егор Воронов)")
    parser.add_argument(
        "--out-dir",
        default=str(_REPO_ROOT / "geo"),
        help="Directory to save output reports and JSON datasets"
    )
    parser.add_argument(
        "--assume-organic",
        action="store_true",
        help="Assume all non-branded queries are in Top-10 if not explicitly specified in JSON"
    )

    args = parser.parse_args()

    queries_path = Path(args.queries)
    if not queries_path.exists():
        sys.exit(f"[ERROR] Queries file not found: {queries_path}")

    try:
        with open(queries_path, "r", encoding="utf-8") as f:
            queries_data = json.load(f)
    except Exception as e:
        sys.exit(f"[ERROR] Failed to read queries JSON: {e}")

    # 1. Pre-flight validation
    validate_matrix(queries_data, queries_path)
    if args.engine != "mock":
        validate_environment(args.engine)

    # 2. Initialize Runner
    runner = FastUpGASRunner(
        target_domain=args.target_domain,
        target_brand=args.target_brand,
        target_person=args.target_person,
        xmlriver_user=os.environ.get("XMLRIVER_USER"),
        xmlriver_key=os.environ.get("XMLRIVER_KEY"),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
    )

    engines_to_run = ["chatgpt", "google", "yandex"] if args.engine == "all" else [args.engine]
    out_dir = Path(args.out_dir)

    all_results = {}
    for eng in engines_to_run:
        all_results[eng] = run_single_engine(
            runner=runner,
            engine_name=eng,
            queries_data=queries_data,
            assume_organic=args.assume_organic,
            out_dir=out_dir,
            target_domain=args.target_domain,
            target_brand=args.target_brand,
            target_person=args.target_person,
        )

    if len(engines_to_run) > 1:
        date_str = datetime.now().strftime("%Y-%m-%d")
        print(f"\n{'='*70}", flush=True)
        print("CONSOLIDATED 3-ENGINE SCORECARD", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"{'Metric':<10} | {'ChatGPT':<10} | {'Google':<10} | {'Yandex':<10} | {'Average':<10}")
        print("-" * 60)
        for m_key in ["NVI", "CBK", "PKS", "PCL", "SCG"]:
            val_gpt = all_results.get("chatgpt", {}).get("metrics", {}).get(m_key, "—")
            val_goog = all_results.get("google", {}).get("metrics", {}).get(m_key, "—")
            val_yan = all_results.get("yandex", {}).get("metrics", {}).get(m_key, "—")
            vals = [v for v in [val_gpt, val_goog, val_yan] if isinstance(v, (int, float))]
            avg = round(sum(vals) / len(vals), 1) if vals else "—"
            print(f"{m_key:<10} | {str(val_gpt):<10} | {str(val_goog):<10} | {str(val_yan):<10} | {str(avg):<10}")
        print(f"{'='*70}", flush=True)


if __name__ == "__main__":
    main()
