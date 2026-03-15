Name: oceanbase-diagnostic-tool
Version: %(echo $OBDIAG_VERSION)
Release: %(echo $RELEASE)%{?dist}
Summary: oceanbase diagnostic tool program
Group: Development/Tools
Url: git@github.com:oceanbase/oceanbase-diagnostic-tool.git
License: Commercial
# BuildRoot:  %_topdir/BUILDROOT
%define debug_package %{nil}
%define __os_install_post %{nil}
%define _build_id_links none
AutoReqProv: no

%description
oceanbase diagnostic tool program

%install
RPM_DIR=$OLDPWD
SRC_DIR=$OLDPWD
BUILD_DIR=$OLDPWD/rpmbuild
cd $SRC_DIR/
rm -rf build.log build dist oceanbase-diagnostic-tool.spec
DATE=`date`
VERSION="$RPM_PACKAGE_VERSION"

cd $SRC_DIR
pwd
pip install .[build]
cp -f src/main.py src/obdiag.py
sed -i  "s/<B_TIME>/$DATE/" ./src/common/version.py  && sed -i "s/<VERSION>/$VERSION/" ./src/common/version.py
mkdir -p $BUILD_DIR/SOURCES ${RPM_BUILD_ROOT}
mkdir -p ${RPM_BUILD_ROOT}/usr/bin
mkdir -p ${RPM_BUILD_ROOT}/opt/oceanbase-diagnostic-tool

# Build all-in-one binary with PyInstaller --add-data
# This bundles plugins, conf, example, resources, dependencies into the binary
pyinstaller --hidden-import=decimal \
    --add-data "plugins:plugins" \
    --add-data "conf:conf" \
    --add-data "example:example" \
    --add-data "resources:resources" \
    --add-data "dependencies/bin:dependencies/bin" \
    --add-data "rpm/init_obdiag_cmd.sh:rpm" \
    -p $SRC_DIR/src \
    -F src/obdiag.py
rm -f obdiag.py oceanbase-diagnostic-tool.spec

# Copy the all-in-one binary
\cp -rf $SRC_DIR/dist/obdiag ${RPM_BUILD_ROOT}/opt/oceanbase-diagnostic-tool/obdiag

%files
%defattr(-,root,root,0777)
/opt/oceanbase-diagnostic-tool/obdiag

%post
chmod -R 755 /opt/oceanbase-diagnostic-tool/obdiag
chown -R root:root /opt/oceanbase-diagnostic-tool/obdiag
chmod +x /opt/oceanbase-diagnostic-tool/obdiag
ln -sf /opt/oceanbase-diagnostic-tool/obdiag /usr/bin/obdiag

echo ""
echo "=============================================="
echo "OceanBase Diagnostic Tool installed!"
echo ""
echo "Please run the following command to initialize:"
echo ""
echo "  obdiag init"
echo ""
echo "=============================================="

%preun
# Clean up symbolic links before uninstall
rm -f /usr/bin/obdiag 2>/dev/null || true