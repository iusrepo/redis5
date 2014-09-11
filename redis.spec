%global _hardened_build 1

%global with_perftools 0

# redis 2.8 sentinel is the first upstream version to work
# however as packaged here it is entirely broken
# FIXME: consider removal into a separate package
%if 0%{?fedora} >= 21 || 0%{?rhel} >= 7
%global with_sentinel 1
%endif

%if 0%{?fedora} >= 15 || 0%{?rhel} >= 7
%global with_systemd 1
%else
%global with_systemd 0
%endif

# tcl 8.4 in EL5.
%if 0%{?el5}
%global with_tests 0
%else
%global with_tests 1
%endif

Name:              redis
Version:           2.8.14
Release:           1%{?dist}
Summary:           A persistent caching system, key-value and data structures database
License:           BSD
URL:               http://redis.io
Source0:           http://download.redis.io/releases/%{name}-%{version}.tar.gz
Source1:           %{name}.logrotate
Source2:           %{name}-sentinel.service
Source3:           %{name}.service
Source4:           %{name}.tmpfiles
Source5:           %{name}-sentinel.init
Source6:           %{name}.init
# Update configuration for Fedora
Patch0:            redis-2.8.11-redis-conf.patch
Patch1:            redis-2.8.11-deps-library-fPIC-performance-tuning.patch
Patch2:            redis-2.8.11-use-system-jemalloc.patch
# tests/integration/replication-psync.tcl failed on slow machines(GITHUB #1417)
Patch3:            redis-2.8.11-disable-test-failed-on-slow-machine.patch
%if 0%{?with_perftools}
BuildRequires:     gperftools-devel
%else
BuildRequires:     jemalloc-devel
%endif
%if 0%{?with_tests}
BuildRequires:     procps-ng
%endif
%if 0%{?with_systemd}
BuildRequires:     systemd
%endif
%if 0%{?with_tests}
BuildRequires:     tcl
%endif
Requires:          logrotate
Requires(pre):     shadow-utils
%if 0%{?with_systemd}
Requires(post):    systemd
Requires(preun):   systemd
Requires(postun):  systemd
%else
Requires(post):    chkconfig
Requires(preun):   chkconfig
Requires(preun):   initscripts
Requires(postun):  initscripts
%endif

%description
Redis is an advanced key-value store. It is often referred to as a data 
structure server since keys can contain strings, hashes, lists, sets and 
sorted sets.

You can run atomic operations on these types, like appending to a string;
incrementing the value in a hash; pushing to a list; computing set 
intersection, union and difference; or getting the member with highest 
ranking in a sorted set.

In order to achieve its outstanding performance, Redis works with an 
in-memory dataset. Depending on your use case, you can persist it either 
by dumping the dataset to disk every once in a while, or by appending 
each command to a log.

Redis also supports trivial-to-setup master-slave replication, with very 
fast non-blocking first synchronization, auto-reconnection on net split 
and so forth.

Other features include Transactions, Pub/Sub, Lua scripting, Keys with a 
limited time-to-live, and configuration settings to make Redis behave like 
a cache.

You can use Redis from most programming languages also.

%prep
%setup -q
rm -frv deps/jemalloc
%patch0 -p1
%patch1 -p1
%patch2 -p1
%if 0%{?with_tests}
%patch3 -p1
%endif

# No hidden build.
sed -i -e 's|\t@|\t|g' deps/lua/src/Makefile
sed -i -e 's|$(QUIET_CC)||g' src/Makefile
sed -i -e 's|$(QUIET_LINK)||g' src/Makefile
sed -i -e 's|$(QUIET_INSTALL)||g' src/Makefile
# Ensure deps are built with proper flags
sed -i -e 's|$(CFLAGS)|%{optflags}|g' deps/Makefile
sed -i -e 's|OPTIMIZATION?=-O3|OPTIMIZATION=%{optflags}|g' deps/hiredis/Makefile
sed -i -e 's|$(LDFLAGS)|%{?__global_ldflags}|g' deps/hiredis/Makefile
sed -i -e 's|$(CFLAGS)|%{optflags}|g' deps/linenoise/Makefile
sed -i -e 's|$(LDFLAGS)|%{?__global_ldflags}|g' deps/linenoise/Makefile

%build
make %{?_smp_mflags} \
    DEBUG="" \
    LDFLAGS="%{?__global_ldflags}" \
    CFLAGS+="%{optflags}" \
    LUA_LDFLAGS+="%{?__global_ldflags}" \
%if 0%{?with_perftools}
    MALLOC=tcmalloc \
