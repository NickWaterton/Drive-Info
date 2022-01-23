#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#Program to check disk stats
#N Waterton 11th April 2019 V1.0.0 initial release

from __future__ import print_function
from __future__ import absolute_import
__version__ = "1.0.1"

import sys, os, shutil, json
from json import JSONDecoder, JSONDecodeError
import re
import time
import datetime as dt
import logging
from logging.handlers import RotatingFileHandler
import threading
import subprocess
from subprocess import check_output, CalledProcessError

global log

class disk_info():
    def __init__(self, name, drive):
        self.name = name
        self.drive = drive
        self.num_drives = None
        self.temp = None
        self.life = 100
        self.spare = 100
        self.bytes_written = None
        self.power_on_hrs = None
        self.smart_status = None
        self.ssd = False
        self.smart = False
        self.raid = False
        self.drive_db = ''
        if os.path.isfile('drivedb.h'):
            self.drive_db = '-B drivedb.h'
        if drive['SMART']:
            self.smart = True
            if 'raid' not in drive['type'].lower():
                self.drive_info=self.SCSI_disk_info()
            else:
                self.drive_info=self.RAID_disk_info()
                self.raid = True
                
    def human_size(self,size_bytes):
        """
        format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
        Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
        e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
        """
        if size_bytes == 1:
            # because I really hate unnecessary plurals
            return "1 byte"

        suffixes_table = [('bytes',0),('KB',0),('MB',1),('GB',2),('TB',2), ('PB',2)]

        num = float(size_bytes)
        for suffix, precision in suffixes_table:
            if num < 1024.0:
                break
            num /= 1024.0

        if precision == 0:
            formatted_size = "%d" % num
        else:
            formatted_size = str(round(num, ndigits=precision))

        return "%s %s" % (formatted_size, suffix)
                
    def get_data_from_text(self, match, lines):
        val = None
        LBA_size = 512
        last_column = [ 'Airflow_Temperature_Cel',
                        'Temperature_Celsius',
                        'Total_LBAs_Written',
                        'Host_Writes_32MiB',
                        'Power_On_Hours',
                        'SMART Health Status',
                        'SMART overall-health'] #values reported by SSD's in last column
        if not isinstance(match, list):
            match = [match]
        if not isinstance(lines, list):
            lines = [lines]
        for line_num, text in enumerate(lines):
            if len(text) > 0:
                if 'Model Family' in text and 'Seagate Constellation' in text:
                    last_column.remove('Temperature_Celsius')
                if any(check.lower() in text.lower() for check in match):
                    info = text.split()
                    if any(check in text for check in last_column):
                        if 'SMART Health Status' in text:
                            val = info[-1]
                            return val
                        if 'SMART overall-health' in text:
                            val = info[-1]
                            if 'passed' in val.lower():
                                val = 'OK'
                            return val
                        pos = 0
                        while pos > -len(text):
                            pos -= 1
                            try:
                                val = int(info[pos])
                                break
                            except ValueError:
                                pass
                        if 'Total_LBAs_Written' in text:
                            val = val*LBA_size
                        if 'Host_Writes_32MiB' in text:
                            val = val*32*1024*1000
                        if val > 99999:
                            val = self.human_size(val)
                        return val
                    if 'Available Spare' in text:
                        #SSD Spare capacity Available
                        val = info[-1].replace("%","")
                        return val
                    if 'Percentage Used' in text:
                        #SSD life remaining
                        val =  str(100 - int(info[-1].replace("%","")))
                        return val
                    if 'Data Units Written' in text:
                        val = info[-2]+' '+info[-1]
                        return val.replace('[','').replace(']','')
                    elif 'write:' in text:
                        val = self.human_size(float(info[-2])*1000000000)
                        return val
                    if '(hours)' in text:
                        #power on hours is on the next line
                        if 'in progress' in lines[line_num+1]:
                            return 'pending'
                        line_text = lines[line_num+1].split()
                        for column, data in enumerate(line_text):
                            if data.isdigit() and column > 2: #skip test number
                                val=data
                                return val
                    for count, data in enumerate(info):
                        data = data.replace('%','').replace(',','')
                        if data.isdigit() and count > 0:
                            val = int(data)
                            return val
        return val
                          
    def SCSI_disk_info(self):
        self.num_drives = 1
        now = dt.datetime.now()
        if now.hour == 0 and now.minute == 0:   #run short drive test at midnight
            log.info('running self test')
            cmd_string = 'smartctl %s -t short %s' % (self.drive_db,self.name)
        else:
            cmd_string = 'smartctl %s -a %s' % (self.drive_db,self.name)
        try:
            smart_text = check_output(cmd_string.split())
        except CalledProcessError as e:
            smart_text = e.output
        lines = smart_text.decode('utf8').split('\n')
        log.debug('SMART: %s' % lines)
        self.temp = self.get_data_from_text('Temperature', lines)
        self.bytes_written = self.get_data_from_text(['Total_LBAs_Written', 'Data Units Written', 'write:', 'Host_Writes_32MiB'], lines)
        self.smart_status = self.get_data_from_text(['SMART Health Status', 'SMART overall-health'], lines)
        self.power_on_hrs = self.get_data_from_text(['Power_On_Hours', 'Power On Hours'], lines)
        if self.drive['ssd']:
            self.ssd = True
            self.life = self.get_data_from_text(['Percentage Used','Wear_Leveling_Count', 'Remaining_Lifetime_Perc'], lines)
            self.spare = self.get_data_from_text(['Available Spare', 'Available_Reservd_Space'], lines)
        
    def RAID_disk_info(self):
        physicaldrives = self.drive["logical_volumes"][0]["drives"]
        self.num_drives = len(physicaldrives)
        log.debug('number of drives in raid %s: %s' % (self.name, self.num_drives))
        if self.num_drives > 0:
            self.temp = []
            self.life = []
            self.spare = []
            self.bytes_written = []
            self.power_on_hrs = []
            self.smart_status = []
            self.ssd = []
        log.debug('RAID drives: %s' % self.drive["logical_volumes"][0]["drives"])
        for physicaldrive in physicaldrives:
            drive_num = int(physicaldrive["physicaldrive"].split(':')[-1]) -1
            #log.info('getting data for %s(%d)' % (self.name,drive_num ))
            now = dt.datetime.now()
            if now.hour == 0 and now.minute == 0:   #run short drive test at midnight
                log.info('running self test')
                cmd_string = 'smartctl %s -t short %s -d cciss,%s' % (self.drive_db, self.name, drive_num)
            else:
                cmd_string = 'smartctl %s -a %s -d cciss,%s' % (self.drive_db, self.name, drive_num)
            try:
                smart_text = check_output(cmd_string.split())
            except CalledProcessError as e:
                smart_text = e.output
            lines = smart_text.decode('utf8').split('\n')
            log.debug('SMART: %s' % lines)
            self.temp.append(self.get_data_from_text('Temperature', lines))
            self.bytes_written.append(self.get_data_from_text(['Total_LBAs_Written', 'Data Units Written', 'write:', 'Host_Writes_32MiB'], lines))
            self.smart_status.append(self.get_data_from_text(['SMART Health Status', 'SMART overall-health'], lines))
            self.power_on_hrs.append(self.get_data_from_text(['Power_On_Hours', 'Power On Hours', '(hours)'], lines))
            if self.drive['ssd']:
                self.ssd.append(True)
                self.life.append(self.get_data_from_text(['Percentage Used','Wear_Leveling_Count', 'Remaining_Lifetime_Perc'], lines))
                self.spare.append(self.get_data_from_text(['Available Spare', 'Available_Reservd_Space'], lines))
            else:
                self.ssd.append(False)
                
 
        
