#
# Fedora spec file for redis
#
# License: MIT
# http://opensource.org/licenses/MIT
#
# Please preserve changelog entries
#

# Tests fail in mock, not in local build.
%global with_tests 1

# Commit IDs for the (unversioned) redis-doc repository
# https://fedoraproject.org/wiki/Packaging:SourceURL "Commit Revision"
%global doc_commit abfe8e0698564af7260b4c1a0ea4d21424d14a88
%global short_doc_commit %(c=%{doc_commit}; echo ${c:0:7})

# %%{rpmmacrodir} not usable on EL-6
%global macrosdir %(d=%{_rpmconfigdir}/macros.d; [ -d $d ] || d=%{_sysconfdir}/rpm; echo $d)

Name:              redis5
Version:           5.0.13
Release:           1%{?dist}
Summary:           A persistent key-value database
# redis, linenoise, lzf, hiredis are BSD
# lua is MIT
License:           BSD and MIT
URL:               https://redis.io
Source0:           http://download.redis.io/releases/redis-%{version}.tar.gz
Source1:           redis.logrotate
Source2:           redis-sentinel.service
Source3:           redis.service
Source4:           redis-sentinel.init
Source5:           redis.init
Source6:           redis-shutdown
Source7:           redis-limit-systemd
Source8:           redis-limit-init
Source9:           macros.redis
Source10:          https://github.com/antirez/redis-doc/archive/%{doc_commit}/redis-doc-%{short_doc_commit}.tar.gz

# To refresh patches:
# tar xf redis-xxx.tar.gz && cd redis-xxx && git init && git add . && git commit -m "%%{version} baseline"
# git am %%{patches}
# Then refresh your patches
# git format-patch HEAD~<number of expected patches>
# Update configuration for Fedora
# https://github.com/antirez/redis/pull/3491 - man pages
Patch0001:         0001-1st-man-pageis-for-redis-cli-redis-benchmark-redis-c.patch
# https://github.com/antirez/redis/pull/3494 - symlink
Patch0002:         0002-install-redis-check-rdb-as-a-symlink-instead-of-dupl.patch
BuildRequires:     gcc
%if 0%{?with_tests}
BuildRequires:     procps-ng
BuildRequires:     tcl
%endif
BuildRequires:     systemd
# Required for redis-shutdown
Requires:          /bin/awk
Requires:          logrotate
Requires(pre):     shadow-utils
Requires(post):    systemd
Requires(preun):   systemd
Requires(postun):  systemd
Provides:          bundled(hiredis)
Provides:          bundled(jemalloc)
Provides:          bundled(lua-libs)
Provides:          bundled(linenoise)
Provides:          bundled(lzf)
Provides:          redis = %{version}-%{release}
Provides:          redis%{?_isa} = %{version}-%{release}
Conflicts:         redis < %{version}

%global redis_modules_abi 1
%global redis_modules_dir %{_libdir}/redis/modules
Provides:          redis(modules_abi)%{?_isa} = %{redis_modules_abi}

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

%package           devel
Summary:           Development header for Redis module development
# Header-Only Library (https://fedoraproject.org/wiki/Packaging:Guidelines)
Provides:          redis-static = %{version}-%{release}

%description       devel
Header file required for building loadable Redis modules. Detailed
API documentation is available in the redis-doc package.

%package           doc
Summary:           Documentation for Redis including man pages
License:           CC-BY-SA
BuildArch:         noarch

%description       doc
Manual pages and detailed documentation for many aspects of Redis use,
administration and development.

%prep
%autosetup -n redis-%{version} -a 10 -p 1
mv redis-doc-%{doc_commit} doc

mv deps/lua/COPYRIGHT    COPYRIGHT-lua
mv deps/hiredis/COPYING  COPYING-hiredis

# Configuration file changes
sed -i -e 's|^logfile .*$|logfile /var/log/redis/redis.log|g' redis.conf
sed -i -e 's|^logfile .*$|logfile /var/log/redis/sentinel.log|g' sentinel.conf
sed -i -e 's|^dir .*$|dir /var/lib/redis|g' redis.conf

