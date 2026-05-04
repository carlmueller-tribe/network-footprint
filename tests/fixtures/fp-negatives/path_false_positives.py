import os
import pathlib

# Filesystem path operations — NOT routes
config_path = pathlib.Path("/etc/config")
result = os.path.join("/tmp", "output.txt")


def process(file_path: str) -> None:
    p = pathlib.Path(file_path)
    resolved = p.resolve()
    _ = resolved.parts
