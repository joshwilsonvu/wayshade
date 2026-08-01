from wayshade import WaylandUnavailableError
from wayshade._protocol.wlr_layer_shell_unstable_v1.zwlr_layer_shell_v1 import (
    ZwlrLayerShellV1,
)
from wayshade._protocol.wlr_layer_shell_unstable_v1.zwlr_layer_surface_v1 import (
    ZwlrLayerSurfaceV1,
)


def test_layer_shell_bindings_are_packaged() -> None:
    assert ZwlrLayerShellV1.name == "zwlr_layer_shell_v1"
    assert ZwlrLayerSurfaceV1.name == "zwlr_layer_surface_v1"


def test_error_is_public() -> None:
    assert issubclass(WaylandUnavailableError, RuntimeError)
