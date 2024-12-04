#
# spec file for package .spec
#
# Copyright (c) 2024 SUSE LLC
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via https://bugs.opensuse.org/
#

Name:           qem-bot
Version:        %{?version}git%{?commit}%{!?commit:%{time:git%Y%m%d}}
Release:        0
Summary:        Tool for scheduling maintenance jobs and syncing SMELT/OpenQA to QEM-Dashboard
License:        MIT
URL:            https://github.com/r-richardson/qem-bot
Source:         %{name}-%{version}.tar.gz
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  python3-osc
BuildRequires:  python3-openqa-client
BuildRequires:  python3-pika
BuildRequires:  python3-requests
BuildRequires:  python3-ruamel.yaml
BuildRequires:  python3-jsonschema
Requires:       python3-osc
Requires:       python3-openqa-client
Requires:       python3-pika
Requires:       python3-requests
Requires:       python3-ruamel.yaml
Requires:       python3-jsonschema

%description
QEM Bot is a tool for scheduling maintenance jobs and syncing SMELT/OpenQA to QEM-Dashboard.

%prep
%setup -q

%build
python3 setup.py build

%install
python3 setup.py install --root=%{buildroot} --prefix=/usr

%files
%license LICENSE
%doc Readme.md
/usr/bin/bot-ng.py
/usr/bin/pc_helper_online.py

%changelog
* %{time:git%Y%m%d} - Initial package creation.
