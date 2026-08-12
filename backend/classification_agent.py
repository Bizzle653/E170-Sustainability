from __future__ import annotations

import argparse
import json

from backend.services.classification_intelligence import (
    DeepSeekClassificationProvider,
    SustainabilityIntelligenceAgent,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autonomously research and update Green Canopy sustainability classifications.",
    )
    parser.add_argument("--tickers", help="Comma-separated tickers. Omit to process stale records by rank.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum securities per run (1-25).")
    parser.add_argument("--stale-days", type=int, default=30, help="Revisit classifications older than this many days.")
    parser.add_argument("--min-confidence", type=float, default=0.80, help="Automatic-change threshold (0-1).")
    parser.add_argument("--model", default="deepseek-chat", help="DeepSeek model identifier.")
    parser.add_argument("--apply", action="store_true", help="Persist classifications and publish change announcements.")
    args = parser.parse_args()

    tickers = [item.strip().upper() for item in args.tickers.split(",") if item.strip()] if args.tickers else None
    agent = SustainabilityIntelligenceAgent(
        decision_provider=DeepSeekClassificationProvider(model=args.model),
        min_confidence=max(0.5, min(args.min_confidence, 1.0)),
    )
    result = agent.run(
        tickers=tickers,
        stale_days=args.stale_days,
        limit=args.limit,
        apply=args.apply,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
