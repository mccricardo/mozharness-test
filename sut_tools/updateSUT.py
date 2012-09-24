#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import urllib2
import sys
import time
import os
from sut_lib import connect

# Constants
target_version = "1.13"
apkfilename = "sutAgentAndroid.apk"
tegra_name = os.getenv('SUT_NAME')
apkFoopyDirPattern =  "/builds/%(tegra_name)s"
apkFoopyDir = apkFoopyDirPattern % {'tegra_name': tegra_name}
version_pattern = 'SUTAgentAndroid Version %s'

RETCODE_SUCCESS = 0
RETCODE_APK_DL_FAILED = 1
RETCODE_REVERIFY_FAILED = 2
RETCODE_REVERIFY_WRONG = 3

def isVersionCorrect(dm=None, ver=None):
    assert ver is not None or dm is not None # We allow only one to be set

    if not ver:
        ver = version(dm)

    return ver == (version_pattern % target_version)

def doUpdate(dm):
    _oldDebug = dm.debug
    print "INFO: updateSUT.py: We're going to try to install SUTAgentAndroid Version %s" % target_version
    try:
         data = download_apk()
    except Exception, e:
         print "Automation Error: updateSUT.py: We have failed to retrieve the SUT Agent. %s" % str(e)
         return RETCODE_APK_DL_FAILED
    dm.sendCMD(['push /mnt/sdcard/%s %s\r\n' % (apkfilename, str(len(data))), data], newline=False)
    dm.debug = 5
    dm.sendCMD(['updt com.mozilla.SUTAgentAndroid /mnt/sdcard/%s' % apkfilename])
    # XXX devicemanager.py might need to close the sockets so we won't need these 2 steps
    if dm._sock:
        dm._sock.close()
    dm._sock = None
    dm = None
    ver = None
    tries = 0
    while tries < 5:
        try:
            dm = connect(tegra_name, sleep=90)
            break
        except:
            tries += 1
            print "Automation Error: updateSUT.py: We have tried to connect %s time(s) after trying to update." % tries

    try:
        ver = version(dm)
    except Exception, e:
        print "Automation Error: updateSUT.py: We should have been able to get the version"
        print "Automation Error: updateSUT.py: %s" % e
        return RETCODE_REVERIFY_FAILED

    dm.debug = _oldDebug # Restore it

    if ver == None:
        print "Automation Error: updateSUT.py: We should have been able to connect and determine the version."
        return RETCODE_REVERIFY_FAILED
    elif not isVersionCorrect(ver=ver):
        print "Automation Error: updateSUT.py: We should have had the %s version but instead we have %s" % \
              (target_version, ver)
        return RETCODE_REVERIFY_WRONG
    else:
        print "INFO: updateSUT.py: We're now running %s" % ver
        return RETCODE_SUCCESS

def main(device):
    dm = connect(device)

    if not isVersionCorrect(dm=dm):
        return doUpdate(dm)
    else:
        # The SUT Agent was already up-to-date
        return RETCODE_SUCCESS

def version(dm):
    ver = dm.sendCMD(['ver']).split("\n")[0]
    print "INFO: updateSUT.py: We're running %s" % ver
    return ver

def download_apk():
    url = 'http://build.mozilla.org/talos/mobile/sutAgentAndroid.%s.apk' % target_version
    print "INFO: updateSUT.py: We're downloading the apk: %s" % url
    req = urllib2.Request(url)
    try:
        f = urllib2.urlopen(req)
    except urllib2.URLError, e:
        reason = getattr(e, "reason", "SUT-Undef")
        code = getattr(e, "code", "SUT-Undef")
        raise Exception("Automation Error: updateSUT.py: code: %s; reason: %s" % (code, reason))

    local_file_name = os.path.join(apkFoopyDir, apkfilename)
    local_file = open(local_file_name, 'wb')
    local_file.write(f.read())
    local_file.close()
    f = open(local_file_name, 'rb')
    data = f.read()
    f.close()
    return data

if __name__ == '__main__':
    if (len(sys.argv) <> 2):
        if os.getenv('SUT_NAME') in (None, ''):
            print "usage: updateSUT.py [tegra name]"
            print "   Must have $SUT_NAME set in environ to omit tegra name"
            sys.exit(1)
        else:
            print "INFO: Using tegra '%s' found in env variable" % tegra_name
    else:
        tegra_name = sys.argv[1]
        apkFoopyDir = apkFoopyDirPattern % {'tegra_name': tegra_name}

    # Exit 5 if an error, for buildbot RETRY
    ret = 0
    if main(tegra_name): ret = 5
    sys.stdout.flush()
    sys.exit(ret)
else:
    if tegra_name in (None, ''):
        raise ImportError("To use updateSUT.py non-standalone you need SUT_NAME defined in environment")
    else:
        print "DEBUG: updateSUT: Using tegra '%s' found in env variable" % tegra_name