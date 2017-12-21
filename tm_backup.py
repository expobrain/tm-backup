#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

import datetime
import glob
import logging
import os
import shutil
import sys


if __name__ == "__main__":
    # Check arguments
    if len(sys.argv) != 3:
        print("Wrong arguments: ", sys.argv)
        print("Usage: backup.py <source> <target>")
        sys.exit(1)

    # Constants
    ORIGIN = sys.argv[1]    # "/home/expo/"
    TARGET = os.path.abspath(sys.argv[2])    # "/media/backups/ubuntu"
    CURRENT = os.path.join(TARGET, "current")
    INCOMPLETE = os.path.join(TARGET, "incomplete")
    PREFIX = "back-"


    # Set up logging
    logger = logging.getLogger(__name__)

    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.INFO)

    # Check exclude file list
    exclude_filename = os.path.join(TARGET, "exclude")

    # Create backup
    now = datetime.datetime.now()

    target = os.path.join(
        TARGET, PREFIX + now.strftime("%Y-%m-%dT%H_%M_%S"))

    if not os.path.exists(exclude_filename):
        with open(exclude_filename, "w+"):
            pass

    if os.system(
            "rsync -aPSvz "
            "--delete --delete-excluded "
            "--exclude-from={exclude} "
            "--link-dest={current} "
            "{origin} {incomplete}"
            .format(target=TARGET, origin=ORIGIN, exclude=exclude_filename,
                    current=CURRENT, incomplete=INCOMPLETE)):

        raise RuntimeError

    os.rename(INCOMPLETE, target)

    if os.path.exists(CURRENT):
        os.remove(CURRENT)
    os.symlink(os.path.relpath(target, TARGET), CURRENT)

    # Start scanning
    logger.info("Scanning %s ...", TARGET)

    targets = {}

    for target in glob.glob(os.path.join(TARGET, PREFIX + "*")):
        # Normalise target to filename
        target = os.path.split(target)[1]

        # Extract timestamp and convert to timedelta form now
        timestamp = target[len(PREFIX):]
        timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H_%M_%S")

        # Save into targets list
        targets[timestamp] = target

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
        target = targets.pop(timestamp)
        days = (now - timestamp).days

        if days < 1:
            # Hourly
            hourly[timestamp] = target

        elif days < 30:
            # Daily
            daily[timestamp] = target

        else:
            # Weekly
            weekly[timestamp] = target

    logger.info("...collected %s hourly targets", len(hourly))
    logger.info("...collected %s daily targets", len(daily))
    logger.info("...collected %s weekly targets", len(weekly))

    # Group targets
    logger.info("Finding obsolete targets...")

    group = {}

    for timestamp, target in daily.items():
        days = (now - timestamp).days

        group.setdefault(days, []).append(target)


    for timestamp, target in weekly.items():
        week = timestamp.isocalendar()[:2]

        group.setdefault(week, []).append(target)

    # Make target purge list
    purge = []

    for week, targets in group.items():
        if len(targets) > 1:
            purge.extend(sorted(targets)[:-1])

    logger.info("%s targets to be purged", len(purge))

    # Purge targets starting from the oldest one
    for target in sorted(purge):
        logger.info("..purging target %s", target)

        shutil.rmtree(os.path.join(TARGET, target))

    # End
    logger.info("End.")
