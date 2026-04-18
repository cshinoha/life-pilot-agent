"""Non-interactive bootstrap helper for LLM runtime auth."""

from life_pilot.services.factory import get_runner


def main() -> int:
    """Exit 0 when the runtime is ready, otherwise print instructions."""
    runtime_status = get_runner().get_runtime_status(trigger_bootstrap=True)
    if runtime_status["ready"]:
        return 0

    print(runtime_status["details"] or runtime_status["summary"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
