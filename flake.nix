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
        waylandLibraries = [ pkgs.wayland ];
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
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath waylandLibraries}:$LD_LIBRARY_PATH"
          '';
        };
      });
}
