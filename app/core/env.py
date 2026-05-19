from pathlib import Path

from dotenv import load_dotenv


_ENV_LOADED = False


def load_environment() -> None:
	global _ENV_LOADED

	if _ENV_LOADED:
		return

	backend_root = Path(__file__).resolve().parents[2]
	load_dotenv(backend_root / ".env")
	load_dotenv(backend_root / ".env.local", override=True)
	_ENV_LOADED = True