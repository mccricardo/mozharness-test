#!/usr/bin/python
"""
signing-server [options] server.ini
"""
import os, site
# Modify our search path to find our modules
site.addsitedir(os.path.join(os.path.dirname(__file__), "../../lib/python"))
import shutil
import signal
import multiprocessing
import socket
import tempfile

import logging
import logging.handlers

from util.file import sha1sum as sync_sha1sum, safe_unlink
from util.file import load_config
from signing.server import SigningServer, create_server, run_signscript

# External dependencies
import daemon

import gevent.backdoor
from gevent.event import Event

log = logging.getLogger(__name__)

# We need to ignore SIGINT (KeyboardInterrupt) in the children so that the
# parent exits properly.
def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

_sha1sum_worker_pool = None
def sha1sum(fn):
    "Non-blocking sha1sum. Will calculate sha1sum of fn in a subprocess"
    result = _sha1sum_worker_pool.apply_async(sync_sha1sum, args=(fn,))
    # Most of the time we'll complete pretty fast, so don't need to sleep very
    # long
    sleep_time = 0.1
    while not result.ready():
        gevent.sleep(sleep_time)
        # Increase the time we sleep next time, up to a maximum of 5 seconds
        sleep_time = min(5, sleep_time*2)
    return result.get()

def run(config_filename, passphrases):
    log.info("Running with pid %i", os.getpid())

    # Start our worker pool now, before we create our sockets for the web app
    # otherwise the workers inherit the file descriptors for the http(s)
    # socket and we have problems shutting down cleanly
    global _sha1sum_worker_pool
    if not _sha1sum_worker_pool:
        _sha1sum_worker_pool = multiprocessing.Pool(None, init_worker)
    app = None
    listener = None
    server = None
    backdoor = None
    handler = None
    backdoor_state = {}
    while True:
        log.info("Loading configuration")
        config = load_config(config_filename)
        if not app:
            app = SigningServer(config, passphrases)
        else:
            app.load_config(config)

        listen_addr = (config.get('server', 'listen'), config.getint('server', 'port'))
        if not listener or listen_addr != listener.getsockname():
            if listener and server:
                log.info("Listening address has changed, stopping old wsgi server")
                log.debug("Old address: %s", listener.getsockname())
                log.debug("New address: %s", listen_addr)
                server.stop()
            listener = gevent.socket.socket()
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(listen_addr)
            listener.listen(256)

        server = create_server(app, listener, config)

        backdoor_state['server'] = server
        backdoor_state['app'] = app

        if config.has_option('server', 'backdoor_port'):
            backdoor_port = config.getint('server', 'backdoor_port')
            if not backdoor or backdoor.server_port != backdoor_port:
                if backdoor:
                    log.info("Stopping old backdoor on port %i", backdoor.server_port)
                    backdoor.stop()
                log.info("Starting backdoor on port %i", backdoor_port)
                backdoor = gevent.backdoor.BackdoorServer(
                        ('127.0.0.1', backdoor_port),
                        locals=backdoor_state)
                gevent.spawn(backdoor.serve_forever)

        # Handle SIGHUP
        # Create an event to wait on
        # Our SIGHUP handler will set the event, allowing us to continue
        sighup_event = Event()
        h = gevent.signal(signal.SIGHUP, lambda e: e.set(), sighup_event)
        if handler:
            # Cancel our old handler
            handler.cancel()
        handler = h
        log.info("Serving on %s", repr(server))
        try:
            gevent.spawn(server.serve_forever)
            # Wait for SIGHUP
            sighup_event.wait()
        except KeyboardInterrupt:
            break
    log.info("pid %i exiting normally", os.getpid())

def setup_logging(options):
    if options.logfile:
        handler = logging.handlers.RotatingFileHandler(options.logfile,
                maxBytes=1024**2, backupCount=10)
    else:
        handler = logging.StreamHandler()

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(options.loglevel)

