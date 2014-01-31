from __future__ import with_statement

import os
from os import path
import re
import shutil
import sys
from urllib import urlretrieve
from urllib2 import urlopen
from urlparse import urljoin

from release.platforms import getPlatformLocales, buildbot2ftp
from release.paths import makeCandidatesDir
from util.commands import run_cmd
from util.hg import mercurial, update
from util.paths import windows2msys, msys2windows
from util.retry import retry

import logging
log = logging.getLogger(__name__)


def getMakeCommand(usePymake, absSourceRepoPath):
    if usePymake:
        return [sys.executable, "%s/build/pymake/make.py" % absSourceRepoPath]
    return ["make"]


def getAllLocales(appName, sourceRepo, rev="default",
                  hg="https://hg.mozilla.org"):
    localeFile = "%s/raw-file/%s/%s/locales/all-locales" % \
        (sourceRepo, rev, appName)
    url = urljoin(hg, localeFile)
    try:
        sl = urlopen(url).read()
    except:
        log.error("Failed to retrieve %s", url)
        raise
    return sl


def compareLocales(repo, locale, l10nRepoDir, localeSrcDir, l10nIni,
                   revision="default", merge=True):
    retry(mercurial, args=(repo, "compare-locales"))
    update("compare-locales", revision=revision)
    mergeDir = path.join(localeSrcDir, "merged")
    if path.exists(mergeDir):
        log.info("Deleting %s" % mergeDir)
        shutil.rmtree(mergeDir)
    run_cmd(["python", path.join("compare-locales", "scripts",
                                 "compare-locales"),
             "-m", mergeDir,
             l10nIni,
             l10nRepoDir, locale],
            env={"PYTHONPATH": path.join("compare-locales", "lib")})


def l10nRepackPrep(sourceRepoName, objdir, mozconfigPath, srcMozconfigPath,
                   l10nBaseRepoName, makeDirs, localeSrcDir, env,
                   tooltoolManifest=None, tooltool_script=None,
                   tooltool_urls=None):
    if not path.exists(l10nBaseRepoName):
        os.mkdir(l10nBaseRepoName)

    if srcMozconfigPath:
        shutil.copy(path.join(sourceRepoName, srcMozconfigPath),
                    path.join(sourceRepoName, ".mozconfig"))
    else:
        shutil.copy(mozconfigPath, path.join(sourceRepoName, ".mozconfig"))
    with open(path.join(sourceRepoName, ".mozconfig"), "a") as mozconfig:
        mozconfig.write("ac_add_options --enable-official-branding")

    run_cmd(["mkdir", "-p", "l10n"])

    if tooltoolManifest:
        cmd = ['scripts/scripts/tooltool/fetch_and_unpack.sh',
               os.path.join(sourceRepoName, tooltoolManifest),
               tooltool_urls[0],  # TODO: pass all urls when tooltool ready
               tooltool_script, 'setup.sh']
        run_cmd(cmd)

    absSourceRepoPath = os.path.join(os.getcwd(), sourceRepoName)
    make = getMakeCommand(env.get("USE_PYMAKE"), absSourceRepoPath)
    run_cmd(make + ["-f", "client.mk", "configure"], cwd=sourceRepoName,
            env=env)
    # we'll get things like (config, tier_base) for Firefox releases
    # and (mozilla/config, mozilla/tier_base) for Thunderbird releases
    for dir in makeDirs:
        if path.basename(dir).startswith("tier"):
            run_cmd(make + [path.basename(dir)],
                    cwd=path.join(sourceRepoName, objdir, path.dirname(dir)),
                    env=env)
        else:
            run_cmd(make,
                    cwd=path.join(sourceRepoName, objdir, dir),
                    env=env)


