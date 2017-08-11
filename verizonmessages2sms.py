#!/usr/bin/env python3
#
# For usage information run with "--help"
#
# Works on Python 2.6 and later, 3 and later
# Requires argparse for Python 2.6 (available from pip)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# Copyright 2017 Kevin Locke <kevin@kevinlocke.name>

"""Convert a Verizon Messages database to SMS Backup XML format."""

from __future__ import with_statement

import argparse
import locale
import logging
import os
import re
import sqlite3
import sys
import time
import uuid
import xml.etree.ElementTree as ET

from contextlib import closing

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

__version__ = "0.1.0"

VERSION_MESSAGE = "%(prog)s " + __version__ + """

Copyright 2017 Kevin Locke <kevin@kevinlocke.name>

VerizonMessages2SMS is free software; you can redistribute it and/or modify
it under the terms of the MIT License."""

_logger = logging.getLogger(__name__)

def _setup_logging(level=None):
    """Initialize the logging framework with a root logger for the console"""
    handler = logging.StreamHandler()
    rootlogger = logging.getLogger()
    rootlogger.addHandler(handler)
    if level is not None:
        rootlogger.setLevel(level)

def _created_on_to_timestamp_ms(created_on):
    """
    Converts the Message CreatedOn column to a millisecond timestamp value.

    CreatedOn is number of 100 nanosecond increments since midnight 0000-01-01.
    Output is number of millisecond increments since midnight 1970-01-01.
    """
    return created_on / 10000 - 62167219200000

def _guess_region():
    """Guess the phonenumbers region"""
    locale.setlocale(locale.LC_ALL, "")
    locale_name = locale.getlocale()[0]
    if locale_name is None:
        return None
    if os.name == "nt":
        # https://msdn.microsoft.com/en-us/library/windows/desktop/dd373814.aspx
        match = re.match("-([A-Z]+)(?:_|$)", locale_name, re.IGNORECASE)
    else:
        # https://www.gnu.org/software/libc/manual/html_node/Locale-Names.html
        match = re.match("^[A-Z]+_([A-Z]+)", locale_name, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1).upper()

def _guess_region_or_warn():
    """Guess the phonenumbers region or print a warning"""
    region = _guess_region()
    if region is None:
        _logger.warning("Unable to guess phone number region.  "
                        "Numbers must start with '+' then country code.")
    else:
        _logger.debug("Assuming phone region is %s", region)
    return region

if phonenumbers is not None:
    def _normalize_phone_num(phonestr, region=None):
        """Normalizes a phone number to E.164 format"""
        phonenum = phonenumbers.parse(phonestr, region)
        return phonenumbers.format_number(phonenum,
                                          phonenumbers.PhoneNumberFormat.E164)
else:
    def _normalize_phone_num(phonestr, region=None):
        """Normalizes a phone number to E.164 format"""
        onlynum = re.sub("[^0-9]+", "", phonestr)
        if len(onlynum) == 10 and region == "US":
            onlynum = "1" + onlynum
        return "+" + onlynum

def _message_row_to_attrs(row, num2name=None, region=None, senders=None):
    """Converts a row from the Message table to sms element attributes"""
    sms_date = _created_on_to_timestamp_ms(row["CreatedOn"])
    sms_time = time.localtime(sms_date / 1000)

    sender = _normalize_phone_num(row["Sender"], region)
    source_type = row["SourceType"]
    if source_type == 3 or (senders is not None and sender in senders):
        # Sent message
        sms_type = "2"
        address = _normalize_phone_num(row["ToAddress"], region)
    else:
        # Received message
        if source_type != 2:
            _logger.warning("Unrecognized SourceType %s", source_type)
        sms_type = "1"
        address = sender

    contact_name = None
    if num2name is not None:
        contact_name = num2name.get(address)
        if contact_name is None:
            _logger.warning("%s did not match any contacts", address)
            contact_name = "(Unknown)"

    return {
        "protocol": "0",
        "address": address,
        "date": str(int(sms_date)),
        "type": sms_type,
        "subject": "null",
        "body": row["Body"],
        "toa": "null",
        "sc_toa": "null",
        "service_center": "null",
        "read": str(row["IsRead"]),
        "status": "-1",
        "locked": str(row["IsLocked"]),
        "date_sent": str(int(sms_date)),
        "readable_date":
            time.strftime("%b %d, %Y %I:%M:%S %p", sms_time).replace(" 0", " "),
        "contact_name": contact_name
    }

