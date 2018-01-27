#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from urllib.parse import urlparse
import re
import datetime
import glob
import logging
import os
import shutil
import sys
import subprocess
import tempfile

from paramiko.client import SSHClient, AutoAddPolicy


# Set up logging
logging.basicConfig(
    format="format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%m-%d %H:%M:%S",
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

logger.addHandler(logging.StreamHandler(sys.stdout))


PREFIX = "back-"


class SSHError(Exception):
    pass


class AbstractFs:

    def open(self, filename, mode="r"):
        raise NotImplementedError(self)

    def rename(self, src, dest):
        raise NotImplementedError(self)

    def exists(self, path):
        raise NotImplementedError(self)

    def remove(self, path):
        raise NotImplementedError(self)

    def symlink(self, src, dest):
        raise NotImplementedError(self)

    def glob(self, pattern):
        raise NotImplementedError(self)

    def rmtree(self, path):
        raise NotImplementedError(self)

    def close(self):
        raise NotImplementedError(self)

    def copy(self, src, dst):
        raise NotImplementedError(self)


class Local(AbstractFs):

    def open(self, filename, mode="r"):
        return open(filename, mode=mode)

    def rename(self, src, dest):
        return os.rename(src, dest)

    def exists(self, path):
        return os.path.exists(path)

    def remove(self, path):
        return os.remove(path)

    def symlink(self, src, dest):
        return os.symlink(src, dest)

    def glob(self, pattern):
        return glob.glob(pattern)

    def rmtree(self, path):
        return shutil.rmtree(path)

    def close(self):
        pass


class SSH(AbstractFs):

    policy = AutoAddPolicy
    recv_size = 1024

    _ssh = None
    _basepath = "/"

    def __init__(self, host, username="expo", basepath=None):
        logger.debug("Creating SSH client")
        self._ssh = SSHClient()
        self._ssh.load_system_host_keys()

        logger.debug("Setting %s for missing host keys", self.policy.__name__)
        self._ssh.set_missing_host_key_policy(self.policy)

        logger.info(
            "Connecting to %s%s%s",
            "{}@".format(username) or '',
            host,
            ":{}".format(basepath) or ''
        )
        self._ssh.connect(host, username=username, compress="true")

        if basepath:
            logger.info("Use basepath %s", basepath)
            self._basepath = basepath

    def _collect_stream(self, channel, recv_fn):
        content = ""
        buffer = None

        while True:
            buffer = recv_fn(self.recv_size)
            content += buffer.decode('utf-8')

            if len(buffer) == 0:
                break

        return content

    def _exec(self, cmd):
        channel = self._ssh.get_transport().open_session()
        channel.exec_command(cmd)

        stdout = self._collect_stream(channel, channel.recv)
        stderr = self._collect_stream(channel, channel.recv_stderr)

        exit_code = channel.recv_exit_status()

        logger.debug(stdout)

        if exit_code != 0:
            logger.error(stderr)
            logger.error("Command %s failed with exit code %s", cmd, exit_code)

        return exit_code, stdout, stderr

    def touch(self, filename):
        logger.debug("Touching file %s", filename)
        self._exec('touch "{}"'.format(filename))

    def rename(self, remote_src, remote_dest):
        logger.debug("Renaming %s into %s", remote_src, remote_dest)

        exit_code, _, _ = self._exec('mv "{}" "{}"'.format(remote_src, remote_dest))

        if exit_code != 0:
            raise SSHError("Failed renaming {} into {}".format(remote_src, remote_dest))

    def exists(self, path):
        logger.debug("Checking if %s exists...", path)
        exit_code, _, _ = self._exec('test -f "{}"'.format(path))
        exists = exit_code == 0

        logger.debug("File %s does%s exists.", path, "" if exists else " not")
        return exists

    def copy(self, remote_src, local_dst):
        exit_code, remote_content, _ = self._exec('cat "{}"'.format(remote_src))

        if exit_code != 0:
            raise SSHError("Cannot read from %s", remote_src)

        with open(local_dst, "w") as f:
            f.write(remote_content)

    # def remove(self, path):
    #     return os.remove(path)

    def symlink(self, remote_src, remote_dest, relative_to=None):
        if relative_to:
            remote_src = remote_src.replace(relative_to, ".")

        logger.debug("Symlinking %s to %s", remote_src, remote_dest)

        exit_code, _, _ = self._exec('ln -sf "{}" "{}"'.format(remote_src, remote_dest))

        if exit_code != 0:
            raise SSHError("Failed symlinking {} to {}".format(remote_src, remote_dest))

    def glob(self, remote_path, regex_str):
        logger.debug("Globbing %s for %s", remote_path, regex_str)

        exit_code, remote_content, _ = self._exec('ls "{}"'.format(remote_path))

        if exit_code != 0:
            raise SSHError("Failed listing {}".format(remote_path))

        regex = re.compile(regex_str)

        entries = (e for e in remote_content.split() if regex.match(e))
        entries = (os.path.join(remote_path, e) for e in entries)

        return entries

    def rmtree(self, remote_path):
        logger.debug("Removing tree %s", remote_path)

        exit_code, _, _ = self._exec('rm -rf "{}"'.format(remote_path))

        if exit_code != 0:
            raise SSHError("Failed removing {}".format(remote_path))

    def close(self):
        logger.debug("Closing SSH connection...")
        self._ssh.close()

        logger.debug("Connection closed.")


class URI:

    user = None
    original = None
    uri = None
    host = None
    path = None

    def __init__(self, uri_str):
        parts = os.path.abspath(uri_str).split('@')[:2]

        if len(parts) == 2:
            user, uri = parts
        elif len(parts) == 1:
            user = None
            uri = parts[0]
        else:
            raise ValueError("Malformed URI {}".format(uri_str))

        parsed_uri = urlparse(uri)

        self.original = uri_str
        self.user = user
        self.uri = uri
        self.host = parsed_uri.scheme
        self.path = parsed_uri.path

    def __repr__(self):
        return self.original

    def join(self, *args):
        new_uri = os.path.join(self.original, *args)

        return URI(new_uri)


if __name__ == "__main__":
    # Check arguments
    if len(sys.argv) != 3:
        print("Wrong arguments: ", sys.argv)
        print("Usage: backup.py <source> <target>")
        sys.exit(1)

    # fs = Local()
    target_path = URI(sys.argv[2])
    host = target_path.host
    basepath = target_path.path

    # Paths
    origin_path = URI(sys.argv[1])
    current_path = target_path.join("current")
    incomplete_path = target_path.join("incomplete")

    fs = SSH(host, basepath=basepath)

    # Check exclude file list
    exclude_filename = os.path.join(basepath, "exclude")

    # Create backup
    now = datetime.datetime.now()

    if not fs.exists(exclude_filename):
        fs.touch(exclude_filename)

    _, exclude_filename_tmp = tempfile.mkstemp()

    fs.copy(exclude_filename, exclude_filename_tmp)

    subprocess.check_call([
        "rsync", "-aPSvz",
        "--delete", "--delete-excluded",
        "--exclude-from={}".format(exclude_filename_tmp),
        "--link-dest={}".format(current_path),
        str(origin_path), str(incomplete_path)
    ])

    os.remove(exclude_filename_tmp)

    # Rename incomplete backup to full backup
    backup_path = target_path.join(PREFIX + now.strftime("%Y-%m-%dT%H_%M_%S"))

    fs.rename(incomplete_path.path, backup_path.path)

    if fs.exists(current_path):
        fs.remove(current_path)
    fs.symlink(backup_path.path, current_path.path, relative_to=target_path.path)

    # Start scanning
    logger.info("Scanning %s ...", target_path)

    targets = {}

    for target_path in fs.glob(target_path.path, "^" + PREFIX + "*"):
        # Normalise target to filename
        target_path = os.path.split(target_path)[1]

        # Extract timestamp and convert to timedelta from now
        timestamp = target_path[len(PREFIX):]
        timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H_%M_%S")

        # Save into targets list
        targets[timestamp] = target_path

    logger.info("...Found %s targets", len(targets))

    # Get keys sorted by timedelta
    timestamps = sorted(targets.keys())

    # Exclude most recent target
    last = targets.pop(timestamps.pop())

    logger.info("Excluding most recent target %s", last)

    # Collect hourly targets consuming deltas list
    logger.info("Grouping targets...")

    hourly = {}
    daily = {}
    weekly = {}

    while timestamps:
        timestamp = timestamps.pop()
        target_path = targets.pop(timestamp)
        days = (now - timestamp).days

        if days < 1:
            # Hourly
            hourly[timestamp] = target_path

        elif days < 30:
            # Daily
            daily[timestamp] = target_path

        else:
            # Weekly
            weekly[timestamp] = target_path

    logger.info("...collected %s hourly targets", len(hourly))
    logger.info("...collected %s daily targets", len(daily))
    logger.info("...collected %s weekly targets", len(weekly))

    # Group targets
    logger.info("Finding obsolete targets...")

    group = {}

    for timestamp, target_path in daily.items():
        days = (now - timestamp).days

        group.setdefault(days, []).append(target_path)

    for timestamp, target_path in weekly.items():
        week = timestamp.isocalendar()[:2]

        group.setdefault(week, []).append(target_path)

    # Make target purge list
    purge = []

    for week, targets in group.items():
        if len(targets) > 1:
            purge.extend(sorted(targets)[:-1])

    logger.info("%s targets to be purged", len(purge))

    # Purge targets starting from the oldest one
    for target_path in sorted(purge):
        logger.info("..purging target %s", target_path)

        fs.rmtree(os.path.join(target_path, target_path))

    # End
    fs.close()
    logger.info("End.")