def repackLocale(locale, l10nRepoDir, l10nBaseRepo, revision, localeSrcDir,
                 l10nIni, compareLocalesRepo, env, merge=True,
                 productName=None, platform=None,
                 version=None, partialUpdates=None,
                 buildNumber=None, stageServer=None):
    repo = "/".join([l10nBaseRepo, locale])
    localeDir = path.join(l10nRepoDir, locale)
    retry(mercurial, args=(repo, localeDir))
    update(localeDir, revision=revision)

    mozillaDir = ''
    if 'thunderbird' in productName:
        mozillaDir = 'mozilla/'

    # split on \\ since we care about the absSourceRepoPath for pymake, which
    # is windows.
    absSourceRepoPath = os.path.join(os.getcwd(), localeSrcDir.split("\\")[0])
    use_pymake = env.get("USE_PYMAKE", False)
    make = getMakeCommand(use_pymake, absSourceRepoPath)

    env["AB_CD"] = locale
    env["LOCALE_MERGEDIR"] = path.abspath(path.join(localeSrcDir, "merged"))
    if sys.platform.startswith('win'):
        if use_pymake:
            env["LOCALE_MERGEDIR"] = msys2windows(env["LOCALE_MERGEDIR"])
        else:
            env["LOCALE_MERGEDIR"] = windows2msys(env["LOCALE_MERGEDIR"])
    if sys.platform.startswith('darwin'):
        env["MOZ_PKG_PLATFORM"] = "mac"
    UPLOAD_EXTRA_FILES = []
    nativeDistDir = path.normpath(path.abspath(
        path.join(localeSrcDir, '../../%sdist' % mozillaDir)))
    posixDistDir = windows2msys(nativeDistDir)
    mar = '%s/host/bin/mar' % posixDistDir
    mbsdiff = '%s/host/bin/mbsdiff' % posixDistDir
    if platform.startswith('win'):
        mar += ".exe"
        mbsdiff += ".exe"
    current = '%s/current' % posixDistDir
    previous = '%s/previous' % posixDistDir
    updateDir = 'update/%s/%s' % (buildbot2ftp(platform), locale)
    updateAbsDir = '%s/%s' % (posixDistDir, updateDir)
    current_mar = '%s/%s-%s.complete.mar' % (
        updateAbsDir, productName, version)
    unwrap_full_update = '../../../tools/update-packaging/unwrap_full_update.pl'
    make_incremental_update = '../../tools/update-packaging/make_incremental_update.sh'
    prevMarDir = '../../../../'
    if mozillaDir:
        unwrap_full_update = '../../../../%stools/update-packaging/unwrap_full_update.pl' % mozillaDir
        make_incremental_update = '../../../%stools/update-packaging/make_incremental_update.sh' % mozillaDir
        prevMarDir = '../../../../../'
    env['MAR'] = mar
    env['MBSDIFF'] = mbsdiff

    log.info("Download mar tools")
    if stageServer:
        candidates_dir = makeCandidatesDir(productName, version, buildNumber,
                                           protocol="http", server=stageServer)
        if not path.isfile(msys2windows(mar)):
            marUrl = "%(c_dir)s/mar-tools/%(platform)s/%(mar)s" % \
                dict(c_dir=candidates_dir, platform=platform,
                     mar=path.basename(mar))
            run_cmd(['mkdir', '-p', path.dirname(mar)])
            log.info("Downloading %s to %s", marUrl, mar)
            urlretrieve(marUrl, msys2windows(mar))
            if not sys.platform.startswith('win'):
                run_cmd(['chmod', '755', mar])
        if not path.isfile(msys2windows(mbsdiff)):
            mbsdiffUrl = "%(c_dir)s/mar-tools/%(platform)s/%(mbsdiff)s" % \
                dict(c_dir=candidates_dir, platform=platform,
                     mbsdiff=path.basename(mbsdiff))
            run_cmd(['mkdir', '-p', path.dirname(mbsdiff)])
            log.info("Downloading %s to %s", mbsdiffUrl, mbsdiff)
            urlretrieve(mbsdiffUrl, msys2windows(mbsdiff))
            if not sys.platform.startswith('win'):
                run_cmd(['chmod', '755', mbsdiff])
    else:
        log.warning('stageServer not set. mar tools will *not* be downloaded.')

    compareLocales(compareLocalesRepo, locale, l10nRepoDir, localeSrcDir,
                   l10nIni, revision=revision, merge=merge)
    run_cmd(make + ["installers-%s" % locale], cwd=localeSrcDir, env=env)

    run_cmd(['rm', '-rf', current])
    run_cmd(['mkdir', current])
    run_cmd(['perl', unwrap_full_update, current_mar],
            cwd=path.join(nativeDistDir, 'current'), env=env)
    for oldVersion in partialUpdates:
        prevMar = partialUpdates[oldVersion]['mar']
        if prevMar:
            partial_mar_name = '%s-%s-%s.partial.mar' % (productName, oldVersion,
                                                         version)
            partial_mar = '%s/%s' % (updateAbsDir, partial_mar_name)
            UPLOAD_EXTRA_FILES.append('%s/%s' % (updateDir, partial_mar_name))
            run_cmd(['rm', '-rf', previous])
            run_cmd(['mkdir', previous])
            run_cmd(
                ['perl', unwrap_full_update, '%s/%s' % (prevMarDir, prevMar)],
                cwd=path.join(nativeDistDir, 'previous'), env=env)
            run_cmd(['bash', make_incremental_update, partial_mar, previous,
                    current], cwd=nativeDistDir, env=env)
            if os.environ.get('MOZ_SIGN_CMD'):
                run_cmd(['bash', '-c',
                        '%s -f mar -f gpg "%s"' %
                        (os.environ['MOZ_SIGN_CMD'], partial_mar)],
                        env=env)
                UPLOAD_EXTRA_FILES.append(
                    '%s/%s.asc' % (updateDir, partial_mar_name))
        else:
            log.warning(
                "Skipping partial MAR creation for %s %s" % (oldVersion,
                                                             locale))

    env['UPLOAD_EXTRA_FILES'] = ' '.join(UPLOAD_EXTRA_FILES)
    retry(run_cmd,
          args=(make + ["upload", "AB_CD=%s" % locale], ),
          kwargs={'cwd': localeSrcDir, 'env': env})


def getLocalesForChunk(possibleLocales, chunks, thisChunk):
    if 'en-US' in possibleLocales:
        possibleLocales.remove('en-US')
    possibleLocales = sorted(possibleLocales)
    nLocales = len(possibleLocales)
    for c in range(1, chunks + 1):
        n = nLocales / chunks
        # If the total number of locales isn't evenly divisible by the number
        # of chunks we need to append one more onto some chunks
        if c <= (nLocales % chunks):
            n += 1
        if c == thisChunk:
            return possibleLocales[0:n]
        del possibleLocales[0:n]


def getNightlyLocalesForChunk(appName, sourceRepo, platform, chunks, thisChunk,
                              hg="https://hg.mozilla.org"):
    possibleLocales = getPlatformLocales(
        getAllLocales(appName, sourceRepo, hg=hg),
        (platform,)
    )[platform]
    return getLocalesForChunk(possibleLocales, chunks, thisChunk)
