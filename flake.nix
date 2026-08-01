{
  description = "Wayshade development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        # libglvnd supplies the EGL/OpenGL loader, not a GPU driver. Driver
        # selection remains the host distribution's responsibility.
        runtimeLibraries = [ pkgs.wayland pkgs.libglvnd ];
      in {
        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.python313
            pkgs.uv
            pkgs.pkg-config
            pkgs.wayland-scanner
            pkgs.wayland-protocols
            pkgs.wlr-protocols
          ];

          # PyWayland loads libwayland-client dynamically. Keep this scoped to
          # the repository's development shell; do not alter the user's global
          # linker path or select a Nix OpenGL driver for the host.
          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath runtimeLibraries}:$LD_LIBRARY_PATH"
          '';
        };
      });
}
