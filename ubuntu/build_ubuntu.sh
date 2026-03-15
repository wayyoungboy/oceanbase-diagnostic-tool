#!/usr/bin/env bash
# Build Ubuntu/Debian package for oceanbase-diagnostic-tool
# All-in-one binary with bundled resources
#
# Usage: ./build_ubuntu.sh [version] [release]
#
# Requirements:
#   sudo apt install dpkg-dev -y
#   Python 3.11+ with pyinstaller installed

set -e

# Get script directory
SCRIPT_DIR=$(readlink -f "$(dirname ${BASH_SOURCE[0]})")
PROJECT_DIR=$(dirname "$SCRIPT_DIR")

# Parse arguments
OBDIAG_VERSION=${1:-"4.2.0"}
RELEASE=${2:-$(date +%Y%m%d%H%M)}

# Detect architecture
ARCH=$(dpkg --print-architecture)
case "$ARCH" in
    amd64|x86_64)
        ARCH="amd64"
        ;;
    arm64|aarch64)
        ARCH="arm64"
        ;;
    *)
        echo "Warning: Unknown architecture $ARCH, using as-is"
        ;;
esac

echo "=============================================="
echo "Building Ubuntu/Debian all-in-one package"
echo "Version: ${OBDIAG_VERSION}"
echo "Release: ${RELEASE}"
echo "Architecture: ${ARCH}"
echo "=============================================="

# Check dependencies
command -v dpkg-deb >/dev/null 2>&1 || {
    echo "Error: dpkg-deb not found. Please install: sudo apt install dpkg-dev -y"
    exit 1
}

# Find Python 3.11+
PYTHON=""
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
    echo "Using Python from venv: $PYTHON"
else
    for py in python3.12 python3.11 python3; do
        if command -v $py >/dev/null 2>&1; then
            version=$($py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            if [ "$(echo "$version >= 3.11" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
                PYTHON=$py
                echo "Using Python: $PYTHON (version $version)"
                break
            fi
        fi
    done
fi

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.11+ not found. Please install Python 3.11+ or activate the virtual environment."
    exit 1
fi

# Check pyinstaller
if ! $PYTHON -c "import PyInstaller" 2>/dev/null; then
    echo "Installing pyinstaller..."
    $PYTHON -m pip install pyinstaller
fi

cd "$PROJECT_DIR"

# Clean old build
echo "Cleaning old build files..."
rm -rf ./build_deb ./build ./dist
rm -f ./*.deb
rm -f src/obdiag.py

# Create build directory
BUILD_DIR="./build_deb/oceanbase-diagnostic-tool_${OBDIAG_VERSION}-${RELEASE}_${ARCH}"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/opt/oceanbase-diagnostic-tool"

# Install Python build dependencies
echo "Installing build dependencies (if needed)..."
$PYTHON -m pip install -e . 2>/dev/null || true

# Prepare source
echo "Preparing source files..."
cp -f src/main.py src/obdiag.py

# Update version info
DATE=$(date)
sed -i "s/<B_TIME>/$DATE/" ./src/common/version.py
sed -i "s/<VERSION>/$OBDIAG_VERSION/" ./src/common/version.py

# Build all-in-one binary with PyInstaller --add-data
# This bundles plugins, conf, example, resources, dependencies into the binary
echo "Building all-in-one binary with PyInstaller..."
$PYTHON -m PyInstaller \
    --hidden-import=decimal \
    --add-data "plugins:plugins" \
    --add-data "conf:conf" \
    --add-data "example:example" \
    --add-data "resources:resources" \
    --add-data "dependencies/bin:dependencies/bin" \
    --add-data "rpm/init_obdiag_cmd.sh:rpm" \
    -p ./src \
    -F src/obdiag.py

# Cleanup temp file
rm -f src/obdiag.py

# Copy binary
echo "Copying all-in-one binary..."
cp -rf dist/obdiag "$BUILD_DIR/opt/oceanbase-diagnostic-tool/"
chmod +x "$BUILD_DIR/opt/oceanbase-diagnostic-tool/obdiag"

# Create control file
cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: oceanbase-diagnostic-tool
Version: ${OBDIAG_VERSION}-${RELEASE}
Section: devel
Priority: optional
Architecture: ${ARCH}
Maintainer: OceanBase <oceanbase-public@list.alibaba-inc.com>
Description: OceanBase Diagnostic Tool
 OceanBase Diagnostic Tool (obdiag) is a comprehensive diagnostic tool for
 OceanBase database clusters. It provides cluster diagnosis, log gathering,
 analysis, and various diagnostic features.
 .
 This is an all-in-one package. After installation, run:
   obdiag init
 to initialize the tool and extract resources to ~/.obdiag
 .
 Features:
  - Cluster health checking
  - Log gathering and analysis
  - Performance diagnostics
  - Root cause analysis
  - Configuration management
Homepage: https://github.com/oceanbase/oceanbase-diagnostic-tool
EOF

# Create postinst script
cat > "$BUILD_DIR/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e

# Create symlink
if [ ! -e /usr/bin/obdiag ]; then
    ln -sf /opt/oceanbase-diagnostic-tool/obdiag /usr/bin/obdiag
fi

# Set permissions
chmod 755 /opt/oceanbase-diagnostic-tool/obdiag

echo ""
echo "=============================================="
echo "OceanBase Diagnostic Tool installed!"
echo ""
echo "Please run the following command to initialize:"
echo ""
echo "  obdiag init"
echo ""
echo "=============================================="

exit 0
POSTINST

# Create prerm script
cat > "$BUILD_DIR/DEBIAN/prerm" << 'PRERM'
#!/bin/bash
set -e

# Remove symlink
if [ -L /usr/bin/obdiag ]; then
    rm -f /usr/bin/obdiag
fi

exit 0
PRERM

chmod 755 "$BUILD_DIR/DEBIAN/postinst"
chmod 755 "$BUILD_DIR/DEBIAN/prerm"

# Build the package
echo "Building .deb package..."
dpkg-deb --build "$BUILD_DIR"

# Copy to current directory
DEB_FILE="oceanbase-diagnostic-tool_${OBDIAG_VERSION}-${RELEASE}_${ARCH}.deb"
if [ -f "${BUILD_DIR}.deb" ]; then
    mv "${BUILD_DIR}.deb" ./
    echo ""
    echo "=============================================="
    echo "Build successful!"
    echo "Package: $(pwd)/${DEB_FILE}"
    echo ""
    echo "Install with: sudo dpkg -i ${DEB_FILE}"
    echo "Then run: obdiag init"
    echo "=============================================="
else
    echo "Error: Failed to build .deb package"
    exit 1
fi

# Cleanup
echo "Cleaning build directory..."
rm -rf ./build_deb ./build ./dist

echo "Done!"