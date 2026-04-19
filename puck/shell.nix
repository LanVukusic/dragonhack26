{ pkgs ? import <nixpkgs> {} }:

let
  # Create a customized VS Code FHS environment
  vscodeWithPython = pkgs.vscode.fhsWithPackages (ps: with ps; [
    python3
    # Uncomment to add pip or other specific python packages:
    # python3Packages.pip
  ]);
in
pkgs.mkShell {
  packages = [
    vscodeWithPython
    
    pkgs.python3 
    pkgs.nodejs 
    pkgs.git 
  ];

  shellHook = ''
    echo "VS Code FHS environment with Python is ready."
    echo "Run 'code .' to launch."
  '';
}
