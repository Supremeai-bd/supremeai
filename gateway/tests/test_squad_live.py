import os
from pathlib import Path
from service.pool import squad

def test_discovery():
    old_env = dict(os.environ)
    try:
        env_file = Path(r"f:\supremeai\.env")
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip("'\"")

        squad.reload_squad()
        stats = squad.stats()
        print("========================================")
        print(" SQUAD DYNAMIC KEY DISCOVERY REPORT")
        print("========================================")
        print(f"Total Keys Discovered : {stats['total_keys']}")
        print(f"Total Healthy Keys    : {stats['total_healthy_keys']}")
        print("----------------------------------------")
        for provider, data in stats["providers"].items():
            print(f"  {provider.upper():<12}: {data['total']:>2} keys (Healthy: {data['healthy']})")
        print("========================================")

        assert stats["total_keys"] > 0, "Expected to discover keys from .env"
        candidates = squad.get_candidate_slots()
        print(f"Active Candidate rotation count: {len(candidates)}")
        for p, slot in candidates:
            print(f"  Candidate: {p} -> {slot.name}")
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        squad.reload_squad()

if __name__ == "__main__":
    test_discovery()
