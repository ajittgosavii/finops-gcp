"""Connector registry.

Connectors are registered lazily by key so that importing this package never
drags in `boto3`, `azure-*` or `google-cloud-bigquery`. Demo Mode must run on a
bare `pip install -r requirements.txt` with no cloud SDKs present, and a
customer who only uses AWS should never need the Azure SDK installed.
"""

from __future__ import annotations

import importlib
from typing import Callable, Dict, List, Optional, Type

from finops_core.connectors.base import (
    AuthKind,
    Capability,
    ConnectionResult,
    Connector,
    ConnectorSpec,
    Recommendation,
    UnconfiguredConnector,
)

__all__ = [
    "AuthKind",
    "Capability",
    "ConnectionResult",
    "Connector",
    "ConnectorSpec",
    "Recommendation",
    "UnconfiguredConnector",
    "REGISTRY",
    "get_connector",
    "available_connectors",
    "connectors_for_cloud",
]

# key -> "module:ClassName". Resolved on first use.
REGISTRY: Dict[str, str] = {
    # Demo
    "demo": "finops_core.connectors.demo:DemoConnector",
    # Native cloud billing
    "aws_native": "finops_core.connectors.aws_native:AWSNativeConnector",
    "azure_native": "finops_core.connectors.azure_native:AzureNativeConnector",
    "gcp_native": "finops_core.connectors.gcp_native:GCPNativeConnector",
    "oci_native": "finops_core.connectors.oci_native:OCINativeConnector",
    # Any FOCUS-conformant file or object store
    "focus_file": "finops_core.connectors.focus_file:FocusFileConnector",
    # Commercial FinOps platforms
    "cloudability": "finops_core.connectors.vendors.cloudability:CloudabilityConnector",
    "cloudhealth": "finops_core.connectors.vendors.cloudhealth:CloudHealthConnector",
    "flexera": "finops_core.connectors.vendors.flexera:FlexeraConnector",
    "finout": "finops_core.connectors.vendors.finout:FinoutConnector",
    "vantage": "finops_core.connectors.vendors.vantage:VantageConnector",
    "cloudzero": "finops_core.connectors.vendors.cloudzero:CloudZeroConnector",
    "harness": "finops_core.connectors.vendors.harness:HarnessConnector",
    "nops": "finops_core.connectors.vendors.nops:NOpsConnector",
    "kubecost": "finops_core.connectors.vendors.kubecost:KubecostConnector",
    "opencost": "finops_core.connectors.vendors.kubecost:OpenCostConnector",
    "turbonomic": "finops_core.connectors.vendors.turbonomic:TurbonomicConnector",
    "servicenow": "finops_core.connectors.vendors.servicenow:ServiceNowConnector",
}


def _resolve(key: str) -> Type[Connector]:
    target = REGISTRY.get(key)
    if not target:
        raise KeyError(f"Unknown connector: {key!r}. Known: {', '.join(sorted(REGISTRY))}")
    module_name, class_name = target.split(":")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def get_connector(key: str, secrets: Optional[Dict[str, str]] = None, **options) -> Connector:
    """Instantiate a connector.

    Raises only on an unknown key or a genuinely broken module. A connector
    that is merely missing credentials is a normal state -- ask it via
    `.configured` / `.missing_secrets()`.
    """
    cls = _resolve(key)
    return cls(secrets=secrets or {}, **options)


def available_connectors() -> List[str]:
    return sorted(REGISTRY)


def specs() -> List[ConnectorSpec]:
    """Every connector's static metadata, for the Integrations tab.

    A connector whose optional SDK is not installed still contributes its spec,
    so the admin can see what it would need. Import failures degrade to a skip,
    never to a crashed page.
    """
    out: List[ConnectorSpec] = []
    for key in available_connectors():
        try:
            out.append(_resolve(key)(secrets={}).spec)
        except Exception:
            continue
    return out


def connectors_for_cloud(cloud: str) -> List[str]:
    return [s.key for s in specs() if cloud in s.clouds]
