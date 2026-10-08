import subprocess
import sys


def run_command(
        command: list[str],
        description: str,
) -> None:
    """
    Run one validation command and stop immediately if it fails.
    """

    print()
    print("=" * 70)
    print(description)
    print("=" * 70)

    result = subprocess.run(
        command,
        check=False,
    )

    if result.returncode != 0:
        print()
        print(
            f"FAILED: {description}"
        )
        sys.exit(result.returncode)


def main() -> None:
    """
    Run the Market Lens project validation pipeline.
    """

    python_executable = sys.executable

    run_command(
        [
            python_executable,
            "-m",
            "pytest",
            "-q",
        ],
        "Running test suite",
    )

    print()
    print("=" * 70)
    print("MARKET LENS VALIDATION PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()