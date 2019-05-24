#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
""" log

This exports:
    - LogCollector is a class inherited from collector.SwitchCollector
        that collects each traffic's log.
"""

__all__ = [
    "LogCollector"
]

import re

import collector
import context
import sql
import broker
import traffic


class LogCollector(collector.SwitchCollector):
    """ Collects each traffic's log.
        Use delimiter log to separate traffic's logs.
        After it has collected one traffic's log, it query database to insert the log.

    Arguments:
        - ctx: A Context object.

    Attributes:
        Same as Arguments.
    """
    def __init__(self, ctx):
        """ Create a LogCollector object.
            Initialize SwitchCollector with delimiter log.
            Subscribe itself to RAW_LOG and RESET.
        """
        self._ctx = ctx
        self._unique_id_pattern = re.compile(
            r'\[unique_id "([^\]]+)"\]'
        )
        super(LogCollector, self).__init__(
            self._ctx.delimiter.get_delimiter_log(),
            self._ctx.delimiter.get_delimiter_log(), 
            save_entire_line = True)
        self._reset()

        self._ctx.broker.subscribe(broker.TOPICS.RAW_LOG, self)
        self._ctx.broker.subscribe(broker.TOPICS.RESET, self._reset)

    def __del__(self):
        self._ctx.broker.unsubscribe(broker.TOPICS.RAW_LOG, self)
        self._ctx.broker.subscribe(broker.TOPICS.RESET, self._reset)

    def _get_unique_id(self, line):
        return self._unique_id_pattern.search(line).group(1)

    def _execute(self, collected_buffer, start_result, end_result):
        key = start_result.group(1)
        if key != end_result.group(1):
            return
        # remove delimiter
        collected_buffer = collected_buffer.splitlines()
        if len(collected_buffer) < 2:
            self._ctx.broker.publish(broker.TOPICS.WARNING, "log error")
            return

        log_buffer = []
        # Remove logs generated by dummy request
        start_unique_id = '[unique_id "{unique_id}"]'.format(
            unique_id = self._get_unique_id(collected_buffer[0])
        )
        end_unique_id = '[unique_id "{unique_id}"]'.format(
            unique_id = self._get_unique_id(collected_buffer[-1])
        )
        for line in collected_buffer:
            if start_unique_id not in line and end_unique_id not in line:
                log_buffer.append(line)

        if log_buffer:
            self._ctx.broker.publish(
                broker.TOPICS.SQL_COMMAND,
                sql.SQL_INSERT_LOG,
                "\n".join(log_buffer),
                key,
            )