NOT_WHITESPACE = re.compile(r'[^\s]')

def decode_stacked(document, pos=0, decoder=JSONDecoder()):
    while True:
        match = NOT_WHITESPACE.search(document, pos)
        if not match:
            return
        pos = match.start()

        try:
            obj, pos = decoder.raw_decode(document, pos)
        except JSONDecodeError:
            # do something sensible if there's some error
            return
            raise
        yield obj
    
def get_drives(config_file = 'config.ini'):
    log.info('rescanning drives, please wait ...')
    drives = {}
    drives_1 = json.loads(check_output('lsblk -J'.split()).decode('utf-8'))
    drives_2_raw = check_output('lshw -C storage -C disk -json'.split()).decode('utf8').replace('\n','').strip()
    drives_2 = []
    for obj in decode_stacked(drives_2_raw):
        drives_2.append(obj)      
    log.debug('got drives_2 data: \n%s' % json.dumps(drives_2, indent=2))
    try:
        drives_3 = check_output('ssacli ctrl all show status'.split()).decode('utf8')
        log.debug('got drives_3 data: \n%s' % drives_3)
    except CalledProcessError:
        drives_3 = ''
    
    controllers = []
    for line in drives_3.split('\n'):
        if 'slot' in line.lower():
            words = line.split()
            for word in words:
                if word.isdigit():
                    controllers.append(int(word))
                    log.info("found: %s, adding controller: %s" % (line, word))
                    
    for controller in controllers:
        cmd_string = 'ssacli ctrl slot=%s show config' % controller
        drives_4 = check_output(cmd_string.split()).decode('utf8')
        log.debug('got drives_4 data: \n%s' % drives_4)
    
    
    for drive in drives_1["blockdevices"]:
        if 'loop' not in drive['type']:
            drive_name = '/dev/' + drive['name']
            drives[drive_name] = {}
            drives[drive_name]['size'] = drive['size']
            if 'nvme' in drive['name'].lower():
                drives[drive_name]['SMART'] = True  #assume nvme drives report SMART data
                drives[drive_name]['type'] = 'NVME SSD'
                drives[drive_name]['ssd'] = True
            else:
                drives[drive_name]['SMART'] = False
                drives[drive_name]['ssd'] = False
                drives[drive_name]['type'] = drive['type']
            if 'children' in drive.keys():  #no children for NVME drives, they are their own controller.
                drives[drive_name]['mountpoints'] = []
                for mountpoint in drive['children']:
                    if mountpoint["mountpoint"] != None:
                        drives[drive_name]['mountpoints'].append(mountpoint["mountpoint"] + "(" + mountpoint["size"] + ")")
    
    raid_controller_id = len(controllers)-1
    increment_controller = False
    for controller in drives_2:
        if increment_controller:
            raid_controller_id=max(raid_controller_id-1,0)
            increment_controller = False
        if controller.get('children'):
            for drive in controller['children']:
                drive_name = drive["logicalname"]
                if drive_name not in drives:
                    drives[drive_name] = {}
                    drives[drive_name]['size'] = drive['size']
                    drives[drive_name]['SMART'] = False
                drives[drive_name]['type'] = drive['description'] + " " + drive['product']
                if 'raid' in controller.get("description", "none").lower():
                    drives[drive_name]['type'] = 'RAID ' + drives[drive_name]['type']
                    if len(controllers) > 0:
                        controller["physid"] = controllers[raid_controller_id]
                        increment_controller = True
                    drives[drive_name]["controller_physid"] = controller["physid"]
                    drives[drive_name]['logical_volumes'] = []
                    
                    cmd_string = 'ssacli ctrl slot=%s ld all show status' % controller["physid"]
                    l_volumes = check_output(cmd_string.split())
                    lines = l_volumes.decode('utf8').split('\n')
                    l_volume_devs = {}
                    
                    for line in lines:
                        if len(line) > 0:
                            info = line.split()
                            if 'logicaldrive' in info[0]:
                                lv_num = info[1].strip()
                                cmd_string = 'ssacli ctrl slot=%s ld %s show' % (controller["physid"], lv_num)
                                l_volume_info = check_output(cmd_string.split())
                                info_lines = l_volume_info.decode('utf8').split('\n')
                                l_volume_devs[lv_num] = 'unknown'
                                for info_line in info_lines:
                                    if len(info_lines) > 0:
                                        disk_info = info_line.split(':')
                                        if 'Disk Name' in disk_info[0]:
                                            l_volume_devs[lv_num] = disk_info[1].strip()
                                            break
                    
                    cmd_string = 'ssacli ctrl slot=%s show config' % controller["physid"]
                    l_volumes = check_output(cmd_string.split())
                    lines = l_volumes.decode('utf8').split('\n')
                    
                    for line in lines:
                        if len(line) > 0:
                            info = line.split()
                            if len(info) > 1:
                                if 'logicaldrive' in info[0]:
                                    lv = {}
                                    lv['logicaldrive'] = info[1].strip()
                                    lv['size'] = info[2].replace('(','').strip() + " " + info[3].replace(',','').strip()
                                    lv['raid'] = info[5].replace('):','').strip()
                                    lv['status'] = info[-1].replace(')','').strip()
                                    lv['drives'] = []
                                    if drive_name == l_volume_devs[lv['logicaldrive']]:
                                        log.info('adding logical volume %s to drive %s' % (lv['logicaldrive'], drive_name))
                                        drives[drive_name]['logical_volumes'].append(lv)

                                if 'physicaldrive' in info[0] and drive_name == l_volume_devs[lv['logicaldrive']]:
                                    pd = {}
                                    pd['physicaldrive'] = info[1].strip()
                                    pd['type'] = info[6].strip() + " " + info[7].replace(',','').strip()
                                    pd['ssd'] = True if 'ssd' in info[7].lower() else False
                                    pd['size'] = info[8].strip() + " " + info[9].replace(',','').strip()
                                    if 'OK' in info[-1].replace(')','').strip():
                                        pd['status'] = info[-1].replace(')','').strip()
                                    else:
                                        pd['status'] = info[-2].replace(',','').strip() + " " + info[-1].replace(')','').strip()
                                    lv['drives'].append(pd)

    #log.info('drives: \n%s' % json.dumps(drives, indent=2))
                
    for drive in drives.copy().keys():
        cmd_string = 'smartctl -i %s' % drive
        try:
            drives_3 = check_output(cmd_string.split())
            for line in drives_3.decode('utf8').split('\n'):
                if 'SMART support is:' in line and 'Enabled' in line:
                    log.debug('set drive %s to SMART: True' % drive)
                    drives[drive]['SMART'] = True
                if 'solid state device' in line.lower() or 'ssd' in line.lower():
                    drives[drive]['ssd'] = True
        except CalledProcessError:
            log.warning('error checking SMART status in drive %s' % drive)
            pass
            
    log.debug('got drive info: %s' % json.dumps(drives, indent=2))
    
    with open(config_file, 'w') as f:
        f.write(json.dumps(drives, indent=2))
        
    return drives
        