%else
    MALLOC=jemalloc \
%endif
    all

%install
make install INSTALL="install -p" PREFIX=%{buildroot}%{_prefix}

# Filesystem.
install -d %{buildroot}%{_sharedstatedir}/%{name}
install -d %{buildroot}%{_localstatedir}/log/%{name}
install -d %{buildroot}%{_localstatedir}/run/%{name}

# Install logrotate file.
install -pDm644 %{S:1} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}

# Install configuration files.
install -pDm644 %{name}.conf %{buildroot}%{_sysconfdir}/%{name}.conf
%if 0%{?with_sentinel}
install -pDm644 sentinel.conf %{buildroot}%{_sysconfdir}/%{name}-sentinel.conf
%endif

# Install Systemd/SysV files.
%if 0%{?with_systemd}
mkdir -p %{buildroot}%{_unitdir}
install -pm644 %{S:3} %{buildroot}%{_unitdir}
%if 0%{?with_sentinel}
install -pm644 %{S:2} %{buildroot}%{_unitdir}
%endif

# Install systemd tmpfiles config.
install -pDm644 %{S:4} %{buildroot}%{_tmpfilesdir}/%{name}.conf
%else
%if 0%{?with_sentinel}
install -pDm755 %{S:5} %{buildroot}%{_initrddir}/%{name}-sentinel
%endif
install -pDm755 %{S:6} %{buildroot}%{_initrddir}/%{name}
%endif

# Fix non-standard-executable-perm error.
chmod 755 %{buildroot}%{_bindir}/%{name}-*

%check
%if 0%{?with_tests}
make test ||:
%if 0%{?with_sentinel}
make test-sentinel ||:
%endif
%endif

%pre
getent group %{name} &> /dev/null || groupadd -r %{name} &> /dev/null
getent passwd %{name} &> /dev/null || \
useradd -r -g %{name} -d %{_sharedstatedir}/%{name} -s /sbin/nologin \
-c 'Redis Database Server' %{name} &> /dev/null
exit 0

%post
%if 0%{?with_systemd}
%if 0%{?with_sentinel}
%systemd_post %{name}-sentinel.service
%endif
%systemd_post %{name}.service
%else
%if 0%{?with_sentinel}
chkconfig --add %{name}-sentinel
%endif
chkconfig --add %{name}
%endif

%preun
%if 0%{?with_systemd}
%if 0%{?with_sentinel}
%systemd_preun %{name}-sentinel.service
%endif
%systemd_preun %{name}.service
%else
if [ $1 -eq 0 ] ; then
%if 0%{?with_sentinel}
service %{name}-sentinel stop &> /dev/null
chkconfig --del %{name}-sentinel &> /dev/null
%endif
service %{name} stop &> /dev/null
chkconfig --del %{name} &> /dev/null
%endif

%postun
%if 0%{?with_systemd}
%if 0%{?with_sentinel}
%systemd_postun_with_restart %{name}-sentinel.service
%endif
%systemd_postun_with_restart %{name}.service
%else
if [ "$1" -ge "1" ] ; then
%if 0%{?with_sentinel}
    service %{name}-sentinel condrestart >/dev/null 2>&1 || :
%endif
    service %{name} condrestart >/dev/null 2>&1 || :
fi
%endif

%files
%doc 00-RELEASENOTES BUGS CONTRIBUTING COPYING MANIFESTO README
%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%config(noreplace) %{_sysconfdir}/%{name}.conf
%if 0%{?with_sentinel}
%config(noreplace) %{_sysconfdir}/%{name}-sentinel.conf
%endif
%dir %attr(0750, redis, redis) %{_sharedstatedir}/%{name}
%dir %attr(0750, redis, redis) %{_localstatedir}/log/%{name}
%dir %attr(0750, redis, redis) %{_localstatedir}/run/%{name}
%{_bindir}/%{name}-*
%if 0%{?with_systemd}
%{_tmpfilesdir}/%{name}.conf
%if 0%{?with_sentinel}
%{_unitdir}/%{name}-sentinel.service
%endif
%{_unitdir}/%{name}.service
%else
%if 0%{?with_sentinel}
%{_initrddir}/%{name}-sentinel
%endif
%{_initrddir}/%{name}
%endif

