"""airplay-doctor - check why AirPlay cannot see a device."""

from .network import (
    Device,
    Record,
    build_ptr_query,
    check_port,
    devices,
    discover,
    encode_name,
    interface_names,
    local_addresses,
    parse_response,
    read_name,
)

__version__ = "0.1.0"

__all__ = [
    "Device",
    "Record",
    "build_ptr_query",
    "check_port",
    "devices",
    "discover",
    "encode_name",
    "interface_names",
    "local_addresses",
    "parse_response",
    "read_name",
    "__version__",
]
