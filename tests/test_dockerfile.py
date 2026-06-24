"""Tests for Dockerfile and deployment artifacts."""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


class TestDockerfile:
    def test_dockerfile_exists(self) -> None:
        assert (PROJECT_ROOT / "Dockerfile").exists()

    def test_dockerfile_has_multi_stage(self) -> None:
        content = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "AS builder" in content
        assert "AS runtime" in content

    def test_dockerfile_has_non_root_user(self) -> None:
        content = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "useradd" in content
        assert "USER axon" in content

    def test_dockerfile_has_healthcheck(self) -> None:
        content = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "HEALTHCHECK" in content
        assert "/health" in content

    def test_dockerfile_exposes_port_8000(self) -> None:
        content = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "EXPOSE 8000" in content

    def test_dockerfile_default_cmd_is_serve_api(self) -> None:
        content = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert 'CMD ["axon", "serve-api"' in content


class TestDockerCompose:
    def test_docker_compose_exists(self) -> None:
        assert (PROJECT_ROOT / "docker-compose.yml").exists()

    def test_docker_compose_has_postgres(self) -> None:
        content = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        assert "postgres:" in content
        assert "image: postgres" in content

    def test_docker_compose_has_api_service(self) -> None:
        content = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        assert "axon-api:" in content
        assert "AXON_DB_URL" in content

    def test_docker_compose_has_health_checks(self) -> None:
        content = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        assert "healthcheck:" in content


class TestKubernetesManifests:
    def test_k8s_directory_exists(self) -> None:
        assert (PROJECT_ROOT / "k8s").is_dir()

    @pytest.mark.parametrize(
        "manifest",
        [
            "axon-deployment.yaml",
            "axon-service.yaml",
            "axon-configmap.yaml",
            "axon-secret.yaml",
            "axon-ingress.yaml",
        ],
    )
    def test_manifest_exists(self, manifest: str) -> None:
        assert (PROJECT_ROOT / "k8s" / manifest).exists()

    def test_deployment_has_security_context(self) -> None:
        content = (PROJECT_ROOT / "k8s" / "axon-deployment.yaml").read_text(encoding="utf-8")
        assert "runAsNonRoot: true" in content
        assert "runAsUser: 10001" in content

    def test_deployment_has_probes(self) -> None:
        content = (PROJECT_ROOT / "k8s" / "axon-deployment.yaml").read_text(encoding="utf-8")
        assert "livenessProbe:" in content
        assert "readinessProbe:" in content
        assert "/health" in content

    def test_deployment_has_resource_limits(self) -> None:
        content = (PROJECT_ROOT / "k8s" / "axon-deployment.yaml").read_text(encoding="utf-8")
        assert "resources:" in content
        assert "limits:" in content
        assert "requests:" in content

    def test_service_targets_port_8000(self) -> None:
        content = (PROJECT_ROOT / "k8s" / "axon-service.yaml").read_text(encoding="utf-8")
        assert "port: 8000" in content

    def test_secret_uses_opaque(self) -> None:
        content = (PROJECT_ROOT / "k8s" / "axon-secret.yaml").read_text(encoding="utf-8")
        assert "type: Opaque" in content
        assert "db-url:" in content


class TestDockerignore:
    def test_dockerignore_exists(self) -> None:
        assert (PROJECT_ROOT / ".dockerignore").exists()

    def test_dockerignore_ignores_git(self) -> None:
        content = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
        assert ".git" in content

    def test_dockerignore_ignores_pycache(self) -> None:
        content = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
        assert "__pycache__" in content
