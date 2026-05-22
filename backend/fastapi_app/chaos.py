import docker
from docker.errors import NotFound

_client: docker.DockerClient | None = None


def _client_lazy() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def stop_container(name_substr: str) -> dict:
    c = _client_lazy()
    matches = [ct for ct in c.containers.list(all=True) if name_substr in ct.name]
    if not matches:
        raise NotFound(f"no container matching '{name_substr}'")
    for ct in matches:
        ct.stop(timeout=2)
    return {"stopped": [ct.name for ct in matches]}


def start_container(name_substr: str) -> dict:
    c = _client_lazy()
    matches = [ct for ct in c.containers.list(all=True) if name_substr in ct.name]
    if not matches:
        raise NotFound(f"no container matching '{name_substr}'")
    for ct in matches:
        ct.start()
    return {"started": [ct.name for ct in matches]}
