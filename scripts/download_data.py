import argparse

from asteroid_tracker.config import load_config
from asteroid_tracker.jpl_cad import download_close_approaches


def main():
    parser = argparse.ArgumentParser(
        description="Download NASA/JPL NEO close-approach data"
    )
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    target = download_close_approaches(
        load_config(args.config),
        force=args.force,
    )
    print(target)


if __name__ == "__main__":
    main()
