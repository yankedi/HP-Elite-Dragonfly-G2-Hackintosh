{
  description = "HP Elite Dragonfly G2 (Tiger Lake) macOS Tahoe development and verification environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          llvm21 = pkgs.llvmPackages_21;
        in
        {
          default = pkgs.mkShellNoCC {
            name = "mac-for-elitebook-dev";
            packages = [
              llvm21.clang-unwrapped
              llvm21.llvm
              llvm21.lld
              pkgs.rcodesign
              pkgs.grub2
              pkgs.mtools
              pkgs.dosfstools
              pkgs.acpica-tools
              pkgs.python3
              pkgs.openssh
              pkgs.rsync
              pkgs.jq
              pkgs.gnumake
              pkgs.git
            ];

            CLANG_APPLE = "${llvm21.clang-unwrapped}/bin/clang-21";
            LLVM_BIN = "${llvm21.llvm}/bin";
            RCODESIGN = "${pkgs.rcodesign}/bin/rcodesign";
            GRUB_EDITENV = "${pkgs.grub2}/bin/grub-editenv";

            shellHook = ''
              if [ -z "''${SDKROOT:-}" ] && [ -d "/srv/tgl26-usb/GA45-AppleTGL-Native-Port/toolchain/MacOSX26.5.sdk" ]; then
                export SDKROOT="/srv/tgl26-usb/GA45-AppleTGL-Native-Port/toolchain/MacOSX26.5.sdk"
              fi
              if [ -z "''${LD64_LLD:-}" ] && [ -x "/srv/tgl26-usb/GA46-TGL-Integration/toolchain/pr204805/build/bin/ld64.lld" ]; then
                export LD64_LLD="/srv/tgl26-usb/GA46-TGL-Integration/toolchain/pr204805/build/bin/ld64.lld"
              fi
            '';
          };
        });
    };
}
