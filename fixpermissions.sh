#!/bin/bash

# This script fixes the permissions for all robotmk files which are symlinked into OMD. 
# (switching branches makes files write-protected for the site user)

SCRIPT=$(readlink -f "$0")
SCRIPTPATH=$(dirname "$SCRIPT")

# bakery script
chmod 666 lib/check_mk/base/cee/plugins/bakery/robotmk.py
# Check plugin
chmod 666 lib/check_mk/base/plugins/agent_based/robotmk.py
# Agent plugins
chmod 666 agents/plugins/*.py
# Metrics
chmod 666 web/plugins/metrics/robotmk.py
# WATO pages
chmod 666 web/plugins/wato/*.py