# Module API version safety check
api=`sed -n -e 's/#define REDISMODULE_APIVER_[0-9][0-9]* //p' src/redismodule.h`
if test "$api" != "%{redis_modules_abi}"; then
   : Error: Upstream API version is now ${api}, expecting %%{redis_modules_abi}.
   : Update the redis_modules_abi macro, the rpmmacros file, and rebuild.
   exit 1
fi

# skip unstable tests
# https://github.com/antirez/redis/issues/5463
sed -e '/unit\/pendingquerybuf/d' -i tests/test_helper.tcl

%global make_flags	DEBUG="" V="echo" LDFLAGS="%{?__global_ldflags}" CFLAGS+="%{optflags} -fPIC" INSTALL="install -p" PREFIX=%{buildroot}%{_prefix}

%build
make %{?_smp_mflags} %{make_flags} all

%install
make %{make_flags} install

# Filesystem.
install -d %{buildroot}%{_sharedstatedir}/redis
install -d %{buildroot}%{_localstatedir}/log/redis
install -d %{buildroot}%{_localstatedir}/run/redis
install -d %{buildroot}%{redis_modules_dir}

# Install logrotate file.
install -pDm644 %{S:1} %{buildroot}%{_sysconfdir}/logrotate.d/redis

# Install configuration files.
install -pDm640 redis.conf %{buildroot}%{_sysconfdir}/redis.conf
install -pDm640 sentinel.conf %{buildroot}%{_sysconfdir}/redis-sentinel.conf

# Install systemd unit files.
mkdir -p %{buildroot}%{_unitdir}
install -pm644 %{S:3} %{buildroot}%{_unitdir}
install -pm644 %{S:2} %{buildroot}%{_unitdir}

# Install systemd limit files (requires systemd >= 204)
install -p -D -m 644 %{S:7} %{buildroot}%{_sysconfdir}/systemd/system/redis.service.d/limit.conf
install -p -D -m 644 %{S:7} %{buildroot}%{_sysconfdir}/systemd/system/redis-sentinel.service.d/limit.conf

# Fix non-standard-executable-perm error.
chmod 755 %{buildroot}%{_bindir}/redis-*

# Install redis-shutdown
install -pDm755 %{S:6} %{buildroot}%{_libexecdir}/redis-shutdown

# Install redis module header
install -pDm644 src/redismodule.h %{buildroot}%{_includedir}/redismodule.h

