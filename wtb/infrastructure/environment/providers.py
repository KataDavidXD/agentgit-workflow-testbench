"""
Environment Provider Implementations.

Provides execution environment isolation for batch testing variants.

Usage:
    provider = RayEnvironmentProvider()
    env = provider.create_environment("variant-1", {"pip": ["numpy"]})
    runtime_env = provider.get_runtime_env("variant-1")
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from wtb.domain.interfaces.batch_runner import IEnvironmentProvider

logger = logging.getLogger(__name__)


class InProcessEnvironmentProvider(IEnvironmentProvider):
    """
    No-isolation environment provider.
    
    All variants run in the same process with shared dependencies.
    Use for development and testing where isolation isn't needed.
    """
    
    def __init__(self):
        self._environments: Dict[str, Dict[str, Any]] = {}
    
    def create_environment(
        self,
        variant_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a no-op environment (just stores config).
        
        Args:
            variant_id: Unique identifier for the variant
            config: Environment configuration (ignored)
            
        Returns:
            Empty environment spec
        """
        env = {"variant_id": variant_id, "type": "inprocess"}
        self._environments[variant_id] = env
        return env
    
    def cleanup_environment(self, variant_id: str) -> None:
        """Remove environment reference."""
        self._environments.pop(variant_id, None)
    
    def get_runtime_env(self, variant_id: str) -> Optional[Dict[str, Any]]:
        """Return None (no runtime env needed)."""
        return None


@dataclass
class RayRuntimeEnvConfig:
    """
    Configuration for Ray runtime environment.
    
    See: https://docs.ray.io/en/latest/ray-core/handling-dependencies.html
    """
    pip: list = field(default_factory=list)
    conda: Optional[Dict[str, Any]] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    working_dir: Optional[str] = None
    py_modules: list = field(default_factory=list)
    excludes: list = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Ray runtime_env dict."""
        env = {}
        
        if self.pip:
            env["pip"] = self.pip
        if self.conda:
            env["conda"] = self.conda
        if self.env_vars:
            env["env_vars"] = self.env_vars
        if self.working_dir:
            env["working_dir"] = self.working_dir
        if self.py_modules:
            env["py_modules"] = self.py_modules
        if self.excludes:
            env["excludes"] = self.excludes
        
        return env


class RayEnvironmentProvider(IEnvironmentProvider):
    """
    Ray runtime_env-based environment provider.
    
    Provides isolation using Ray's runtime_env feature:
    - Separate pip dependencies per variant
    - Environment variables
    - Working directory isolation
    
    Usage:
        provider = RayEnvironmentProvider()
        
        # Create environment with specific dependencies
        env = provider.create_environment("variant-1", {
            "pip": ["numpy==1.24.0"],
            "env_vars": {"MODEL_VERSION": "v1"},
        })
        
        # Get runtime_env for Ray task/actor
        runtime_env = provider.get_runtime_env("variant-1")
    """
    
    def __init__(self, base_env: Optional[Dict[str, Any]] = None):
        """
        Initialize provider.
        
        Args:
            base_env: Base runtime_env to extend for all variants
        """
        self._base_env = base_env or {}
        self._environments: Dict[str, RayRuntimeEnvConfig] = {}
    
    def create_environment(
        self,
        variant_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a Ray runtime_env.
        
        Args:
            variant_id: Unique identifier for the variant
            config: Environment configuration with optional keys:
                - pip: List of pip packages
                - conda: Conda environment dict
                - env_vars: Environment variables
                - working_dir: Working directory
                - py_modules: Python modules to include
                
        Returns:
            Ray runtime_env dict
        """
        # Merge with base env
        merged_pip = self._base_env.get("pip", []) + config.get("pip", [])
        merged_env_vars = {
            **self._base_env.get("env_vars", {}),
            **config.get("env_vars", {}),
        }
        
        env_config = RayRuntimeEnvConfig(
            pip=merged_pip,
            conda=config.get("conda"),
            env_vars=merged_env_vars,
            working_dir=config.get("working_dir"),
            py_modules=config.get("py_modules", []),
            excludes=config.get("excludes", []),
        )
        
        self._environments[variant_id] = env_config
        
        return env_config.to_dict()
    
    def cleanup_environment(self, variant_id: str) -> None:
        """
        Cleanup an environment.
        
        For Ray, this just removes the config.
        Ray manages actual environment lifecycle.
        
        Args:
            variant_id: Environment to cleanup
        """
        self._environments.pop(variant_id, None)
    
    def get_runtime_env(self, variant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get Ray runtime_env for a variant.
        
        Args:
            variant_id: Variant identifier
            
        Returns:
            Ray runtime_env dict or None if not found
        """
        env_config = self._environments.get(variant_id)
        if env_config is None:
            return None
        return env_config.to_dict()
    
    def list_environments(self) -> Dict[str, Dict[str, Any]]:
        """List all created environments."""
        return {
            vid: config.to_dict()
            for vid, config in self._environments.items()
        }


class GrpcEnvironmentProvider(IEnvironmentProvider):
    """
    gRPC-based environment provider (STUB).
    
    Wraps a colleague's gRPC environment management service.
    This is a placeholder for future integration.
    
    The gRPC service is expected to provide:
    - CreateEnvironment(variant_id, config) -> env_id
    - DestroyEnvironment(env_id)
    - GetEnvironment(env_id) -> runtime_config
    """
    
    def __init__(
        self,
        grpc_address: str,
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize gRPC provider.
        
        Args:
            grpc_address: gRPC service address (host:port)
            timeout_seconds: RPC timeout
        """
        self._grpc_address = grpc_address
        self._timeout = timeout_seconds
        self._environments: Dict[str, str] = {}  # variant_id -> remote_env_id
        
        # TODO: Initialize gRPC channel
        # self._channel = grpc.insecure_channel(grpc_address)
        # self._stub = environment_pb2_grpc.EnvironmentServiceStub(self._channel)
        
        logger.warning(
            "GrpcEnvironmentProvider is a stub. "
            "Full implementation requires gRPC proto definitions."
        )
    
    def create_environment(
        self,
        variant_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create environment via gRPC (stub)."""
        # TODO: Implement gRPC call
        # request = environment_pb2.CreateEnvironmentRequest(
        #     variant_id=variant_id,
        #     config=json.dumps(config),
        # )
        # response = self._stub.CreateEnvironment(request, timeout=self._timeout)
        # self._environments[variant_id] = response.env_id
        
        logger.info(f"[STUB] Would create gRPC environment for {variant_id}")
        self._environments[variant_id] = f"grpc-{variant_id}"
        
        return {"type": "grpc", "variant_id": variant_id}
    
    def cleanup_environment(self, variant_id: str) -> None:
        """Cleanup environment via gRPC (stub)."""
        remote_id = self._environments.pop(variant_id, None)
        
        if remote_id:
            # TODO: Implement gRPC call
            # request = environment_pb2.DestroyEnvironmentRequest(env_id=remote_id)
            # self._stub.DestroyEnvironment(request, timeout=self._timeout)
            logger.info(f"[STUB] Would destroy gRPC environment {remote_id}")
    
    def get_runtime_env(self, variant_id: str) -> Optional[Dict[str, Any]]:
        """Get runtime_env from gRPC service (stub)."""
        remote_id = self._environments.get(variant_id)
        if remote_id is None:
            return None
        
        # TODO: Implement gRPC call
        # request = environment_pb2.GetEnvironmentRequest(env_id=remote_id)
        # response = self._stub.GetEnvironment(request, timeout=self._timeout)
        # return json.loads(response.runtime_config)
        
        return {"type": "grpc", "remote_id": remote_id}

