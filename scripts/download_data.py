import argparse

from requests import RequestException

from asteroid_tracker.config import load_config
from asteroid_tracker.jpl_cad import acquire_close_approaches


def main():
    parser = argparse.ArgumentParser(
        description="Download NASA/JPL NEO close-approach data"
    )
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        result = acquire_close_approaches(load_config(args.config), force=args.force)
    except RequestException as error:
        # Request exceptions can include a URL with credentials.
        parser.exit(1, f"CAD request failed ({type(error).__name__}).\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"CAD download failed: {error}\n")
    print(result["path"])
    print(f"{result['download_status']} | acquisition metadata: {result['acquisition_metadata_status']}")


if __name__ == "__main__":
    main()