# Install man pages
man=$(dirname %{buildroot}%{_mandir})
for page in man/man?/*; do
    install -Dpm644 $page $man/$page
done
ln -s redis-server.1 %{buildroot}%{_mandir}/man1/redis-sentinel.1
ln -s redis.conf.5   %{buildroot}%{_mandir}/man5/redis-sentinel.conf.5

# Install documentation and html pages
doc=$(echo %{buildroot}/%{_docdir}/redis)
for page in 00-RELEASENOTES BUGS CONTRIBUTING MANIFESTO; do
    install -Dpm644 $page $doc/$page
done
for page in $(find doc -name \*.md | sed -e 's|.md$||g'); do
    base=$(echo $page | sed -e 's|doc/||g')
    install -Dpm644 $page.md $doc/$base.md
done

# Install rpm macros for redis modules
mkdir -p %{buildroot}%{macrosdir}
install -pDm644 %{S:9} %{buildroot}%{macrosdir}/macros.redis

%check
%if 0%{?with_tests}
# ERR Active defragmentation cannot be enabled: it requires a Redis server compiled
# with a modified Jemalloc like the one shipped by default with the Redis source distribution
sed -e '/memefficiency/d' -i tests/test_helper.tcl

# https://github.com/antirez/redis/issues/1417 (for "taskset -c 1")
taskset -c 1 make %{make_flags} test
make %{make_flags} test-sentinel
%endif

%pre
getent group redis &> /dev/null || \
groupadd -r redis &> /dev/null
getent passwd redis &> /dev/null || \
useradd -r -g redis -d %{_sharedstatedir}/redis -s /sbin/nologin \
-c 'Redis Database Server' redis &> /dev/null
exit 0

%post
%systemd_post redis.service
%systemd_post redis-sentinel.service

%preun
%systemd_preun redis.service
%systemd_preun redis-sentinel.service

%postun
%systemd_postun_with_restart redis.service
%systemd_postun_with_restart redis-sentinel.service

%files
%{!?_licensedir:%global license %%doc}
%license COPYING
%config(noreplace) %{_sysconfdir}/logrotate.d/redis
%attr(0640, redis, root) %config(noreplace) %{_sysconfdir}/redis.conf
%attr(0640, redis, root) %config(noreplace) %{_sysconfdir}/redis-sentinel.conf
%dir %attr(0750, redis, redis) %{_libdir}/redis
%dir %attr(0750, redis, redis) %{redis_modules_dir}
%dir %attr(0750, redis, redis) %{_sharedstatedir}/redis
%dir %attr(0750, redis, redis) %{_localstatedir}/log/redis
%exclude %{macrosdir}
%exclude %{_includedir}
%exclude %{_docdir}/redis/*
%{_bindir}/redis-*
%{_libexecdir}/redis-*
%{_mandir}/man1/redis*
%{_mandir}/man5/redis*
%{_unitdir}/redis.service
%{_unitdir}/redis-sentinel.service
%dir %{_sysconfdir}/systemd/system/redis.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/redis.service.d/limit.conf
%dir %{_sysconfdir}/systemd/system/redis-sentinel.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/redis-sentinel.service.d/limit.conf
%dir %attr(0755, redis, redis) %ghost %{_localstatedir}/run/redis

%files devel
%license COPYING
%license COPYRIGHT-lua
%license COPYING-hiredis
%{_includedir}/redismodule.h
%{macrosdir}/*

%files doc
%docdir %{_docdir}/redis
%{_docdir}/redis

%changelog
* Fri Oct 01 2021 Carl George <carl@george.computer> - 5.0.13-1
- Latest upstream

* Tue Apr 21 2020 Carl George <carl@george.computer> - 5.0.9-1
- Latest upstream

* Tue Nov 19 2019 Carl George <carl@george.computer> - 5.0.7-1
- Latest upstream

* Thu Sep 26 2019 Nathan Scott <nathans@redhat.com> - 5.0.6-1
- Upstream 5.0.6 release and redis-doc updates.

* Mon Jul 15 2019 Nathan Scott <nathans@redhat.com> - 5.0.5-2
- Use the (modified) bundled jemalloc for defrag (RHBZ #1725852)

* Thu May 16 2019 Nathan Scott <nathans@redhat.com> - 5.0.5-1
- Upstream 5.0.5 release and redis-doc updates.

* Sat May 11 2019 Nathan Scott <nathans@redhat.com> - 5.0.4-2
- Obsolete redis-trib - functionality now in redis-cli(1)
- Remove old chkconfig support, all systemd platforms now

* Wed Mar 20 2019 Carl George <carl@george.computer> - 5.0.4-1
- Latest upstream (including docs)
- Sync patches with Fedora
- Fix sentinel.conf logfile line addition (Fedora)

* Thu Dec 13 2018 Carl George <carl@george.computer> - 5.0.3-1
- Latest upstream
- Enable test suite
- Skip unstable pendingquerybuf test

* Wed Nov 28 2018 evitalis <evitalis@users.noreply.github.com> - 5.0.2-1
- Port from Fedora to IUS

* Fri Nov 23 2018 Nathan Scott <nathans@redhat.com> - 5.0.2-1
- Upstream 5.0.2 release and redis-doc updates.

* Thu Nov 08 2018 Nathan Scott <nathans@redhat.com> - 5.0.1-1
- Upstream 5.0.1 release.

* Thu Oct 18 2018 Nathan Scott <nathans@redhat.com> - 5.0.0-1
- Update systemd service files for network-online requirement
- Upstream 5.0.0 release.

* Thu Aug 09 2018 Nathan Scott <nathans@redhat.com> - 4.0.11-1
- Drop the pandoc build dependency, install only markdown.
- Upstream 4.0.11 release.

* Sat Jul 14 2018 Fedora Release Engineering <releng@fedoraproject.org> - 4.0.10-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Mon Jun 25 2018 Remi Collet <rcollet@redhat.com> - 4.0.10-2
- fix License (BSD and MIT)
- add bundled libraries licences
- add information about bundled lzf

* Thu Jun 14 2018 Nathan Scott <nathans@redhat.com> - 4.0.10-1
- Upstream 4.0.10 release.

* Tue Mar 27 2018 Nathan Scott <nathans@redhat.com> - 4.0.9-1
- Upstream 4.0.9 release.

* Fri Feb 09 2018 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 4.0.8-2
- Escape macros in %%changelog

* Wed Feb  7 2018 Nathan Scott <nathans@redhat.com> - 4.0.8-1
- Upstream 4.0.8 release.

* Wed Jan 31 2018 Nathan Scott <nathans@redhat.com> - 4.0.7-1
- Upstream 4.0.7 release.

* Thu Dec  7 2017 Nathan Scott <nathans@redhat.com> - 4.0.6-1
- Upstream 4.0.6 release.

* Fri Dec  1 2017 Remi Collet <remi@remirepo.net> - 4.0.5-1
- Redis 4.0.5 - Released Thu Dec 1 16:03:32 CET 2017
- Upgrade urgency CRITICAL: Redis 4.0.4 fix for PSYNC2 was broken,
  causing the slave to crash when receiving an RDB file from the
  master that contained a duplicated Lua script.

* Fri Dec 01 2017 Nathan Scott <nathans@redhat.com> - 4.0.4-1
- Upstream 4.0.4 release.
- Update to current upstream redis-doc also.
- Fix man page issues (RHBZ #1513594 and RHBZ #1515417).

* Thu Nov 30 2017 Remi Collet <remi@remirepo.net> - 4.0.3-1
- Redis 4.0.3
- fix ownership of /usr/share/doc/redis
- use make_flags for test to avoid rebuild and failure
- fix rpm macro location on EL-6
- add /var/run/redis on EL-6
- add spec file license header
- drop duplicated documentation from main package
- keep man in main page

* Fri Nov 17 2017 Nathan Scott <nathans@redhat.com> - 4.0.2-2
- Install the base modules directories, owned by the main package.

* Tue Oct 31 2017 Nathan Scott <nathans@redhat.com> - 4.0.2-1
- Upstream 4.0.2 release.  (RHBZ #1389592)
- Add redis-devel for loadable module development.
- Add redis-doc for man pages and detailed documentation.
- Provide redis-check-aof as a symlink to redis-server also now.

* Tue Sep 26 2017 Nathan Scott <nathans@redhat.com> - 3.2.11-1
- Upstream 3.2.11 bug-fix-only release
- Switch to using Type=notify for Redis systemd services (RHBZ #1172841)
- Add Provides:bundled hiredis, linenoise, lua-libs clauses (RHBZ #788500)

* Mon Aug 14 2017 Nathan Scott <nathans@redhat.com> - 3.2.10-2
- Add redis-trib based on patch from Sebastian Saletnik.  (RHBZ #1215654)

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.9-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Mon Jul 31 2017 Nathan Scott <nathans@redhat.com> - 3.2.10-1
- Upstream 3.2.10 release
- Ensure both the redis and redis-sentinel service files set correct perms
- Dropped systemd tmpfiles source, handled directly in systemd service files

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.9-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Mon May 29 2017 Nathan Scott <nathans@redhat.com> - 3.2.9-1
- Upstream 3.2.9
- Add RuntimeDirectory=redis to systemd unit file (RHBZ #1454700)
- Mark rundir as %%ghost since it may disappear (tmpfs - #1454700)
- Fix a shutdown failure with Unix domain sockets (RHBZ #1444988)

* Mon Feb 20 2017 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.8-1
- Upstream 3.2.8
- bugfix for #3796 (MIGRATE could cause server crash  after socket error)

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Sat Feb  4 2017 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.7-1
- Upstream 3.2.7 (important security fix)

* Sat Nov 05 2016 Alan Pevec <apevec AT redhat.com> - 3.2.4-2
- Install tmpfiles and /run/redis for legacy configurations

* Mon Sep 26 2016 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.4-1
- Upstream 3.2.4
- Fix buffer overlow (TALOS-2016-0206)

* Wed Sep 14 2016 Remi Collet <remi@fedoraproject.org> - 3.2.3-2
- add missing man pages #1374577
  using patch from https://github.com/antirez/redis/pull/3491
- data and configuration should not be publicly readable #1374700
- remove /var/run/redis with systemd #1374728
- provide redis-check-rdb as a symlink to redis-server #1374736
  using patch from https://github.com/antirez/redis/pull/3494
- move redis-shutdown to libexec

* Thu Aug  4 2016 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.3-1
- Upstream 3.2.3
- Security fix for CVE-2013-7458 (redis-cli history world readable)
- RHBZ#1363670 RHBZ#1363671

* Mon Feb  8 2016 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.6-3
- Fix redis-shutdown to handle password-protected instances shutdown

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 3.0.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Sat Dec 19 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.6-1
- Upstream 3.0.6 (RHBZ#1272281)

* Fri Oct 16 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.5-1
- Upstream 3.0.5
- Fix slave/master replication hanging forever in certain case

* Mon Sep 07 2015 Christopher Meng <rpm@cicku.me> - 3.0.4-1
- Update to 3.0.4

* Sun Aug 30 2015 Christopher Meng <rpm@cicku.me> - 3.0.3-2
- Rebuilt for jemalloc 4.0.0

* Tue Jul 21 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.3-1
- Upstream 3.0.3

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 3.0.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Jun 04 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.2-1
- Upstream 3.0.2 (RHBZ #1228245)
- Fix Lua sandbox escape and arbitrary code execution (RHBZ #1228331)

* Sat May 09 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.1-1
- Upstream 3.0.1 (RHBZ #1208322)

* Tue Apr 14 2015 Remi Collet <remi@fedoraproject.org> - 3.0.0-2
- rotate /var/log/redis/sentinel.log

* Thu Apr  2 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.0-1
- Upstream 3.0.0 (RHBZ #1208322)

* Thu Mar 26 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.19-2
- Fix redis-shutdown on multiple NIC setup (RHBZ #1201237)

* Fri Feb 27 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.19-1
- Upstream 2.8.19 (RHBZ #1175232)
- Fix permissions for tmpfiles (RHBZ #1182913)
- Add limits config files
- Spec cleanups

* Fri Dec 05 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.18-1
- Upstream 2.8.18
- Rebased patches

* Sat Sep 20 2014 Remi Collet <remi@fedoraproject.org> - 2.8.17-1
- Upstream 2.8.17
- fix redis-sentinel service unit file for systemd
- fix redis-shutdown for sentinel
- also use redis-shutdown in init scripts

* Wed Sep 17 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.15-2
- Minor fix to redis-shutdown (from Remi Collet)

* Sat Sep 13 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.15-1
- Upstream 2.8.15 (critical bugfix for sentinel)
- Fix to sentinel systemd service and configuration (thanks Remi)
- Refresh patch management

* Thu Sep 11 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.14-2
- Cleanup spec
- Fix shutdown for redis-{server,sentinel}
- Backport fixes from Remi Collet repository (ie: sentinel working)

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