def load_drives(config_file = 'config.ini'):
    with open(config_file, 'r') as f:
        drives=json.loads(f.read())
    return drives
    
def check_raid_failures(arg):
    raid_info=''
    special_strings=['failed', 'rebuilding', 'recovering']
    cmd_string = 'ssacli ctrl all show config'
    try:
        l_volumes = check_output(cmd_string.split())
        lines = l_volumes.decode('utf8').split('\n')
        
        for line in lines:
            if len(line) > 0:
                info = line.split()
                if any(check.lower() in info[-1].replace(')','').replace(',','').lower() for check in special_strings):
                    raid_info+= line.strip() + '\n'
                if any(check.lower() in info[-3].replace(')','').replace(',','').lower() for check in special_strings):
                    raid_info+= line.strip() + '\n'
        if not arg.summary:
            if raid_info != '':            
                log.info('RAID Problems: %s' % raid_info)
            else:
                log.info('RAID Status: OK')
    except CalledProcessError:
        pass
    return raid_info
    
def get_smart_data(drives):
    drive_data = {}
    for drive in drives:
        if drives[drive]['SMART']:
            drive_data[drive] = disk_info(drive, drives[drive])
    return drive_data
    
def print_smart_data(drive_data):
    for drive in drive_data.values():
        if drive.raid:
            for drive_no in range(drive.num_drives):
                #log.info('getting data for %s(%d), drive.power_on_hrs %s' % (drive.name,drive_no, len(drive.power_on_hrs) ))
                if drive.ssd[drive_no]:
                    ssd_text = ', Available Spare: {}%, Remaining life: {}%'.format(drive.spare[drive_no],drive.life[drive_no])
                else:
                    ssd_text = ''
                text = 'Drive: %s(%d), Power On: %s, Temp: %s, LBA: %s, Status: %s%s' % (drive.name,drive_no,drive.power_on_hrs[drive_no] if drive.power_on_hrs[drive_no] is not None else 'unknown',
                                                                       drive.temp[drive_no],
                                                                       drive.bytes_written[drive_no] if drive.bytes_written[drive_no] is not None else 'unknown',
                                                                       drive.smart_status[drive_no],
                                                                       ssd_text)
                log.info(text)    
        else:
            if drive.ssd:
                ssd_text = ', Available Spare: {}%, Remaining life: {}%'.format(drive.spare,drive.life)
            else:
                ssd_text = ''
            text = 'Drive: %s, Power On: %s, Temp: %s, LBA: %s, Status: %s%s' % (drive.name,drive.power_on_hrs if drive.power_on_hrs is not None else 'unknown',
                                                                   drive.temp,
                                                                   drive.bytes_written if drive.bytes_written is not None else 'unknown',
                                                                   drive.smart_status,
                                                                   ssd_text)

            log.info(text)
            
