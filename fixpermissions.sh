#!/bin/bash

# This script fixes the permissions for all robotmk files which are symlinked into OMD. 
# (switching branches makes files write-protected for the site user)
# !! CMK V2 only !!

SCRIPT=$(readlink -f "$0")
SCRIPTPATH=$(dirname "$SCRIPT")
SITE=$1
OMDSITES=/opt/omd/sites

function relink {
    chmod 666 $1
    if [ "x$SITE" != "x" ]; then 
        TARGET="$SCRIPTPATH/$1"
        LINKNAME="$OMDSITES/$SITE/$2"
        echo "Linking $TARGET into OMD site $SITE ..."
        ln -fs $TARGET $LINKNAME       
    fi
}

# Version specific ####
# Check plugin
relink lib/check_mk/base/plugins/agent_based/robotmk.py  local/lib/check_mk/base/plugins/agent_based/
# bakery script
relink lib/check_mk/base/cee/plugins/bakery/robotmk.py   local/lib/check_mk/base/cee/plugins/bakery/

# Agent plugins
relink agents/plugins/robotmk.py                         local/share/check_mk/agents/plugins/
relink agents/plugins/robotmk-runner.py                  local/share/check_mk/agents/plugins/
# Metrics
relink web/plugins/metrics/robotmk.py                    local/share/check_mk/web/plugins/metrics/
# WATO pages
relink web/plugins/wato/robotmk_wato_params_bakery.py    local/share/check_mk/web/plugins/wato/
relink web/plugins/wato/robotmk_wato_params_check.py     local/share/check_mk/web/plugins/wato/
relink web/plugins/wato/robotmk_wato_params_discovery.py local/share/check_mk/web/plugins/wato/

