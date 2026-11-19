import argparse
from scientific_project.config import load_config
from scientific_project.data import download_data


def main():
    parser = argparse.ArgumentParser(description="Generate demo data or download a public dataset")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(download_data(load_config(args.config), force=args.force))


if __name__ == "__main__":
    main()