def _read_contacts(contacts_file, region=None):
    num2name = {}
    with contacts_file:
        for linenum, line in enumerate(contacts_file):
            if re.match(r"^\s*(?:#|$)", line):
                continue

            lineparts = line.split(None, 1)
            if len(lineparts) < 2:
                _logger.error("Missing name or number on line %d: %s",
                              linenum, line)
                return 1
            number = _normalize_phone_num(lineparts[0], region)
            name = lineparts[1]
            num2name[number] = name
    return num2name

def main(*argv):
    """Entry point for command-line usage."""

    default_db = os.path.expanduser(
        "~\\AppData\\Local\\Packages\\"
        "VerizonWireless.VerizonMessages_40sg4y5zd4vfj\\"
        "LocalState\\Database\\Verizon.db")

    parser = argparse.ArgumentParser(
        usage="%(prog)s [options] <Verizon Messages SQLite DB>",
        description="Convert a Verizon Messages database to SMS Backup XML.",
        # Use raw formatter to avoid mangling version text
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "-c", "--contacts", type=argparse.FileType("r"),
        help="Contacts file (\"num name\" lines)")
    parser.add_argument(
        "-o", "--output", type=argparse.FileType("wb"), default="-",
        help="Output file (default: -)")
    parser.add_argument(
        "-q", "--quiet", action="count",
        help="Decrease verbosity (less detailed output)")
    parser.add_argument(
        "-r", "--region",
        help="Region of phone numbers, for normalization (default from locale)")
    parser.add_argument(
        "-s", "--sender", action="append",
        help="Phone number to always treat as the sender")
    parser.add_argument(
        "-v", "--verbose", action="count",
        help="Increase verbosity (more detailed output)")
    parser.add_argument(
        "-V", "--version", action="version",
        help="Output version and license information",
        version=VERSION_MESSAGE)
    parser.add_argument(
        "messages_db", metavar="Verizon Messages SQLite DB", nargs="?",
        default=default_db, help="Verizon Messages SQLite database file.\n"
        "(default: " + default_db + ")")
    args = parser.parse_args(args=argv[1:])

    if args.output.mode != "wb":
        # argparse.FileType does not reopen stdout
        args.output = os.fdopen(args.output.fileno(), "wb")

    # Set log level based on verbosity requested (default of INFO)
    verbosity = (args.quiet or 0) - (args.verbose or 0)
    _setup_logging(logging.INFO + verbosity * 10)

    if args.region is None:
        args.region = _guess_region_or_warn()
    else:
        args.region = args.region.upper()

    if args.sender is not None:
        args.sender = frozenset(_normalize_phone_num(s, args.region)
                                for s in args.sender)

    if args.contacts is None:
        num2name = None
    else:
        num2name = _read_contacts(args.contacts)

    # sqlite3 creates the file if it does not exist.  Check first.
    with open(args.messages_db, "rb"):
        pass

    with sqlite3.connect(args.messages_db) as conn:
        conn.row_factory = sqlite3.Row
        with closing(conn.cursor()) as cur:
            messages = [
                _message_row_to_attrs(row, num2name, args.region, args.sender)
                for row
                in cur.execute("SELECT * FROM Message")]

    smses = ET.Element("smses", {
        "count": str(len(messages)),
        "backup_set": str(uuid.uuid4()),
        "backup_date": str(int(time.time() * 1000))
    })
    for message in messages:
        ET.SubElement(smses, "sms", message)

    # Match SMS Backup prelude
    args.output.write(
        "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n"
        "<!--File Created By verizonmessages2sms.py {} on {} -->\n"
        "<?xml-stylesheet type=\"text/xsl\" href=\"sms.xsl\"?>\n"
        .format(__version__, time.strftime("%x %X"))
        .encode("utf-8")
    )
    ET.ElementTree(smses).write(args.output, "UTF-8", False)
    return 0

if __name__ == "__main__":
    sys.exit(main(*sys.argv))
