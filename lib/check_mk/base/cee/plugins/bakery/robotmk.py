#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020 Simon Meggle <simon.meggle@elabit.de>

# This file is part of Robotmk
# https://robotmk.org
# https://github.com/simonmeggle/robotmk

# Robotmk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 3.  This file is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# ails.  You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

from typing import Iterable, TypedDict, List
from cmk.utils.exceptions import MKGeneralException
from pathlib import Path
import shutil
import os
import yaml
import re
import copy

from .bakery_api.v1 import (
   OS,
   Plugin,
   PluginConfig,
   Scriptlet,
   WindowsConfigEntry,
   DebStep,
   RpmStep,
   SolStep,
   SystemBinary,
   register,
   quote_shell_string,
   FileGenerator,
   ScriptletGenerator,
   WindowsConfigGenerator,
)


def bake_robotmk(opsys, conf, conf_dir, plugins_dir):
    # ALWAYS (!) make a deepcopy of the conf dict. Even if you do not change
    # anything on it, there are strange changes ocurring while building the
    # packages of OS. A deepcopy solves this completely.
    myconf = copy.deepcopy(conf)
    execution_mode = myconf['execution_mode'][0]
    if opsys not in ['windows', 'linux']:
        raise MKGeneralException(
            "Error in bakery plugin 'robotmk': Robotmk is only supported on Windows and Linux."
        )
    config = RMKConfigAdapter(myconf, opsys, execution_mode)

    # Robotmk RUNNER plugin (async, OS specific)
    if execution_mode == "agent_serial":
        if opsys == "windows":
            # async mode in Windows: write configfile in INI-style, will be converted
            # during installation to YML
            # There the Robotmk terminology needs explanation:
            # - The plugin "cache time" is in fact the "execution interval".
            # - The plugin "timeout" is the max time the plugin is allowed to run
            #   before going stale = "cache time".

            with Path(conf_dir, "check_mk.ini.plugins.%s" %
                      config.os_rmk_runner).open("w") as out:
                out.write(u"    execution %s = async\r\n" %
                          config.os_rmk_runner)
                out.write(u"    cache_age %s = %d\r\n" %
                          (config.os_rmk_runner,
                           config.global_dict['execution_interval']))
                # Kill the plugin before the next async execution will start
                out.write(
                    u"    timeout %s = %d\r\n" %
                    (config.os_rmk_runner, config.global_dict['cache_time']))
                out.write(u"\r\n")
                plugins_dir_async = plugins_dir
        elif opsys == "linux":
            # async mode in Linux: "seconds"-subdir in plugins dir
            plugins_dir_async = Path(
                plugins_dir, "%s" % config.global_dict['execution_interval'])
            plugins_dir_async.mkdir(parents=True, exist_ok=True)
        else:
            raise MKGeneralException(
                "Error in bakery plugin \"%s\": %s\n" %
                ("robotmk", "Robotmk is supported on Windows and Linux only"))

        src = str(
            Path(
                cmk.utils.paths.local_agents_dir).joinpath('plugins').joinpath(
                    RMKConfigAdapter._DEFAULTS['linux']['rmk_runner']))
        dest = str(Path(plugins_dir_async).joinpath(config.os_rmk_runner))

        shutil.copy2(src, dest)

    # II) Robotmk Controller plugin
    src = str(
        Path(cmk.utils.paths.local_agents_dir).joinpath('plugins').joinpath(
            RMKConfigAdapter._DEFAULTS['linux']['rmk_ctrl']))
    dest = str(Path(plugins_dir).joinpath(config.os_rmk_ctrl))
    shutil.copy2(src, dest)

    # I)I) Generate YML config file
    with open(conf_dir + "/robotmk.yml", "w") as robotmk_yml:
        robotmk_yml.write(header)
        yaml.safe_dump(config.cfg_dict,
                       robotmk_yml,
                       line_break=config.os_newline,
                       encoding='utf-8',
                       allow_unicode=True,
                       sort_keys=True)


