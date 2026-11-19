import argparse
from scientific_project.config import load_config
from scientific_project.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Summarize the input CSV")
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    print(run_pipeline(load_config(args.config)))


if __name__ == "__main__":
    main()