%changelog
* Thu Sep 11 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.14-1
- Upstream 2.8.14 (RHBZ #1136287)
- Bugfix for lua scripting users (server crash)
- Refresh patches
- backport spec from EPEL7 (thanks Warren)

* Wed Jul 16 2014 Christopher Meng <rpm@cicku.me> - 2.8.13-1
- Update to 2.8.13

* Tue Jun 24 2014 Christopher Meng <rpm@cicku.me> - 2.8.12-1
- Update to 2.8.12

* Wed Jun 18 2014 Christopher Meng <rpm@cicku.me> - 2.8.11-1
- Update to 2.8.11

* Sun Jun 08 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.16-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Fri Sep 06 2013 Fabian Deutsch <fabian.deutsch@gmx.de> - 2.6.16-1
- Update to 2.6.16
- Fix rhbz#973151
- Fix rhbz#656683
- Fix rhbz#977357 (Jan Vcelak <jvcelak@fedoraproject.org>)

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.13-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Tue Jul 23 2013 Peter Robinson <pbrobinson@fedoraproject.org> 2.6.13-4
- ARM has gperftools

* Wed Jun 19 2013 Fabian Deutsch <fabiand@fedoraproject.org> - 2.6.13-3
- Modify jemalloc patch for s390 compatibility (Thanks sharkcz)

* Fri Jun 07 2013 Fabian Deutsch <fabiand@fedoraproject.org> - 2.6.13-2
- Unbundle jemalloc

* Fri Jun 07 2013 Fabian Deutsch <fabiand@fedoraproject.org> - 2.6.13-1
- Add compile PIE flag (rhbz#955459)
- Update to redis 2.6.13 (rhbz#820919)

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Dec 27 2012 Silas Sewell <silas@sewell.org> - 2.6.7-1
- Update to redis 2.6.7

* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4.15-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Sun Jul 08 2012 Silas Sewell <silas@sewell.org> - 2.4.15-2
- Remove TODO from docs

* Sun Jul 08 2012 Silas Sewell <silas@sewell.org> - 2.4.15-1
- Update to redis 2.4.15

* Sat May 19 2012 Silas Sewell <silas@sewell.org> - 2.4.13-1
- Update to redis 2.4.13

* Sat Mar 31 2012 Silas Sewell <silas@sewell.org> - 2.4.10-1
- Update to redis 2.4.10

* Fri Feb 24 2012 Silas Sewell <silas@sewell.org> - 2.4.8-1
- Update to redis 2.4.8

* Sat Feb 04 2012 Silas Sewell <silas@sewell.org> - 2.4.7-1
- Update to redis 2.4.7

* Wed Feb 01 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-4
- Fixed a typo in the spec

* Tue Jan 31 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-3
- Fix .service file, to match config (Type=simple).

* Tue Jan 31 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-2
- Fix .service file, credits go to Timon.

* Thu Jan 12 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-1
- Update to 2.4.6
- systemd unit file added
- Compiler flags changed to compile 2.4.6
- Remove doc/ and Changelog

* Sun Jul 24 2011 Silas Sewell <silas@sewell.org> - 2.2.12-1
- Update to redis 2.2.12

* Fri May 06 2011 Dan Horák <dan[at]danny.cz> - 2.2.5-2
- google-perftools exists only on selected architectures

* Sat Apr 23 2011 Silas Sewell <silas@sewell.ch> - 2.2.5-1
- Update to redis 2.2.5

* Sat Mar 26 2011 Silas Sewell <silas@sewell.ch> - 2.2.2-1
- Update to redis 2.2.2

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Sun Dec 19 2010 Silas Sewell <silas@sewell.ch> - 2.0.4-1
- Update to redis 2.0.4

* Tue Oct 19 2010 Silas Sewell <silas@sewell.ch> - 2.0.3-1
- Update to redis 2.0.3

* Fri Oct 08 2010 Silas Sewell <silas@sewell.ch> - 2.0.2-1
- Update to redis 2.0.2
- Disable checks section for el5

* Sat Sep 11 2010 Silas Sewell <silas@sewell.ch> - 2.0.1-1
- Update to redis 2.0.1

* Sat Sep 04 2010 Silas Sewell <silas@sewell.ch> - 2.0.0-1
- Update to redis 2.0.0

* Thu Sep 02 2010 Silas Sewell <silas@sewell.ch> - 1.2.6-3
- Add Fedora build flags
- Send all scriplet output to /dev/null
- Remove debugging flags
- Add redis.conf check to init script

* Mon Aug 16 2010 Silas Sewell <silas@sewell.ch> - 1.2.6-2
- Don't compress man pages
- Use patch to fix redis.conf

* Tue Jul 06 2010 Silas Sewell <silas@sewell.ch> - 1.2.6-1
- Initial package