def get_smart_data_summary(drive_data):
    drive_issues = ''
    for drive in drive_data.values():
        if drive.raid:
            for drive_no in range(drive.num_drives):
                if drive.smart_status[drive_no] != 'OK':
                    if drive.ssd[drive_no]:
                        ssd_text = ', Available Spare: {}%, Remaining life: {}%'.format(drive.spare[drive_no], drive.life[drive_no])
                    else:
                        ssd_text = ''
                    drive_issues+= 'Drive: %s(%d), Power On: %s, Temp: %s, LBA: %s, Status: %s%s\n' % (drive.name,drive_no,drive.power_on_hrs[drive_no] if drive.power_on_hrs[drive_no] is not None else 'unknown',
                                                                           drive.temp[drive_no],
                                                                           drive.bytes_written[drive_no] if drive.bytes_written[drive_no] is not None else 'unknown',
                                                                           drive.smart_status[drive_no],
                                                                           ssd_text)
                    
        else:
            if drive.smart_status != 'OK':
                if drive.ssd:
                    ssd_text = ', Available Spare: {}%, Remaining life: {}%'.format(drive.spare, drive.life)
                else:
                    ssd_text = ''
                drive_issues+= 'Drive: %s, Power On: %s, Temp: %s, LBA: %s, Status: %s%s\n' % (drive.name,drive.power_on_hrs if drive.power_on_hrs is not None else 'unknown',
                                                                       drive.temp,
                                                                       drive.bytes_written if drive.bytes_written is not None else 'unknown',
                                                                       drive.smart_status,
                                                                       ssd_text)
    if drive_issues == '':
        return 'All drives OK, ', True
    return drive_issues, False
    
