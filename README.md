# Drive Info

This is a *python 3* program for getting the status of **HP** RAID drives, SCSI and SSD's drives on an HP server.

**NOTE: You must always run this as root**

Tested on Proxmox pve-manager/6.4-13/9f411e79 (running kernel: 5.4.157-1-pve) Python 3.7

## Required Programs

The following tools are required to be installed.

* ssacli
* smartctl
* lsblk
* lshw
* wget
* virt-what (optional for virtual environments)

## Python Modules

No non-standard python 3 modules are needed.

## Usage

```
nick@proliantdl380p:~/Scripts/drive_info$ sudo ./drive_info.py -h
usage: drive_info.py [-h] [-l LOG] [-ws WRITESUMMARYFILE]
                     [-rs READSUMMARYFILE] [-r] [-S] [-D] [--version]

Check Drive Stats

optional arguments:
  -h, --help            show this help message and exit
  -l LOG, --log LOG     path/name of log file (default:
                        /home/nick/Scripts/drive_info.log)
  -ws WRITESUMMARYFILE, --writesummaryfile WRITESUMMARYFILE
                        path/name of write summary file (default:
                        /home/nick/Scripts/disk_info.txt)
  -rs READSUMMARYFILE, --readsummaryfile READSUMMARYFILE
                        path/name of read summary file (default:
                        /shares/nick/Scripts/disk_info.txt)
  -r, --rescan          rescan drives
  -S, --summary         summary
  -D, --debug           debug mode
  --version             show program's version number and exit
```

Full info:
```
nick@proliantdl380p:~/Scripts/drive_info$ sudo ./drive_info.py
[I 2022-01-23 12:39:26,200] MainThread: *******************
[I 2022-01-23 12:39:26,201] MainThread: * Program Started *
[I 2022-01-23 12:39:26,201] MainThread: *******************
[I 2022-01-23 12:39:26,201] MainThread: drive_info.py version: 1.0.1
[I 2022-01-23 12:39:26,201] MainThread: Python Version: 3.7.3 (default, Jan 22 2021, 20:04:44) [GCC 8.3.0]
[I 2022-01-23 12:39:26,272] MainThread: Running on Host
[I 2022-01-23 12:39:26,352] MainThread: Drive: /dev/sda, Power On: 15544, Temp: 44, LBA: 703.37 GB, Status: OK, Available Spare: 100%, Remaining life: 100%
[I 2022-01-23 12:39:26,352] MainThread: Drive: /dev/nvme0n1, Power On: 6315, Temp: 38, LBA: 9.66 TB, Status: OK, Available Spare: 88%, Remaining life: 100%
[I 2022-01-23 12:39:27,550] MainThread: RAID Status: OK
```

Another Example:
```
nick@proliantml310e:~/Scripts/drive_info$ sudo ./drive_info.py
[I 2022-01-23 12:44:04,283] MainThread: *******************
[I 2022-01-23 12:44:04,283] MainThread: * Program Started *
[I 2022-01-23 12:44:04,283] MainThread: *******************
[I 2022-01-23 12:44:04,283] MainThread: drive_info.py version: 1.0.1
[I 2022-01-23 12:44:04,283] MainThread: Python Version: 3.7.3 (default, Jan 22 2021, 20:04:44) [GCC 8.3.0]
[I 2022-01-23 12:44:04,347] MainThread: Running on Host
[I 2022-01-23 12:44:10,362] MainThread: Drive: /dev/sda(0), Power On: 27358, Temp: 38, LBA: unknown, Status: OK
[I 2022-01-23 12:44:10,362] MainThread: Drive: /dev/sda(1), Power On: 42097, Temp: 38, LBA: unknown, Status: OK
[I 2022-01-23 12:44:10,362] MainThread: Drive: /dev/sda(2), Power On: 44892, Temp: 39, LBA: unknown, Status: OK
[I 2022-01-23 12:44:10,362] MainThread: Drive: /dev/sda(3), Power On: 46978, Temp: 39, LBA: unknown, Status: OK
[I 2022-01-23 12:44:10,363] MainThread: Drive: /dev/nvme0n1, Power On: 7874, Temp: 33, LBA: 14.0 TB, Status: OK, Available Spare: 100%, Remaining life: 97%
[I 2022-01-23 12:44:10,363] MainThread: Drive: /dev/sdb(0), Power On: 27358, Temp: 38, LBA: unknown, Status: OK
[I 2022-01-23 12:44:10,363] MainThread: Drive: /dev/sdb(1), Power On: 42097, Temp: 38, LBA: unknown, Status: OK
[I 2022-01-23 12:44:10,363] MainThread: Drive: /dev/sdb(2), Power On: 44892, Temp: 39, LBA: unknown, Status: OK
[I 2022-01-23 12:44:10,363] MainThread: Drive: /dev/sdb(3), Power On: 46978, Temp: 39, LBA: unknown, Status: OK
[I 2022-01-23 12:44:11,757] MainThread: RAID Status: OK
```

Summary Info:
```
nick@proliantdl380p:~/Scripts/drive_info$ sudo ./drive_info.py -S
All drives OK,
```

On first use, the program will scan the local drives, and save the drive configuration in a `config.ini` file, so the acrivity does not need to be repeated every time.

Run `sudo ./drive_info.py -r` to rescan if your drive configuration changes.

The program will also download a new `drivedb.h` for `smartctl` usage, to ensure the drive database is up to date.

## Return value

The program returns 0 for Drives OK, or 1 for a drive issue.

## Summary File

The summary output is written to a file defined by `-ws`. If the program is run in a VM, then the drive checking is not performed, and the results are read from a file designated by the `-rs` option.

## Limitations

`drive_info.py` is intended to be run on bare metal **HP** servers (eg Proxmox) periodically, to check the RAID status. If run on a VM, the passed through drive characteristics are not available, so the contents of the summary file will be returned, if the drive path is available to the VM.

## S.M.A.R.T Characteristics

These vary depending on the drive manufacture, I've tried to pull out the most common ones, but YMMV.