class RMKConfigAdapter():
    _DEFAULTS = {
        'windows': {
            'newline': "\r\n",
            'robotdir': "C:\\ProgramData\\checkmk\\agent\\robot",
            'rmk_ctrl': 'robotmk.py',
            'rmk_runner': 'robotmk-runner.py'
        },
        'linux': {
            'newline': "\n",
            'robotdir': "/usr/lib/check_mk_agent/robot",
            'rmk_ctrl': 'robotmk.py',
            'rmk_runner': 'robotmk-runner.py'
        },
        'posix': {
            'newline': "\n",
            'robotdir': "/usr/lib/check_mk_agent/robot",
            'rmk_ctrl': 'robotmk.py',
            'rmk_runner': 'robotmk-runner.py'
        },
        'noarch': {
            'cache_time': 900,
        }
    }

    def __init__(self, conf, opsys, execution_mode):
        self.opsys = opsys
        self.os_newline = self.get_os_default('newline')
        self.os_rmk_ctrl = self.get_os_default('rmk_ctrl')
        self.os_rmk_runner = self.get_os_default('rmk_runner')
        self.cfg_dict = {
            'global': {},
            'suites': {},
        }
        global_dict = self.cfg_dict['global']
        suites_dict = self.cfg_dict['suites']
        global_dict['agent_output_encoding'] = conf['agent_output_encoding']
        global_dict['transmit_html'] = conf['transmit_html']
        global_dict['logging'] = conf['logging']
        global_dict['log_rotation'] = conf['log_rotation']
        if 'robotdir' in conf and conf['robotdir'] != {}:
            global_dict['robotdir'] = conf['robotdir']
        else:
            global_dict['robotdir'] = self._DEFAULTS[opsys]['robotdir']
        global_dict['execution_mode'] = execution_mode

        # mode_conf:
        # >> suite tuples, cache, execution
        mode_conf = conf['execution_mode'][1]
        # mode specific settings
        # Because of the WATO structure ("function follows form") we do not have
        # keys here, but only a list of Tuples. Depending on the mode, fields
        # are hidden, the indizes my vary!
        #                        serial       parallel      external      idx
        # global
        #   cache_time           x                          x             1
        #   execution_interval   x                                        0
        # suite
        #   cache_time                        x             x
        #   execution_interval                x

        if execution_mode in ['agent_serial']:
            global_dict['cache_time'] = mode_conf[1]
            global_dict['execution_interval'] = mode_conf[2]
        elif execution_mode in ['agent_parallel']:
            # set nothing, done in suites!
            pass
        elif execution_mode in ['external']:
            # For now, we assume that the external mode is meant to execute all
            # suites exactly as configured. Hence, we can use the global cache time.
            global_dict['cache_time'] = mode_conf[1]
        # suite_tuple:
        # >> path, tag, piggyback, robot_params{}, cachetime, execution_int
        if 'suites' in mode_conf[0]:
            for suite_tuple in mode_conf[0]['suites']:
                path = suite_tuple[0]
                tag = suite_tuple[1].get('tag', None)
                # generate a unique ID (path_tag)
                suiteid = make_suiteid(path, tag)
                suitedict = {
                    'path': path,
                }
                suitedict.update(self.dict_if_set('tag', tag))
                suitedict.update(suite_tuple[2].get('piggybackhost', {}))
                # ROBOT PARAMS
                robot_param_dict = suite_tuple[3].get('robot_params', {})
                # Variables: transform the var 'list of tuples' into a dict.
                vardict = {}
                for (k1, v1) in robot_param_dict.items():
                    if k1 == 'variable':
                        for t in v1:
                            vardict.update({t[0]: t[1]})
                robot_param_dict.update(self.dict_if_set('variable', vardict))
                suitedict.update(robot_param_dict)
                # CACHE & EXECUTION TIME
                timing_dict = {}
                if execution_mode == 'agent_parallel':
                    timing_dict.update({'cache_time': suite_tuple[4]})
                    timing_dict.update({'execution_interval': suite_tuple[5]})
                # if execution_mode == 'external':
                #     timing_dict.update(
                #         {'cache_time': global_dict['cache_time']})
                suitedict.update(timing_dict)
                if suiteid in self.cfg_dict['suites']:
                    raise MKGeneralException(
                        "Error in bakery plugin 'robotmk': Suite with ID %s is not unique. Please use tags to solve this problem."
                    )
                self.cfg_dict['suites'].update({suiteid: suitedict})

    @staticmethod
    def dict_if_set(key, value):
        if bool(value):
            return {key: value}
        else:
            return {}

    def get_os_default(self, setting):
        '''Read a setting from the DEFAULTS hash. If no OS setting is found, try noarch.
        Args:
            setting (str): Setting name
        Returns:
            str: The setting value
        '''
        value = self._DEFAULTS[self.opsys].get(setting, None)
        if value is None:
            value = self._DEFAULTS['noarch'].get(setting, None)
            if value is None:
                raise MKGeneralException(
                    "Error in bakery plugin 'robotmk': Cannot determine OS.")
        return value

    @property
    def global_dict(self):
        return self.cfg_dict['global']

    @property
    def suites_dict(self):
        return self.cfg_dict['suites']


def make_suiteid(robotpath, tag):
    '''Create a unique ID from the Robot path (dir/.robot file) and the tag. 
    with underscores for everything but letters, numbers and dot.'''
    if bool(tag):
        tag_suffix = "_%s" % tag
    else:
        tag_suffix = ""
    composite = "%s%s" % (robotpath, tag_suffix)
    outstr = re.sub('[^A-Za-z0-9\.]', '_', composite)
    # make underscores unique
    return re.sub('_+', '_', outstr).lower()


bakery_info["robotmk"] = {
    "bake_function": bake_robotmk,
    "os": ["linux", "windows"],
}

header = """# This file is part of Robotmk, a module for the integration of Robot
# framework test results into Checkmk.
#
# https://robotmk.org
# https://github.com/simonmeggle/robotmk
# https://robotframework.org/#tools\n\n"""
