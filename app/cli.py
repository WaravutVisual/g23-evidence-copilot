import argparse
import json

from app.verifier import verify_artifact


def main():
    parser = argparse.ArgumentParser(
        description="G23 Evidence Copilot deterministic verifier"
    )
    parser.add_argument("--file", required=True, help="Artifact file path")
    parser.add_argument(
        "--sha256",
        default=None,
        help="Trusted reference SHA-256"
    )
    args = parser.parse_args()

    result = verify_artifact(args.file, args.sha256)

    print(json.dumps({
        "state": result.state.value,
        "explanation": result.explanation,
        "scope_limit": (
            "A matching SHA-256 does not establish runtime correctness "
            "or production readiness."
        )
    }, indent=2))

    return 0 if result.state.value == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
