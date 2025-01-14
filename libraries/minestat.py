# minestat.py - A Minecraft server status checker
# Copyright (C) 2016 Lloyd Dilley
# http://www.dilley.me/
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# -------------------------------
# Modified by Joinemm

import socket
from datetime import datetime


class MineStat:
    NUM_FIELDS = 6  # number of values expected from server
    NUM_FIELDS_BETA = 3  # number of values expected from a 1.8b/1.3 server
    DEFAULT_TIMEOUT = 5  # default TCP timeout in seconds

    def __init__(self, address, port, timeout=DEFAULT_TIMEOUT):
        self.address = address
        self.port = port
        self.online = None  # online or offline?
        self.version = None  # server version
        self.motd = None  # message of the day
        self.current_players = None  # current number of players online
        self.max_players = None  # maximum player capacity
        self.latency = None  # ping time to server in milliseconds

        # Connect to the server and get the data
        byte_array = bytearray([0xFE, 0x01])
        raw_data = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            start_time = datetime.now()
            sock.connect((address, port))
            self.latency = datetime.now() - start_time
            self.latency = int(round(self.latency.total_seconds() * 1000))
            sock.settimeout(None)
            sock.send(byte_array)
            raw_data = sock.recv(512)
            sock.close()
        except Exception:
            self.online = False

        # Parse the received data
        if raw_data is None or raw_data == "":
            self.online = False
        else:
            data = raw_data.decode("cp437").split("\x00\x00\x00")
            if data and len(data) >= self.NUM_FIELDS:
                self.online = True
                self.version = data[2].replace("\x00", "")
                self.motd = data[3].replace("\x00", "")
                self.current_players = data[4].replace("\x00", "")
                self.max_players = data[5].replace("\x00", "")
            else:
                self.online = False
