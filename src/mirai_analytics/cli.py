"""Command-line interface for Mirai Analytics."""

from __future__ import annotations

import argparse

from mirai_analytics.data.synthetic import generate_dataset


def _cmd_generate(args: argparse.Namespace) -> None:
    """Generate a synthetic hospital dataset and write CSVs."""
    counts = generate_dataset(
        n_patients=args.patients,
        seed=args.seed,
        output_dir=args.out,
    )
    print(f"Generated synthetic dataset in '{args.out}':")
    for key, value in counts.items():
        print(f"  {key}: {value}")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="mirai",
        description="Mirai Analytics command-line tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser(
        "generate",
        help="Generate a synthetic Kenyan hospital dataset (patients, encounters, claims).",
    )
    gen.add_argument(
        "-n",
        "--patients",
        type=int,
        default=1000,
        help="Number of patients to generate (default: 1000).",
    )
    gen.add_argument(
        "-s", "--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)."
    )
    gen.add_argument(
        "-o",
        "--out",
        default="data/raw",
        help="Output directory for the CSV files (default: data/raw).",
    )
    gen.set_defaults(func=_cmd_generate)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point: parse arguments and dispatch to the chosen command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