if __name__ == '__main__':
    from optparse import OptionParser
    import getpass
    import sys

    parser = OptionParser(__doc__)
    parser.set_defaults(
            loglevel=logging.INFO,
            logfile=None,
            daemonize=False,
            pidfile="signing.pid",
            action="run",
            )
    parser.add_option("-v", dest="loglevel", action="store_const",
            const=logging.DEBUG, help="be verbose")
    parser.add_option("-q", dest="loglevel", action="store_const",
            const=logging.WARNING, help="be quiet")
    parser.add_option("-l", dest="logfile", help="log to this file instead of stderr")
    parser.add_option("-d", dest="daemonize", action="store_true",
            help="daemonize process")
    parser.add_option("--pidfile", dest="pidfile")
    parser.add_option("--stop", dest="action", action="store_const", const="stop")
    parser.add_option("--reload", dest="action", action="store_const", const="reload")
    parser.add_option("--restart", dest="action", action="store_const", const="restart")

    options, args = parser.parse_args()

    if options.action == "stop":
        try:
            pid = int(open(options.pidfile).read())
            os.kill(pid, signal.SIGINT)
        except (IOError,ValueError):
            log.info("no pidfile, assuming process is stopped")
        sys.exit(0)
    elif options.action == "reload":
        pid = int(open(options.pidfile).read())
        os.kill(pid, signal.SIGHUP)
        sys.exit(0)

    if len(args) != 1:
        parser.error("Need just one server.ini file to read")

    config = load_config(args[0])
    if not config:
        parser.error("Error reading config file: %s" % args[0])

    setup_logging(options)

    # Read passphrases
    passphrases = {}
    formats = [f.strip() for f in config.get('signing', 'formats').split(',')]
    for format_ in formats:
        passphrase = getpass.getpass("%s passphrase: " % format_)
        if not passphrase:
            passphrase = None
        try:
            log.info("checking %s passphrase", format_)
            src = config.get('signing', 'testfile_%s' % format_)
            tmpdir = tempfile.mkdtemp()
            dst = os.path.join(tmpdir, os.path.basename(src))
            shutil.copyfile(src, dst)
            if 0 != run_signscript(config.get('signing', 'signscript'), src, dst, src, format_, passphrase, max_tries=2):
                log.error("Bad passphrase: %s", open(dst + ".out").read())
                assert False
            log.info("%s passphrase OK", format_)
            passphrases[format_] = passphrase
        finally:
            shutil.rmtree(tmpdir)

    # Possibly stop the old instance
    # We do this here so that we don't have to wait for the user to enter
    # passwords before stopping/starting the new instance.
    if options.action == 'restart':
        try:
            pid = int(open(options.pidfile).read())
            log.info("Killing old server pid:%i", pid)
            os.kill(pid, signal.SIGINT)
            # Wait for it to exit
            while True:
                log.debug("Waiting for pid %i to exit", pid)
                # This will raise OSError once the process exits
                os.kill(pid, 0)
                gevent.sleep(1)
        except (IOError, ValueError):
            log.info("no pidfile, assuming process is stopped")
        except OSError:
            # Process is done
            log.debug("pid %i has exited", pid)

    if options.daemonize:
        curdir = os.path.abspath(os.curdir)
        pidfile = os.path.abspath(options.pidfile)
        logfile = os.path.abspath(options.logfile)

        daemon_ctx = daemon.DaemonContext(
                # We do our own signal handling in run()
                signal_map={},
                working_directory=curdir,
                )
        daemon_ctx.open()

        # gevent needs to be reinitialized after the hardcore forking action
        gevent.reinit()
        open(pidfile, 'w').write(str(os.getpid()))

        # Set up logging again! createDaemon has closed all our open file
        # handles
        setup_logging(options)

    try:
        run(args[0], passphrases)
    except:
        log.exception("error running server")
        raise
    finally:
        try:
            if options.daemonize:
                daemon_ctx.close()
                safe_unlink(pidfile)
            log.info("exiting")
        except:
            log.exception("error shutting down")