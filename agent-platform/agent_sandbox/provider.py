"""
Docker 沙箱提供者 — 管理容器的创建/销毁/命令执行
"""
import os
import docker
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SandboxConfig:
    user_id: int
    cpu_limit: float = 1.0
    memory_limit_mb: int = 512
    workspace_host_path: str = ""
    workspace_container_path: str = "/workspace"


class DockerSandboxProvider:
    def __init__(self):
        self.client = docker.from_env()
        self.image = os.getenv("SANDBOX_IMAGE", "python:3.12-slim")

    def create(self, config: SandboxConfig) -> str:
        Path(config.workspace_host_path).mkdir(parents=True, exist_ok=True)

        container = self.client.containers.run(
            image=self.image,
            name=f"sandbox-user-{config.user_id}",
            command="tail -f /dev/null",
            detach=True,
            remove=False,
            cpu_quota=int(config.cpu_limit * 100000),
            cpu_period=100000,
            mem_limit=f"{config.memory_limit_mb}m",
            pids_limit=200,
            read_only=True,
            cap_drop=["ALL"],
            cap_add=["CHOWN", "DAC_OVERRIDE", "SETGID", "SETUID"],
            security_opt=["no-new-privileges:true"],
            network_mode="bridge",
            environment={
                "WORKSPACE": config.workspace_container_path,
                "HOME": config.workspace_container_path,
            },
            tmpfs={
                "/tmp": "size=128m,mode=1777",
                "/run": "size=32m,mode=0755",
            },
            volumes={
                config.workspace_host_path: {
                    "bind": config.workspace_container_path,
                    "mode": "rw",
                }
            },
        )
        return container.id

    def start(self, container_id: str):
        self.client.containers.get(container_id).start()

    def stop(self, container_id: str):
        self.client.containers.get(container_id).stop(timeout=10)

    def destroy(self, container_id: str):
        c = self.client.containers.get(container_id)
        c.stop(timeout=5)
        c.remove(force=True)

    def exec_cmd(self, container_id: str, command: str, timeout: int = 30) -> dict:
        c = self.client.containers.get(container_id)
        exit_code, output = c.exec_run(
            f"sh -c '{command}'",
            workdir="/workspace",
            user="root",
        )
        return {
            "exit_code": exit_code,
            "stdout": output.decode() if output else "",
        }

    def get_status(self, container_id: str) -> str:
        try:
            c = self.client.containers.get(container_id)
            return c.status
        except Exception:
            return "not_found"

    def write_file(self, container_id: str, path: str, content: bytes):
        """直接写宿主机文件（bind mount），不需 exec"""
        pass

    def read_file(self, container_id: str, path: str) -> bytes:
        pass
