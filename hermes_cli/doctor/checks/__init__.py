"""Doctor checks package — importing this registers all checks."""

from hermes_cli.doctor.checks import (  # noqa: F401 — side-effect imports
    python_env,
    security,
    dep_mgmt,
    config_files,
    xai_retirement,
    auth_providers,
    directory_structure,
    gateway_service,
    command_install,
    external_tools,
    api_connectivity,
    tool_availability,
    skills_hub,
    memory_provider,
    profiles,
)
