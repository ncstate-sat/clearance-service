with (import <nixpkgs> {});
mkShell {
  buildInputs = [
    mongodb-tools
  ];
}