def is_virtual():
    # returns True if running on VM or container, else False
    #needs virt-what installed
    cmd_string = '/usr/sbin/virt-what'
    try:
        VM = check_output(cmd_string.split())
    except CalledProcessError as e:
        log.warning('WARN: could not determine virtual environment!: error: %s' % e.output)
        return False
    if len(VM) != 0:
        log.info('Running in: VM %s' % VM.decode('utf-8'))
        return True
    else:
        log.info('Running on Host')
    return False

def setup_logger(logger_name, log_file, level=logging.DEBUG, console=False):
    try:
        l = logging.getLogger(logger_name)
        if logger_name ==__name__:
            formatter = logging.Formatter('[%(levelname)1.1s %(asctime)s] %(threadName)10.10s: %(message)s')
        else:
            formatter = logging.Formatter('%(message)s')
        fileHandler = logging.handlers.RotatingFileHandler(log_file, mode='a', maxBytes=2000000, backupCount=5)
        fileHandler.setFormatter(formatter)
        if console == True:
          streamHandler = logging.StreamHandler()

        l.setLevel(level)
        l.addHandler(fileHandler)
        if console == True:
          streamHandler.setFormatter(formatter)
          l.addHandler(streamHandler)
    except IOError as e:
        if e[0] == 13: #errno Permission denied
            print("Error: %s: You probably don't have permission to write to the log file/directory - try sudo" % e)
        else:
            print("Log Error: %s" % e)
        sys.exit(1)
        
