#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2021 Simon Meggle <simon.meggle@elabit.de>

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

ROBOTMK_VERSION = 'v1.0.3'

from typing import Iterable, TypedDict, List
from pathlib import Path
import os
import yaml
import re
import copy

import cmk.utils.paths
from cmk.utils.exceptions import MKGeneralException

from .bakery_api.v1 import (
   OS,
   Plugin,
   PluginConfig,
   WindowsConfigEntry,
   register,
   FileGenerator,
   SystemBinary
)

# This dict only adds the new key if the value is not empty
class DictNoNone(dict):
    def __setitem__(self, key, value):
        if key in self or bool(value):
            dict.__setitem__(self, key, value)



class RMKSuite():
    def __init__(self, suite_tuple):
        self.suite_tuple = suite_tuple      

    @property
    def suite2dict(self): 
        suite_dict = DictNoNone()
        suite_dict['path']= self.path
        suite_dict['tag']= self.tag
        suite_dict['piggybackhost']= self.piggybackhost
        suite_dict.update(self.robot_param_dict)
        return suite_dict

    @property
    def path(self):
        return self.suite_tuple[0]

    @property
    def tag(self):
        return self.suite_tuple[1].get('tag', None)

    @property
    def piggybackhost(self):
        return self.suite_tuple[2].get('piggybackhost', None)

    @property
    def robot_param_dict(self):
        robot_params = copy.deepcopy(self.suite_tuple[3].get('robot_params', {}))
        # Variables: transform the var 'list of tuples' into a dict.
        vardict = {}
        for (k1, v1) in robot_params.items():
            if k1 == 'variable':
                for t in v1:
                    vardict.update({t[0]: t[1]})
        robot_params.update(self.dict_if_set('variable', vardict))        
        return robot_params

    @property
    def suiteid(self):
        '''Create a unique ID from the Robot path (dir/.robot file) and the tag. 
        with underscores for everything but letters, numbers and dot.'''
        if bool(self.tag):
            tag_suffix = "_%s" % self.tag
        else:
            tag_suffix = ""
        composite = "%s%s" % (self.path, tag_suffix)
        outstr = re.sub('[^A-Za-z0-9\.]', '_', composite)
        # make underscores unique
        return re.sub('_+', '_', outstr).lower()

    @staticmethod
    # Return a dict with key:value only if value is set
    def dict_if_set(key, value):
        if bool(value):
            return {key: value}
        else:
            return {}

class RMK():
    def __init__(self, conf):
        self.execution_mode = conf['execution_mode'][0]
        mode_conf = conf['execution_mode'][1]        
        self.cfg_dict = {
            'global': DictNoNone(),
            'suites': DictNoNone(),
        }
        # handy dict shortcuts
        global_dict = self.cfg_dict['global']
        suites_dict = self.cfg_dict['suites']
        global_dict['execution_mode'] =  self.execution_mode
        global_dict['agent_output_encoding'] =  conf['agent_output_encoding']
        global_dict['transmit_html'] =  conf['transmit_html']
        global_dict['logging'] =  conf['logging']
        global_dict['log_rotation'] =  conf['log_rotation']
        global_dict['robotdir'] =  conf.get('robotdir')
        if self.execution_mode == 'agent_serial':
            global_dict['cache_time'] = mode_conf[1]
            global_dict['execution_interval'] = mode_conf[2]
            self.execution_interval = mode_conf[2]
        elif self.execution_mode == 'external':
            # For now, we assume that the external mode is meant to execute all
            # suites exactly as configured. Hence, we can use the global cache time.
            global_dict['cache_time'] = mode_conf[1]        
        if 'suites' in mode_conf[0]:
            # each suite suite_tuple:
            # >> path, tag, piggyback, robot_params{}
            for suite_tuple in mode_conf[0]['suites']:
                suite = RMKSuite(suite_tuple)
                if suite.suiteid in self.cfg_dict['suites']:
                    raise MKGeneralException(
                        "Error in bakery plugin 'robotmk': Suite with ID %s is not unique. Please use tags to solve this problem." % suite.suiteid 
                    )      

                self.cfg_dict['suites'].update({
                    suite.suiteid: suite.suite2dict})        
        pass

    def controller_plugin(self, opsys: OS) -> Plugin:
        return  Plugin(
            base_os=opsys,
            source=Path('robotmk.py'),
        )

       
    def runner_plugin(self, opsys: OS) -> Plugin:
        # TODO: when external mode:
        #  => bin!     
        #  when not: 
        #  no target, interval!
        if self.execution_mode == 'external':
            # Runner and Controller have to be deployed as bin
            # /omd/sites/v2/lib/python3/cmk/base/cee/bakery/core_bakelets/bin_files.py

            # cmk.utils.paths.local_agents_dir ?? 
            pass
        elif self.execution_mode == 'agent_serial': 
            # the runner plugin gets
            return Plugin(
                base_os=opsys,
                source=Path('robotmk-runner.py'),
                # TODO: interval=interval,
                interval=self.execution_interval,
            )
        else: 
            raise MKGeneralException(
                "Error: Execution mode %s is not supported." % self.execution_mode 
            )              

    def yml(self, opsys: OS, robotmk) -> PluginConfig:
        return PluginConfig(base_os=opsys,
            lines=_get_yml_lines(robotmk),
            target=Path('robotmk.yml'),
            include_header=True)

    def bin_files(self, opsys: OS):
        files = []            
        if self.execution_mode == 'external':  
            for file in 'robotmk.py robotmk-runner.py'.split():
                files.append(SystemBinary(
                    base_os=opsys,
                    source=Path('plugins/%s' % file),
                    target=Path(file),
                ))
        return files

    @property
    def global_dict(self):
        return self.cfg_dict['global']

    @property
    def suites_dict(self):
        return self.cfg_dict['suites']

def get_robotmk_files(conf) -> FileGenerator:
    # ALWAYS (!) make a deepcopy of the conf dict. Even if you do not change
    # anything on it, there are strange changes ocurring while building the
    # packages of OS. A deepcopy solves this completely.
    robotmk = RMK(copy.deepcopy(conf))    
    for base_os in [OS.LINUX, OS.WINDOWS]: 
        controller_plugin =  robotmk.controller_plugin(base_os)
        runner_plugin =  robotmk.runner_plugin(base_os)
        robotmk_yml = robotmk.yml(base_os, robotmk)
        bin_files = robotmk.bin_files(base_os)
        yield controller_plugin
        yield runner_plugin
        yield robotmk_yml
        for file in bin_files: 
            yield file

def _get_yml_lines(robotmk) -> List[str]:

    header = "# This file is part of Robotmk, a module for the integration of Robot\n" +\
        "# framework test results into Checkmk.\n" +\
        "#\n" +\
        "# https://robotmk.org\n" +\
        "# https://github.com/simonmeggle/robotmk\n" +\
        "# https://robotframework.org/\n" +\
        "# ROBOTMK VERSION: %s\n" % ROBOTMK_VERSION
    headerlist = header.split('\n')   
    # PyYAML is very picky with Dict subclasses; add a representer to dump the data. 
    # https://github.com/yaml/pyyaml/issues/142#issuecomment-732556045
    yaml.add_representer(
        DictNoNone, 
        lambda dumper, data: dumper.represent_mapping('tag:yaml.org,2002:map', data.items())
        )
    bodylist = yaml.dump(
        robotmk.cfg_dict,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=True).split('\n')         
    return headerlist + bodylist

register.bakery_plugin(
   name="robotmk",
   files_function=get_robotmk_files,
)
