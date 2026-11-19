import argparse

from asteroid_tracker.config import load_config
from asteroid_tracker.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Normalize and summarize JPL close-approach data"
    )
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    result = run_pipeline(load_config(args.config))
    print(result)


if __name__ == "__main__":
    main()
