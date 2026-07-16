from __future__ import annotations

from app.core.version import PLATFORM_NAME, version_metadata


def main() -> None:
    metadata = version_metadata()
    print(PLATFORM_NAME)
    print(f"Version {metadata['version']}")
    print(f"Environment {str(metadata['environment']).title()}")
    print(f"Workflow Engine {metadata['workflow_engine']}")
    if metadata.get("build"):
        print(f"Build {metadata['build']}")


if __name__ == "__main__":
    main()
