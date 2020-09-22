
import ctypes
import win32api
import win32event
import win32process
import win32security
import win32ts
import win32con

import logging
from time import sleep

# nur für dump_token verwendet
from security_enums import TOKEN_GROUP_ATTRIBUTES, TOKEN_PRIVILEGE_ATTRIBUTES, \
     SECURITY_IMPERSONATION_LEVEL, TOKEN_TYPE, TOKEN_ELEVATION_TYPE

#sleep(1000)
 
def run_process(command_line):
   # STEP 1: ERMITTELN DES EIGENEN TOKENS, ANPASSEN DER PRIVILEGIEN
   process = win32api.GetCurrentProcess()
   token = win32security.OpenProcessToken(process,
      win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY)
   se_enable = win32security.SE_PRIVILEGE_ENABLED
   #log_debug("Vor Token-Anpassung =====================")
   #dump_token(token)  
   # Privileg 1: 
   tcb_privilege_flag = win32security.\
                        LookupPrivilegeValue(None,
                                             
                                             win32security.SE_INCREASE_QUOTA_NAME)
 
   win32security.AdjustTokenPrivileges(token, 0,
                                              [(tcb_privilege_flag,
                                                se_enable)])
   #2                                             
   tcb_privilege_flag = win32security.\
                        LookupPrivilegeValue(None,
                                             win32security.SE_ASSIGNPRIMARYTOKEN_NAME)
 
   win32security.AdjustTokenPrivileges(token, 0,
                                              [(tcb_privilege_flag,
                                                se_enable)])
   #2                                             
   tcb_privilege_flag = win32security.\
                        LookupPrivilegeValue(None,
                                             win32security.SE_TCB_NAME)
 
   win32security.AdjustTokenPrivileges(token, 0,
                                              [(tcb_privilege_flag,
                                                se_enable)])
   #log_debug("Nach Token-Anpassung =====================")
   #dump_token(token)

   # STEP 2: ERMITTELN DES DESKTOP-USERS, STARTEN DES PROZESSES
   console_session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
   console_user_token = win32ts.WTSQueryUserToken(console_session_id)
   startupinfo = win32process.STARTUPINFO()
   startupinfo.dwFlags = win32process.STARTF_USESHOWWINDOW
   startupinfo.wShowWindow = win32con.SW_SHOW
   startupinfo.lpDesktop = 'winsta0\default'
 
   process_arguments = (console_user_token, None,
                       command_line,
                       None, None, 0, 0,None, None,
                       startupinfo)
 
   log_debug(f'Starting: {command_line}')
   
   try:
      proc_handle, thread_id ,pid, tid = win32process.CreateProcessAsUser(*process_arguments)
   except Exception as e:
      log_error(e)
   log_debug(f'Nach Start')
 
 
   win32event.WaitForSingleObject(proc_handle, win32event.INFINITE)
   rc = win32process.GetExitCodeProcess(proc_handle)
   log_debug(f'Prozess beendet, rc: {rc}')
   return(rc)
 
 
def setup_logging():
   global logger
   logger = logging.getLogger('dummy')
   logger.setLevel(logging.DEBUG)
 
   # File log
   fh = logging.FileHandler('c:\\robotmk.log')
   file_formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s - %(message)s')
   fh.setFormatter(file_formatter)
   fh.setLevel(logging.DEBUG)
   logger.addHandler(fh)

      
      

def log_debug(text):
   logger.debug(text)

def log_info(text):
   logger.info(text)

def log_warning(text):
   logger.warning(text)

def log_error(text):
   logger.error(text)


def log_debug_list(*texts):
   logger.debug(', '.join([str(t) for t in texts]))


def dump_token(th):
    token_type=win32security.GetTokenInformation(th, win32security.TokenType)
    log_debug_list('TokenType:', token_type, TOKEN_TYPE.lookup_name(token_type))
    if token_type==win32security.TokenImpersonation:
        imp_lvl=win32security.GetTokenInformation(th, win32security.TokenImpersonationLevel)
        log_debug_list('TokenImpersonationLevel:', imp_lvl, SECURITY_IMPERSONATION_LEVEL.lookup_name(imp_lvl))

    log_debug_list('TokenSessionId:', win32security.GetTokenInformation(th, win32security.TokenSessionId))

    privs=win32security.GetTokenInformation(th,win32security.TokenPrivileges)
    log_debug_list('TokenPrivileges:')
    for priv_luid, priv_flags in privs:
        flag_names, unk=TOKEN_PRIVILEGE_ATTRIBUTES.lookup_flags(priv_flags)
        flag_desc = ' '.join(flag_names)
        if (unk):
            flag_desc += '(' + str(unk) + ')'

        priv_name=win32security.LookupPrivilegeName('',priv_luid)
        priv_desc=win32security.LookupPrivilegeDisplayName('',priv_name)
        log_debug_list('\t', priv_name, priv_desc, priv_flags, flag_desc)

    log_debug_list('TokenGroups:')
    groups=win32security.GetTokenInformation(th,win32security.TokenGroups)
    for group_sid, group_attr in groups:
        flag_names, unk=TOKEN_GROUP_ATTRIBUTES.lookup_flags(group_attr)
        flag_desc = ' '.join(flag_names)
        if (unk):
            flag_desc += '(' + str(unk) + ')'
        if group_attr & TOKEN_GROUP_ATTRIBUTES.SE_GROUP_LOGON_ID:
            sid_desc = 'Logon sid'
        else:
            sid_desc=win32security.LookupAccountSid('',group_sid)
        log_debug_list('\t',group_sid, sid_desc, group_attr, flag_desc)

    ## Vista token information types, will throw (87, 'GetTokenInformation', 'The parameter is incorrect.') on earier OS
    try:
        is_elevated=win32security.GetTokenInformation(th, win32security.TokenElevation)
        log_debug_list('TokenElevation:', is_elevated)
    except pywintypes.error as details:
        if details.winerror != winerror.ERROR_INVALID_PARAMETER:
            raise
        return None
    log_debug_list('TokenHasRestrictions:', win32security.GetTokenInformation(th, win32security.TokenHasRestrictions))
    log_debug_list('TokenMandatoryPolicy', win32security.GetTokenInformation(th, win32security.TokenMandatoryPolicy))   
    log_debug_list('TokenVirtualizationAllowed:', win32security.GetTokenInformation(th, win32security.TokenVirtualizationAllowed))
    log_debug_list('TokenVirtualizationEnabled:', win32security.GetTokenInformation(th, win32security.TokenVirtualizationEnabled))

    elevation_type = win32security.GetTokenInformation(th, win32security.TokenElevationType)        
    log_debug_list('TokenElevationType:', elevation_type, TOKEN_ELEVATION_TYPE.lookup_name(elevation_type))
    if elevation_type!=win32security.TokenElevationTypeDefault:
        lt=win32security.GetTokenInformation(th, win32security.TokenLinkedToken)
        log_debug_list('TokenLinkedToken:', lt)
    else:
        lt=None
    return lt

setup_logging()
log_debug('=======')
run_process('c:\\windows\\system32\\notepad.exe')