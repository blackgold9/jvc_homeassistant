from __future__ import annotations

import copy
import logging
from typing import Any

from jvcprojector.command.base import Command, Spec, Parameter, LIMP_MODE, MapParameter
# Import SPECIFICATIONS directly from where it is defined to avoid import issues
from jvcprojector.command.command import SPECIFICATIONS

_LOGGER = logging.getLogger(__name__)

def get_spec(model_name: str) -> Spec:
    """
    Match a model name to a Spec using the logic described in pyjvcprojector.
    """
    if not model_name:
        return LIMP_MODE

    # 1. Exact match
    for spec in SPECIFICATIONS:
        if spec.matches_model(model_name):
            return spec

    # 2. Partial match (first 3 chars)
    for spec in SPECIFICATIONS:
        if spec.matches_prefix(model_name):
            # matches_prefix sets spec.model to the matched model
            return spec

    return LIMP_MODE

def _get_parameter(command_cls: type[Command], spec: Spec) -> Parameter | None:
    """
    Get the parameter definition for the command and spec.
    Returns a COPY of the parameter to avoid modifying the class definition.
    """
    param_def = command_cls.parameter

    target_param = None

    if isinstance(param_def, Parameter):
        # Global parameter (e.g. ModelName, or if only one defined)
        # Check if it respects limp mode
        if not spec.limp_mode or command_cls.limp_mode:
            target_param = param_def

    elif isinstance(param_def, dict):
        for key, param in param_def.items():
            if isinstance(key, Spec):
                if key == spec:
                    target_param = param
                    break
            elif isinstance(key, tuple):
                if spec in key:
                    target_param = param
                    break

    if target_param:
        try:
            # Create a copy so we don't modify the definition when resolving
            return copy.deepcopy(target_param)
        except Exception as err:
            _LOGGER.error("Failed to copy parameter for %s: %s", command_cls.name, err)
            return None

    return None

def is_command_supported(command_cls: type[Command], spec: Spec) -> bool:
    """Check if command is supported for the given spec."""
    param = _get_parameter(command_cls, spec)
    if not param:
        return False

    # Resolve the parameter for this specific model
    param.resolve(spec)
    return param.supported()

def get_command_options(command_cls: type[Command], spec: Spec) -> list[str]:
    """Get supported write options for a command."""
    param = _get_parameter(command_cls, spec)
    if not param:
        return []

    param.resolve(spec)
    if not param.supported():
        return []

    desc = param.describe()
    if isinstance(desc, dict) and "write" in desc:
        return list(desc["write"].values())

    return []