def main():
    import argparse
    #-------- Command Line -----------------
    parser = argparse.ArgumentParser(description='Check Drive Stats')
    parser.add_argument('-l','--log', action='store',type=str, default="/home/nick/Scripts/drive_info.log", help='path/name of log file (default: /home/nick/Scripts/drive_info.log)')
    parser.add_argument('-ws','--writesummaryfile', action='store',type=str, default="/home/nick/Scripts/disk_info.txt", help='path/name of write summary file (default: /home/nick/Scripts/disk_info.txt)')
    parser.add_argument('-rs','--readsummaryfile', action='store',type=str, default="/shares/nick/Scripts/disk_info.txt", help='path/name of read summary file (default: /shares/nick/Scripts/disk_info.txt)')
    parser.add_argument('-r','--rescan', action='store_true', help='rescan drives', default = False)
    parser.add_argument('-S','--summary', action='store_true', help='summary', default = False)
    parser.add_argument('-D','--debug', action='store_true', help='debug mode', default = False)
    parser.add_argument('--version', action='version', version="%(prog)s ("+__version__+")")

    arg = parser.parse_args()

    #----------- Global Variables -----------
    global log
    #-------------- Main --------------

    if arg.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    #setup logging
    setup_logger(__name__, arg.log,level=log_level,console=not arg.summary)

    log = logging.getLogger(__name__)

    #------------ Main ------------------

    log.info("*******************")
    log.info("* Program Started *")
    log.info("*******************")
    
    log.info("drive_info.py version: %s" % __version__)
    
    log.info("Python Version: %s" % sys.version.replace('\n',''))
    
    log.debug("DEBUG mode on")
    
    if is_virtual():
        #running in VM or container - don't read actual disks or anything, look for file written by actual host
        if os.path.isfile(arg.readsummaryfile):
            with open(arg.readsummaryfile, 'r') as f:
                disk_data = f.read()
                disk_time = disk_data.split(' ').pop(0)
                if time.time() -300 <= float(disk_time):
                    print(disk_data.replace(disk_time, '').strip())
                    sys.exit(0)
        print('No disk_info available')
        sys.exit(1)
    
    config_file = "config.ini"
    
    if not os.path.isfile('drivedb.h'):
        log.info('getting latest drive database')
        check_output('wget --content-disposition https://sourceforge.net/p/smartmontools/code/HEAD/tree/trunk/smartmontools/drivedb.h?format=raw'.split())
    
    if os.path.isfile(config_file) and not arg.rescan:
        drives = load_drives(config_file)
    else:
        drives = get_drives(config_file)
        
    log.debug('got drive info: \n%s' % json.dumps(drives, indent=2))
    
    data = get_smart_data(drives)
    summary=""
    status = True
    if not arg.summary:
        print_smart_data(data)
    else:
        summary, status = get_smart_data_summary(data)
    raid_issues = check_raid_failures(arg)
    if raid_issues != "":
        if not status:
            summary += raid_issues
        else:
            summary = raid_issues
        status = False
    
    try:
        if summary == '':
            summary = 'no data'
        with open(arg.writesummaryfile, 'w') as f:
            text = '%s %s' % (time.time(), summary)
            f.write(text)
    except Exception as e:
        log.warning('Error writing summary file: %s' % e)
    
    if arg.summary:
        print(summary)
        
        if 'failed' in summary.lower() or not status:
            sys.exit(1)

if __name__ == "__main__":
    main()
