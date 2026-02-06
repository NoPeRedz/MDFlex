#!/bin/bash
# Build script for creating Ubuntu .deb package for MDFlex

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASES_DIR="${SCRIPT_DIR}/releases"

echo "=== MDFlex .deb Build Script ==="
echo ""

# Check for required tools
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo "Error: $1 is not installed."
        echo "Install it with: sudo apt install $2"
        exit 1
    fi
}

check_package() {
    if ! dpkg -l "$1" &> /dev/null 2>&1; then
        echo "Error: $1 package is not installed."
        echo "Install it with: sudo apt install $1"
        exit 1
    fi
}

echo "Checking dependencies..."
check_command dpkg-buildpackage "dpkg-dev"
check_command dh "debhelper"

# Create releases directory
echo "Creating releases directory..."
mkdir -p "${RELEASES_DIR}"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info/ .pybuild/
rm -f ../mdflex_*.deb ../mdflex_*.changes ../mdflex_*.buildinfo ../mdflex_*.tar.xz ../mdflex_*.dsc

# Make rules executable
chmod +x debian/rules

# Build the package
echo "Building .deb package..."
dpkg-buildpackage -us -uc -b

# Move built files to releases directory
echo "Moving packages to releases directory..."
mv ../mdflex_*.deb "${RELEASES_DIR}/" 2>/dev/null || true
mv ../mdflex_*.changes "${RELEASES_DIR}/" 2>/dev/null || true
mv ../mdflex_*.buildinfo "${RELEASES_DIR}/" 2>/dev/null || true

echo ""
echo "=== Build Complete ==="
echo ""
echo "Packages created in: ${RELEASES_DIR}"
ls -la "${RELEASES_DIR}"/mdflex_*.deb 2>/dev/null || echo "No .deb files found"
echo ""
echo "To install:   sudo apt install ${RELEASES_DIR}/mdflex_*.deb"
echo "To uninstall: sudo apt remove mdflex"
