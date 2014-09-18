Name: python-release-path
Version: 0.2.0
%define buildnumber %(echo "${BUILD_NUMBER:-dev}")
Release: 4
Summary: Tools for managing a release-branch based git workflow
License: MIT
Group: Development/Libraries
Url: https://github.com/amplify-education/release-path
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Source0: %{name}-%{version}.tar.gz
BuildArch: noarch

Requires: GitPython
Requires: python-simpleversions
BuildRequires: python-setuptools

%description
Tools for managing a release-branch based git workflow

%prep
%setup -q

%build
env CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build

%install
%{__python} setup.py install -O1 --root=%{buildroot} --record=INSTALLED_FILES

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%defattr(-,root,root)
%doc README.rst
