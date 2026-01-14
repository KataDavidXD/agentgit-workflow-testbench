from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetEnvStatusRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ...) -> None: ...

class EnvStatusResponse(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "status", "env_path", "has_pyproject", "has_uv_lock", "has_venv", "metadata_json")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ENV_PATH_FIELD_NUMBER: _ClassVar[int]
    HAS_PYPROJECT_FIELD_NUMBER: _ClassVar[int]
    HAS_UV_LOCK_FIELD_NUMBER: _ClassVar[int]
    HAS_VENV_FIELD_NUMBER: _ClassVar[int]
    METADATA_JSON_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    status: str
    env_path: str
    has_pyproject: bool
    has_uv_lock: bool
    has_venv: bool
    metadata_json: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., status: _Optional[str] = ..., env_path: _Optional[str] = ..., has_pyproject: bool = ..., has_uv_lock: bool = ..., has_venv: bool = ..., metadata_json: _Optional[str] = ...) -> None: ...

class CreateEnvRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "python_version", "packages", "requirements_file_content", "requirements_file_name")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    PYTHON_VERSION_FIELD_NUMBER: _ClassVar[int]
    PACKAGES_FIELD_NUMBER: _ClassVar[int]
    REQUIREMENTS_FILE_CONTENT_FIELD_NUMBER: _ClassVar[int]
    REQUIREMENTS_FILE_NAME_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    python_version: str
    packages: _containers.RepeatedScalarFieldContainer[str]
    requirements_file_content: bytes
    requirements_file_name: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., python_version: _Optional[str] = ..., packages: _Optional[_Iterable[str]] = ..., requirements_file_content: _Optional[bytes] = ..., requirements_file_name: _Optional[str] = ...) -> None: ...

class CreateEnvResponse(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "env_path", "python_version", "status", "pyproject_toml")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    ENV_PATH_FIELD_NUMBER: _ClassVar[int]
    PYTHON_VERSION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PYPROJECT_TOML_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    env_path: str
    python_version: str
    status: str
    pyproject_toml: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., env_path: _Optional[str] = ..., python_version: _Optional[str] = ..., status: _Optional[str] = ..., pyproject_toml: _Optional[str] = ...) -> None: ...

class DeleteEnvRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ...) -> None: ...

class DeleteEnvResponse(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "status")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    status: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., status: _Optional[str] = ...) -> None: ...

class DepsRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "packages", "requirements_file_content", "requirements_file_name")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    PACKAGES_FIELD_NUMBER: _ClassVar[int]
    REQUIREMENTS_FILE_CONTENT_FIELD_NUMBER: _ClassVar[int]
    REQUIREMENTS_FILE_NAME_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    packages: _containers.RepeatedScalarFieldContainer[str]
    requirements_file_content: bytes
    requirements_file_name: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., packages: _Optional[_Iterable[str]] = ..., requirements_file_content: _Optional[bytes] = ..., requirements_file_name: _Optional[str] = ...) -> None: ...

class DepsOperationResponse(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "status", "stdout", "stderr", "exit_code")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STDOUT_FIELD_NUMBER: _ClassVar[int]
    STDERR_FIELD_NUMBER: _ClassVar[int]
    EXIT_CODE_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    status: str
    stdout: str
    stderr: str
    exit_code: int
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., status: _Optional[str] = ..., stdout: _Optional[str] = ..., stderr: _Optional[str] = ..., exit_code: _Optional[int] = ...) -> None: ...

class ListDepsRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ...) -> None: ...

class ListDepsResponse(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "dependencies", "locked_versions")
    class LockedVersionsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    DEPENDENCIES_FIELD_NUMBER: _ClassVar[int]
    LOCKED_VERSIONS_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    dependencies: _containers.RepeatedScalarFieldContainer[str]
    locked_versions: _containers.ScalarMap[str, str]
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., dependencies: _Optional[_Iterable[str]] = ..., locked_versions: _Optional[_Mapping[str, str]] = ...) -> None: ...

class SyncEnvRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ...) -> None: ...

class SyncEnvResponse(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "status", "stdout", "stderr", "exit_code")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STDOUT_FIELD_NUMBER: _ClassVar[int]
    STDERR_FIELD_NUMBER: _ClassVar[int]
    EXIT_CODE_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    status: str
    stdout: str
    stderr: str
    exit_code: int
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., status: _Optional[str] = ..., stdout: _Optional[str] = ..., stderr: _Optional[str] = ..., exit_code: _Optional[int] = ...) -> None: ...

class RunCodeRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "code", "timeout")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    code: str
    timeout: int
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., code: _Optional[str] = ..., timeout: _Optional[int] = ...) -> None: ...

class RunCodeResponse(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "stdout", "stderr", "exit_code")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    STDOUT_FIELD_NUMBER: _ClassVar[int]
    STDERR_FIELD_NUMBER: _ClassVar[int]
    EXIT_CODE_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    stdout: str
    stderr: str
    exit_code: int
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., stdout: _Optional[str] = ..., stderr: _Optional[str] = ..., exit_code: _Optional[int] = ...) -> None: ...

class ExportEnvRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ...) -> None: ...

class ExportEnvResponse(_message.Message):
    __slots__ = ("workflow_id", "node_id", "version_id", "pyproject_toml", "uv_lock")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    PYPROJECT_TOML_FIELD_NUMBER: _ClassVar[int]
    UV_LOCK_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    version_id: str
    pyproject_toml: str
    uv_lock: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., pyproject_toml: _Optional[str] = ..., uv_lock: _Optional[str] = ...) -> None: ...

class CleanupRequest(_message.Message):
    __slots__ = ("idle_hours",)
    IDLE_HOURS_FIELD_NUMBER: _ClassVar[int]
    idle_hours: int
    def __init__(self, idle_hours: _Optional[int] = ...) -> None: ...

class CleanupResponse(_message.Message):
    __slots__ = ("deleted", "checked_at_unix")
    DELETED_FIELD_NUMBER: _ClassVar[int]
    CHECKED_AT_UNIX_FIELD_NUMBER: _ClassVar[int]
    deleted: _containers.RepeatedScalarFieldContainer[str]
    checked_at_unix: int
    def __init__(self, deleted: _Optional[_Iterable[str]] = ..., checked_at_unix: _Optional[int] = ...) -> None: ...

class GetOperationsRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id", "status", "limit", "offset")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    status: str
    limit: int
    offset: int
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., status: _Optional[str] = ..., limit: _Optional[int] = ..., offset: _Optional[int] = ...) -> None: ...

class OperationRecord(_message.Message):
    __slots__ = ("id", "workflow_id", "node_id", "version_id", "operation", "status", "started_at_unix", "finished_at_unix", "duration_ms", "stdout", "stderr", "exit_code", "error", "metadata_json")
    ID_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    OPERATION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_UNIX_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_UNIX_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    STDOUT_FIELD_NUMBER: _ClassVar[int]
    STDERR_FIELD_NUMBER: _ClassVar[int]
    EXIT_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    METADATA_JSON_FIELD_NUMBER: _ClassVar[int]
    id: int
    workflow_id: str
    node_id: str
    version_id: str
    operation: str
    status: str
    started_at_unix: int
    finished_at_unix: int
    duration_ms: int
    stdout: str
    stderr: str
    exit_code: int
    error: str
    metadata_json: str
    def __init__(self, id: _Optional[int] = ..., workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ..., version_id: _Optional[str] = ..., operation: _Optional[str] = ..., status: _Optional[str] = ..., started_at_unix: _Optional[int] = ..., finished_at_unix: _Optional[int] = ..., duration_ms: _Optional[int] = ..., stdout: _Optional[str] = ..., stderr: _Optional[str] = ..., exit_code: _Optional[int] = ..., error: _Optional[str] = ..., metadata_json: _Optional[str] = ...) -> None: ...

class OperationListResponse(_message.Message):
    __slots__ = ("total", "limit", "offset", "items")
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    total: int
    limit: int
    offset: int
    items: _containers.RepeatedCompositeFieldContainer[OperationRecord]
    def __init__(self, total: _Optional[int] = ..., limit: _Optional[int] = ..., offset: _Optional[int] = ..., items: _Optional[_Iterable[_Union[OperationRecord, _Mapping]]] = ...) -> None: ...

class DeleteOperationsRequest(_message.Message):
    __slots__ = ("workflow_id", "node_id")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    node_id: str
    def __init__(self, workflow_id: _Optional[str] = ..., node_id: _Optional[str] = ...) -> None: ...

class DeleteOperationsResponse(_message.Message):
    __slots__ = ("workflow_id", "deleted_count", "node_id", "deleted_node_ids")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    DELETED_COUNT_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    DELETED_NODE_IDS_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    deleted_count: int
    node_id: str
    deleted_node_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, workflow_id: _Optional[str] = ..., deleted_count: _Optional[int] = ..., node_id: _Optional[str] = ..., deleted_node_ids: _Optional[_Iterable[str]] = ...) -> None: ...
